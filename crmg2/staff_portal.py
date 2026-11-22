"""Giao diện làm việc riêng của nhân viên Duyên Spa.

Chỉ nhân viên (is_staff=True, is_superuser=False) được xem và thực hiện
hai nghiệp vụ: xác nhận khách đến và ghi nhận khách không đến.
Giữ nguyên phần quản trị chủ spa.
"""
from datetime import date
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import TrialBooking
from .spa_admin import LABELS, TZ, _booking_row, _cap_table, now_local
from .spa_admin_models import SpaBookingEvent, SpaVisitRecord


def staff_only(view):
    @login_required(login_url='/dang-nhap/')
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff or request.user.is_superuser:
            raise PermissionDenied('Trang này chỉ dành cho nhân viên Duyên Spa.')
        timezone.activate(TZ)
        return view(request, *args, **kwargs)
    return wrapped


def _chosen_date(request):
    try:
        return date.fromisoformat(request.GET.get('date', ''))
    except (TypeError, ValueError):
        return now_local().date()


def _back_to_day(booking_date):
    return redirect(reverse('staff_appointments') + '?' + urlencode({'date': booking_date.isoformat()}))


@staff_only
def appointments(request):
    day = _chosen_date(request)
    search = (request.GET.get('q') or '').strip()[:100]
    status = request.GET.get('status') or 'all'

    qs = (TrialBooking.objects
          .filter(register_date=day)
          .select_related('spa_visit', 'spa_source')
          .order_by('appointment_time', 'pk'))

    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(service__icontains=search)
        )

    if status == 'cancelled':
        qs = qs.filter(Q(status='cancelled') | Q(is_cancelled=True))
    elif status in LABELS:
        qs = qs.filter(status=status, is_cancelled=False)

    today = now_local().date()
    rows = []
    for booking in qs:
        row = _booking_row(booking)
        # Chưa đến ngày hẹn thì không cho xác nhận khách đã đến.
        row['can_mark'] = bool(row['can_mark'] and booking.register_date <= today)
        rows.append(row)

    cap_rows, _ = _cap_table(day)
    return render(request, 'staff/appointments.html', {
        'section': 'appointments',
        'day': day,
        'search': search,
        'status': status,
        'status_labels': LABELS,
        'rows': rows,
        'cap_rows': cap_rows,
    })


@staff_only
@require_POST
def confirm_arrival(request, pk):
    try:
        actual = int(request.POST.get('actual_arrivals', ''))
    except (TypeError, ValueError):
        actual = 0

    try:
        with transaction.atomic():
            booking = get_object_or_404(
                TrialBooking.objects.select_for_update(), pk=pk
            )
            if booking.status not in ('pending', 'confirmed') or booking.is_cancelled:
                messages.error(request, 'Lịch này không còn ở trạng thái có thể xác nhận.')
            elif booking.register_date > now_local().date():
                messages.error(request, 'Chưa đến ngày hẹn; không thể xác nhận khách đến.')
            elif not 1 <= actual <= booking.party_size:
                messages.error(
                    request,
                    f'Số người thực tế phải từ 1 đến {booking.party_size}.'
                )
            elif SpaVisitRecord.objects.filter(booking=booking).exists():
                messages.error(request, 'Lịch này đã được xác nhận trước đó.')
            else:
                SpaVisitRecord.objects.create(
                    booking=booking,
                    actual_arrivals=actual,
                    recorded_by=request.user,
                )
                booking.status = 'completed'
                booking.save(update_fields=['status'])
                SpaBookingEvent.objects.create(
                    booking=booking,
                    action='completed',
                    actor=request.user,
                    note=f'Nhân viên xác nhận: {actual}/{booking.party_size} người đến',
                )
                messages.success(
                    request,
                    f'Đã xác nhận {actual} khách đến; lịch DS-{pk} đã hoàn thành.'
                )
    except (IntegrityError, OperationalError):
        messages.error(request, 'Không thể cập nhật lịch lúc này. Hãy kiểm tra và thử lại.')
        return redirect('staff_appointments')

    return _back_to_day(booking.register_date)


@staff_only
@require_POST
def no_show(request, pk):
    try:
        with transaction.atomic():
            booking = get_object_or_404(
                TrialBooking.objects.select_for_update(), pk=pk
            )
            current = now_local()
            if booking.status not in ('pending', 'confirmed') or booking.is_cancelled:
                messages.error(request, 'Lịch này không còn ở trạng thái có thể ghi nhận Không đến.')
            elif (booking.register_date > current.date()
                  or (booking.register_date == current.date()
                      and (booking.appointment_time is None
                           or booking.appointment_time > current.time()))):
                messages.error(request, 'Chưa đến giờ hẹn; không thể đánh dấu khách Không đến.')
            else:
                booking.status = 'no_show'
                booking.save(update_fields=['status'])
                SpaBookingEvent.objects.create(
                    booking=booking, action='no_show', actor=request.user,
                    note='Nhân viên ghi nhận khách không đến',
                )
                messages.success(request, f'Đã ghi nhận lịch DS-{pk}: khách không đến.')
    except (IntegrityError, OperationalError):
        messages.error(request, 'Không thể cập nhật lịch lúc này. Hãy kiểm tra và thử lại.')
        return redirect('staff_appointments')

    return _back_to_day(booking.register_date)


@staff_only
def confirmation_history(request):
    """Chỉ hiện thao tác xác nhận do chính tài khoản nhân viên thực hiện."""
    search = (request.GET.get('q') or '').strip()[:100]
    status = request.GET.get('status') or 'all'
    chosen_date = (request.GET.get('date') or '').strip()

    events = (SpaBookingEvent.objects
              .filter(actor=request.user, action__in=('completed', 'no_show'))
              .select_related('booking', 'booking__spa_visit')
              .order_by('-created_at', '-pk'))

    if chosen_date:
        try:
            day = date.fromisoformat(chosen_date)
        except ValueError:
            chosen_date = ''
        else:
            events = events.filter(created_at__date=day)

    if search:
        term = Q(booking__full_name__icontains=search) | Q(booking__phone__icontains=search) | Q(booking__service__icontains=search)
        if search.upper().startswith('DS-') and search[3:].isdigit():
            term |= Q(booking_id=int(search[3:]))
        events = events.filter(term)

    if status in ('completed', 'no_show'):
        events = events.filter(action=status)
    else:
        status = 'all'

    page_obj = Paginator(events, 50).get_page(request.GET.get('page'))
    records = []
    for event in page_obj.object_list:
        booking = event.booking
        visit = getattr(booking, 'spa_visit', None)
        actual = visit.actual_arrivals if event.action == 'completed' and visit else 0
        records.append({
            'booking_id': booking.pk,
            'name': booking.full_name,
            'phone': booking.phone,
            'service': booking.service,
            'day': booking.register_date,
            'hour': booking.appointment_time.strftime('%H:%M') if booking.appointment_time else '—',
            'status': event.action,
            'label': LABELS[event.action],
            'actual': actual,
            'confirmed_at': event.created_at,
        })

    return render(request, 'staff/history.html', {
        'section': 'history',
        'search': search,
        'status': status,
        'chosen_date': chosen_date,
        'records': records,
        'page_obj': page_obj,
    })
