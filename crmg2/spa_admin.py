"""Duyên Spa owner portal. Bảo vệ mọi thao tác ghi ở backend + CSRF."""
import re
from collections import Counter
from datetime import date, datetime, time, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Sum, Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST
from zoneinfo import ZoneInfo

from .models import TrialBooking
from .spa_admin_models import (
    SpaVisitRecord, SpaBookingSource, SpaBookingEvent, SpaSlotRule,
    SpaDayClosure, SpaServiceOverride, SpaSiteSettings,
)

HOURS = ('09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00', '17:00')
ACTIVE = ('pending', 'confirmed', 'completed')
LABELS = {
    'pending': 'Đang chờ', 'confirmed': 'Đặt lịch thành công',
    'completed': 'Đã hoàn thành', 'cancelled': 'Đã hủy', 'no_show': 'Không đến',
}
TZ = ZoneInfo('Asia/Ho_Chi_Minh')


def now_local():
    return timezone.now().astimezone(TZ)


def _viewer(fn):
    @login_required(login_url='/dang-nhap/')
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied('Chỉ nhân viên và chủ spa được phép xem lịch.')
        if not request.user.is_superuser:
            return redirect('staff_appointments')
        timezone.activate(TZ)
        return fn(request, *args, **kwargs)
    return wrapped


def _owner(fn):
    @login_required(login_url='/dang-nhap/')
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied('Chức năng chỉ dành cho chủ spa.')
        timezone.activate(TZ)
        return fn(request, *args, **kwargs)
    return wrapped


def _day(request):
    try:
        return date.fromisoformat(request.GET.get('date', ''))
    except (ValueError, TypeError):
        return now_local().date()


def _base(request, section, title, **context):
    return {
        'section': section,
        'page_title': title,
        'owner': request.user.is_superuser,
        'today': now_local().date(),
        'hours': HOURS,
        'status_labels': LABELS,
        **context,
    }


def _status(booking):
    if booking.is_cancelled or booking.status == 'cancelled':
        return 'cancelled'
    return booking.status


def _booking_row(b, day=None):
    st = _status(b)
    actual = b.spa_visit.actual_arrivals if hasattr(b, 'spa_visit') else None
    slot_str = b.appointment_time.strftime('%H:%M') if b.appointment_time else '—'
    return {
        'id': b.pk, 'name': b.full_name, 'phone': b.phone,
        'service': b.service, 'day': b.register_date, 'hour': slot_str,
        'party_size': b.party_size, 'actual_arrivals': actual,
        'status': st, 'label': LABELS.get(st, 'Chưa xác định'),
        'can_mark': st in ('pending', 'confirmed') and not b.is_cancelled,
        'can_no_show': st in ('pending', 'confirmed') and not b.is_cancelled
            and b.register_date <= now_local().date()
            and (b.register_date < now_local().date()
                 or (b.appointment_time is not None and b.appointment_time <= now_local().time())),
        'source': getattr(getattr(b, 'spa_source', None), 'get_source_display', lambda: 'Website')(),
    }


def _fetch_bookings(qs):
    return [_booking_row(b) for b in qs.select_related('spa_visit', 'spa_source')]


def _occupied(day):
    from .views import SPA_BOOKING_HOURS
    rows = (TrialBooking.objects.filter(register_date=day, status__in=ACTIVE, is_cancelled=False,
                                        appointment_time__isnull=False)
            .values('appointment_time').annotate(n=Sum('party_size')))
    result = {h: 0 for h in SPA_BOOKING_HOURS}
    for r in rows:
        key = r['appointment_time'].strftime('%H:%M')
        if key in result:
            result[key] = r['n'] or 0
    return result


def _cap_table(day):
    closed = SpaDayClosure.objects.filter(day=day, is_closed=True).exists()
    rules = {v.appointment_time.strftime('%H:%M'): v.capacity
             for v in SpaSlotRule.objects.filter(day=day)}
    counts = _occupied(day)
    return [{'hour': h, 'used': counts[h], 'cap': rules.get(h, 3),
             'free': max(0, (0 if closed else rules.get(h, 3)) - counts[h])} for h in HOURS], closed


def _stats(day):
    rows = TrialBooking.objects.filter(register_date=day)
    active = rows.exclude(Q(status='cancelled') | Q(status='no_show') | Q(is_cancelled=True))
    completed = rows.filter(status='completed', is_cancelled=False)
    actual = SpaVisitRecord.objects.filter(booking__in=completed).aggregate(n=Sum('actual_arrivals'))['n'] or 0
    return {
        'total': rows.count(),
        'expected': active.aggregate(n=Sum('party_size'))['n'] or 0,
        'actual': actual,
        'completed': completed.count(),
        'cancelled': rows.filter(Q(status='cancelled') | Q(is_cancelled=True)).count(),
        'no_show': rows.filter(status='no_show', is_cancelled=False).count(),
    }


@_owner
def dashboard(request):
    day = _day(request)
    stats = _stats(day)
    caps, _ = _cap_table(day)
    past = []
    for i in range(6, -1, -1):
        d = day - timedelta(days=i)
        past.append({'day': d, 'label': d.strftime('%d/%m'), 'total': _stats(d)['expected']})
    max_trend = max([r['total'] for r in past] or [1]) or 1
    for r in past:
        r['pct'] = round(100 * r['total'] / max_trend)
    top = (TrialBooking.objects.filter(register_date=day, status__in=ACTIVE, is_cancelled=False)
           .values('service').annotate(n=Sum('party_size')).order_by('-n')[:5])
    upcoming = TrialBooking.objects.filter(register_date__gte=day, status__in=('pending', 'confirmed'),
                                          is_cancelled=False).order_by('register_date', 'appointment_time', 'pk')[:6]
    context = _base(request, 'dashboard', 'Tổng quan', day=day, metrics=stats, cap_rows=caps,
                    trend=past, trend_max=max([x['total'] for x in past] or [1]) or 1,
                    service_rank=top, upcoming=_fetch_bookings(upcoming))
    return render(request, 'spa_admin/dashboard.html', context)


@_viewer
def bookings(request):
    day = _day(request)
    qs = TrialBooking.objects.filter(register_date=day).order_by('appointment_time', 'pk')
    search = (request.GET.get('q') or '').strip()[:100]
    status = request.GET.get('status') or 'all'
    if search:
        qs = qs.filter(Q(full_name__icontains=search) | Q(phone__icontains=search) | Q(service__icontains=search))
    if status in LABELS:
        qs = qs.filter(status=status)
    caps, _ = _cap_table(day)
    return render(request, 'spa_admin/bookings.html', _base(
        request, 'bookings', 'Quản lý lịch hẹn' if request.user.is_superuser else 'Xem lịch hẹn',
        day=day, rows=_fetch_bookings(qs), search=search, status=status, cap_rows=caps,
        services=list(_all_services().values()),
    ))


@_viewer
def history(request):
    qs = TrialBooking.objects.filter(status__in=('completed', 'cancelled', 'no_show')).order_by('-register_date', '-appointment_time', '-pk')
    search = (request.GET.get('q') or '').strip()[:100]
    status = request.GET.get('status') or 'all'
    if search:
        qs = qs.filter(Q(full_name__icontains=search) | Q(phone__icontains=search) | Q(service__icontains=search))
    if status in ('completed', 'cancelled', 'no_show'):
        qs = qs.filter(status=status)
    return render(request, 'spa_admin/history.html', _base(
        request, 'history', 'Lịch sử & trạng thái', rows=_fetch_bookings(qs[:250]),
        search=search, status=status,
        total_completed=TrialBooking.objects.filter(status='completed').count(),
        total_cancelled=TrialBooking.objects.filter(Q(status='cancelled') | Q(is_cancelled=True)).count(),
        total_noshow=TrialBooking.objects.filter(status='no_show').count(),
    ))


@_owner
def slots(request):
    day = _day(request)
    if request.method == 'POST':
        try:
            day = date.fromisoformat(request.POST.get('day', ''))
            day_caps = {h: int(request.POST.get('capacity_' + h.replace(':', ''), '3')) for h in HOURS}
            if any(c < 0 or c > 3 for c in day_caps.values()):
                raise ValueError('Số chỗ tối đa mỗi khung giờ là 3, tối thiểu 0.')
            close = request.POST.get('closed') == 'on'
            with transaction.atomic():
                occupied = _occupied(day)
                if close and any(occupied.values()):
                    raise ValueError('Ngày này đã có lịch. Hãy xử lý lịch hiện có trước khi đóng ngày.')
                if not close and any(day_caps[h] < occupied[h] for h in HOURS):
                    raise ValueError('Không thể giảm sức chứa thấp hơn số người đã đặt.')
                SpaDayClosure.objects.update_or_create(day=day, defaults={'is_closed': close})
                for h, c in day_caps.items():
                    SpaSlotRule.objects.update_or_create(day=day, appointment_time=time.fromisoformat(h),
                                                         defaults={'capacity': c})
            messages.success(request, 'Đã lưu sức chứa và ngày hoạt động.')
        except (ValueError, TypeError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse('spa_admin_slots') + '?date=' + day.isoformat())
    caps, closed = _cap_table(day)
    return render(request, 'spa_admin/slots.html', _base(request, 'slots', 'Khung giờ & sức chứa',
                                                        day=day, cap_rows=caps, closed=closed))


def _all_services():
    from .views import get_spa_services
    return get_spa_services(include_inactive=True)


@_owner
def services(request):
    all_services = _all_services()
    from .views import SPA_SERVICES

    rows = [
        {
            'slug': slug,
            **info,
            'can_delete': True
        }
        for slug, info in all_services.items()
    ]
    selected = request.GET.get('edit', '')
    edit = next((r for r in rows if r['slug'] == selected), None)
    return render(request, 'spa_admin/services.html', _base(request, 'services', 'Quản lý dịch vụ',
                                                            rows=rows, edit=edit))


@require_POST
@_owner
def save_service(request):
    from .views import SPA_SERVICES
    source_slug = (request.POST.get('slug') or '').strip()
    name = (request.POST.get('name') or '').strip()[:100]
    description = (request.POST.get('description') or '').strip()[:3000]
    # Kiểm tra tên dịch vụ
    if not name:
        messages.error(request, 'Vui lòng nhập tên dịch vụ.')
        return redirect('spa_admin_services')

    # Cho phép nhập giá: 400000, 400.000, 400,000
    raw_price = (request.POST.get('price') or '').strip()
    formatted_price = raw_price.lower().replace(' ', '')

    for suffix in ('vnđ', 'vnd', 'đ'):
        if formatted_price.endswith(suffix):
            formatted_price = formatted_price[:-len(suffix)]
            break

    if not re.fullmatch(
        r'(?:\d+|\d{1,3}(?:[.,]\d{3})+)',
        formatted_price
    ):
        messages.error(
            request,
            'Giá không hợp lệ. Ví dụ: 400000 hoặc 400.000'
        )
        return redirect('spa_admin_services')

    price = int(
        formatted_price.replace('.', '').replace(',', '')
    )

    if price > 1_000_000_000:
        messages.error(
            request,
            'Giá dịch vụ không được vượt quá 1 tỷ đồng.'
        )
        return redirect('spa_admin_services')
    if not source_slug:

        raw = name.lower().replace('đ', 'd')
        source_slug = slugify(raw)[:90]

        exists_active = SpaServiceOverride.objects.filter(
            slug=source_slug,
            is_deleted=False
        ).exists()

        deleted_default = SpaServiceOverride.objects.filter(
            slug=source_slug,
            is_deleted=True
        ).exists()

        if (
                not source_slug
                or exists_active
                or (source_slug in SPA_SERVICES and not deleted_default)
        ):
            messages.error(
                request,
                'Tên dịch vụ đã tồn tại hoặc không hợp lệ.'
            )

            return redirect('spa_admin_services')
    elif source_slug not in SPA_SERVICES and not SpaServiceOverride.objects.filter(slug=source_slug).exists():
        raise Http404('Dịch vụ không tồn tại.')
    SpaServiceOverride.objects.update_or_create(slug=source_slug, defaults={
        'is_deleted': False,
        'name': name, 'price': price, 'description': description,
        'is_active': request.POST.get('is_active') == 'on',
    })
    messages.success(request, 'Đã lưu dịch vụ. Thông tin mới được dùng cho trang dịch vụ và đặt lịch.')
    return redirect('spa_admin_services')

@require_POST
@_owner
@require_POST
@_owner
def delete_service(request):

    from .views import SPA_SERVICES, get_spa_services

    slug = (request.POST.get('slug') or '').strip()

    # Lấy danh sách tất cả dịch vụ chưa bị xóa
    all_services = get_spa_services(include_inactive=True)

    service = all_services.get(slug)

    if service is None:
        messages.error(
            request,
            'Dịch vụ không tồn tại hoặc đã được xóa.'
        )
        return redirect('spa_admin_services')

    # Kiểm tra lịch hẹn chưa xử lý
    names_to_check = [service['name']]

    if slug in SPA_SERVICES:
        names_to_check.append(SPA_SERVICES[slug]['name'])

    has_bookings = TrialBooking.objects.filter(
        service__in=names_to_check,
        register_date__gte=now_local().date(),
        status__in=['pending', 'confirmed'],
        is_cancelled=False
    ).exists()

    if has_bookings:

        messages.error(
            request,
            'Không thể xóa dịch vụ vì vẫn còn lịch hẹn '
            'chưa xử lý. Vui lòng xử lý lịch trước.'
        )

        return redirect('spa_admin_services')

    # Đánh dấu xóa cho cả dịch vụ gốc và tự thêm
    SpaServiceOverride.objects.update_or_create(
        slug=slug,
        defaults={
            'name': service['name'],
            'price': service.get('raw_price', 0),
            'description': service.get('description', ''),
            'is_active': False,
            'is_deleted': True,
        }
    )

    messages.success(
        request,
        f'Đã xóa dịch vụ "{service["name"]}" thành công.'
    )

    return redirect('spa_admin_services')
@_owner
def analytics(request):
    day = _day(request)
    start = day - timedelta(days=29)
    qs = TrialBooking.objects.filter(register_date__gte=start, register_date__lte=day)
    active = qs.filter(status__in=ACTIVE, is_cancelled=False)
    ranking = list(active.values('service').annotate(n=Sum('party_size')).order_by('-n')[:10])
    hours = (active.filter(appointment_time__isnull=False).values('appointment_time')
             .annotate(n=Sum('party_size')))
    hour_dict = {r['appointment_time'].strftime('%H:%M'): r['n'] for r in hours}
    hrows = [{'hour': h, 'count': hour_dict.get(h, 0)} for h in HOURS]
    max_hour = max([r['count'] for r in hrows] or [1]) or 1
    for row in hrows:
        row['pct'] = round(100 * row['count'] / max_hour)
    max_rank = max([r['n'] for r in ranking] or [1]) or 1
    for row in ranking:
        row['pct'] = round(100 * row['n'] / max_rank)
    visit_total = SpaVisitRecord.objects.filter(booking__register_date__gte=start,
                        booking__register_date__lte=day, booking__status='completed').aggregate(n=Sum('actual_arrivals'))['n'] or 0
    return render(request, 'spa_admin/analytics.html', _base(request, 'analytics', 'Báo cáo & phân tích',
        day=day, period_start=start, total_bookings=qs.count(),
        expected=active.aggregate(n=Sum('party_size'))['n'] or 0,
        actual=visit_total, completed=qs.filter(status='completed').count(),
        cancelled=qs.filter(Q(status='cancelled') | Q(is_cancelled=True)).count(),
        no_show=qs.filter(status='no_show').count(), rank=ranking,
        hour_rows=hrows, hour_max=max([r['count'] for r in hrows] or [1]) or 1,
        rank_max=max([r['n'] for r in ranking] or [1]) or 1))


@_owner
def staff(request):
    staff_users = User.objects.filter(is_staff=True, is_superuser=False).order_by('username')
    return render(request, 'spa_admin/staff.html', _base(request, 'staff', 'Nhân viên & phân quyền',
                                                      staff_users=staff_users))


@_owner
def settings_page(request):
    config, _ = SpaSiteSettings.objects.get_or_create(pk=1)
    if request.method == 'POST':
        config.name = (request.POST.get('name') or 'Duyên Spa').strip()[:100]
        config.phone = (request.POST.get('phone') or '').strip()[:30]
        config.location = (request.POST.get('location') or '').strip()[:150]
        config.slogan = (request.POST.get('slogan') or '').strip()[:255]
        config.save()
        messages.success(request, 'Đã lưu thông tin spa.')
        return redirect('spa_admin_settings')
    return render(request, 'spa_admin/settings.html', _base(request, 'settings', 'Thông tin Duyên Spa', config=config))


@require_POST
@_owner
def create_booking(request):
    from .views import get_spa_services, spa_slot_remaining
    data = request.POST
    name = (data.get('full_name') or '').strip()[:100]
    phone = re.sub(r'[\s().-]', '', (data.get('phone') or '').strip())[:20]
    source = data.get('source', 'zalo')
    svc = get_spa_services().get(data.get('service', ''))
    try:
        day = date.fromisoformat(data.get('day', ''))
        hour = data.get('hour', '')
        size = int(data.get('party_size', '0'))
        if not svc or not name or not re.fullmatch(r'\+?[0-9]{8,15}', phone):
            raise ValueError('Vui lòng nhập đủ tên, số điện thoại và dịch vụ hợp lệ.')
        if source not in dict(SpaBookingSource.SOURCES):
            raise ValueError('Nguồn đặt lịch không hợp lệ.')
        if hour not in HOURS or size not in (1, 2, 3):
            raise ValueError('Giờ hoặc số khách không hợp lệ.')
        if day < now_local().date() or (day == now_local().date() and time.fromisoformat(hour) <= now_local().time()):
            raise ValueError('Chỉ được tạo lịch cho khung giờ chưa diễn ra.')
        with transaction.atomic():
            available = spa_slot_remaining(day).get(hour, 0)
            if available < size:
                raise ValueError(f'Khung {hour} chỉ còn {available} chỗ.')
            b = TrialBooking.objects.create(
                user=None, full_name=name, phone=phone, service=svc['name'], register_date=day,
                appointment_time=time.fromisoformat(hour), party_size=size, email='',
                notes=(data.get('notes') or '')[:1000], contact_consent=False,
                status='confirmed', is_cancelled=False,
            )
            SpaBookingSource.objects.create(booking=b, source=source)
            SpaBookingEvent.objects.create(booking=b, action='created', actor=request.user,
                                           note=f'Tạo thủ công: {source}')
        messages.success(request, f'Đã tạo lịch DS-{b.pk} và giữ {size} chỗ.')
        return redirect(reverse('spa_admin_bookings') + '?date=' + day.isoformat())
    except (ValueError, IntegrityError, OperationalError, TypeError) as exc:
        messages.error(request, str(exc) if isinstance(exc, ValueError) else 'Không thể lưu lịch. Khung giờ có thể vừa được đặt.')
        return redirect('spa_admin_bookings')


@require_POST
@_owner
def confirm_arrival(request, pk):
    try:
        actual = int(request.POST.get('actual_arrivals', 0))
    except (ValueError, TypeError):
        actual = 0
    with transaction.atomic():
        booking = get_object_or_404(TrialBooking.objects.select_for_update(), pk=pk)
        if booking.status not in ('pending', 'confirmed') or booking.is_cancelled:
            messages.error(request, 'Lịch không ở trạng thái có thể xác nhận.')
        elif booking.register_date > now_local().date():
            messages.error(request, 'Chưa đến ngày hẹn; không thể xác nhận khách đến.')
        elif not 1 <= actual <= booking.party_size:
            messages.error(request, f'Số người thực tế phải từ 1 đến {booking.party_size}.')
        else:
            SpaVisitRecord.objects.create(booking=booking, actual_arrivals=actual, recorded_by=request.user)
            booking.status = 'completed'
            booking.save(update_fields=['status'])
            SpaBookingEvent.objects.create(booking=booking, action='completed', actor=request.user,
                                           note=f'Đến thực tế: {actual}/{booking.party_size} người')
            messages.success(request, f'Đã xác nhận {actual} khách đến và hoàn thành lịch DS-{pk}.')
    return redirect(reverse('spa_admin_bookings') + '?date=' + booking.register_date.isoformat())


@require_POST
@_owner
def no_show(request, pk):
    with transaction.atomic():
        b = get_object_or_404(TrialBooking.objects.select_for_update(), pk=pk)
        current = now_local()
        if b.status not in ('pending', 'confirmed') or b.is_cancelled:
            messages.error(request, 'Lịch không ở trạng thái có thể đánh dấu không đến.')
        elif b.register_date > current.date() or (b.register_date == current.date()
            and (not b.appointment_time or b.appointment_time > current.time())):
            messages.error(request, 'Chưa đến giờ hẹn, không thể đánh dấu khách không đến.')
        else:
            b.status = 'no_show'
            b.save(update_fields=['status'])
            SpaBookingEvent.objects.create(booking=b, action='no_show', actor=request.user)
            messages.success(request, f'Đã ghi nhận lịch DS-{pk}: khách không đến.')
    return redirect(reverse('spa_admin_bookings') + '?date=' + b.register_date.isoformat())


@_viewer
def legacy_disabled(request, **kwargs):
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    if not request.user.is_superuser:
        raise PermissionDenied('Nhân viên chỉ được xem lịch.')
    messages.info(request, 'Chức năng cũ đã được thay bằng trang quản lý Duyên Spa.')
    return redirect('spa_admin_home')
