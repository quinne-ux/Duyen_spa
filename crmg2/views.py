import secrets
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Group, User
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
# Import Forms
from .forms import CustomUserCreationForm
from .forms import ServiceItemForm  # <-- FORM MỚI
from .forms import TrialBookingForm  # <-- THÊM MỚI
from .forms import ProfileForm
from .forms import PackageForm

# Import Models (Đã đổi tên để tránh xung đột)
from .models import (
    Complaint, COMPLAINT_TYPE_CHOICES, FACILITY_CHOICES, STATUS_CHOICES,
    Service, MemberPackage, # Service = Gói Hội viên
    ServiceCategory, ServiceItem, TrialBooking, Customer  # <-- MODELS MỚI
)


def home_view(request):
    """Render trang chủ sử dụng home.html."""
    return render(request, 'home.html', {'featured_services': list(get_spa_services().values())[:4]})


# --- CHỨC NĂNG XÁC THỰC NGƯỜI DÙNG ---
# (register_view, login_view, logout_view giữ nguyên)

def register_view(request):
    """Xử lý đăng ký người dùng mới. Sử dụng CustomForm."""
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                customer_group = Group.objects.get(name='Khách hàng')
                user.groups.add(customer_group)
            except Group.DoesNotExist:
                messages.warning(request, "Nhóm 'Khách hàng' chưa được thiết lập.")
            login(request, user)
            messages.success(request, 'Đăng ký thành công! Bạn đã được đăng nhập.')
            return redirect('home')
        else:
            messages.error(request, 'Đăng ký thất bại. Vui lòng kiểm tra lại thông tin.')
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})


def login_view(request):
    """Xử lý đăng nhập người dùng."""
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Chào mừng {username}! Bạn đã đăng nhập thành công.')
                # PHÂN LUỒNG: Nếu là Nhân viên, chuyển đến trang Quản lý
                if user.is_staff:
                    return redirect('spa_admin_home' if user.is_superuser else 'staff_appointments')  # Hoặc trang dashboard admin
                next_url = request.GET.get('next')
                return redirect(next_url or 'home')
            else:
                messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
        else:
            messages.error(request, 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    """Xử lý đăng xuất người dùng."""
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, 'Bạn đã đăng xuất thành công.')
    return redirect('home')


# --- CHỨC NĂNG KHIẾU NẠI (KHÁCH HÀNG & QUẢN LÝ) ---
# (Toàn bộ các hàm complaint_* và delete_complaint_view, update_complaint_status_view giữ nguyên)

@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.add_complaint', raise_exception=True)
def complaint_submission_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number')
        complaint_type = request.POST.get('complaint_type')
        facility = request.POST.get('facility')
        incident_date = request.POST.get('incident_date')
        title = request.POST.get('title')
        content = request.POST.get('content')
        if not all([name, email, title, content, complaint_type]):
            messages.error(request, "Vui lòng điền đầy đủ các trường bắt buộc.")
            context = {'name': name, 'email': email, 'phone_number': phone_number, 'complaint_type': complaint_type,
                       'facility': facility, 'incident_date': incident_date, 'title': title, 'content': content,
                       'COMPLAINT_TYPE_CHOICES': COMPLAINT_TYPE_CHOICES, 'FACILITY_CHOICES': FACILITY_CHOICES, }
            return render(request, 'complaint_form.html', context)
        try:
            Complaint.objects.create(user=request.user, name=name, email=email, phone_number=phone_number,
                                     complaint_type=complaint_type, facility=facility,
                                     incident_date=incident_date if incident_date else None, title=title,
                                     content=content, status='RECEIVED')
            messages.success(request, 'Cảm ơn bạn đã chia sẻ khiếu nại. Chúng tôi sẽ liên hệ với bạn sớm nhất có thể.')
            return redirect('complaint_history')
        except Exception as e:
            messages.error(request, f"Lỗi khi gửi khiếu nại: {e}")
            return render(request, 'complaint_form.html', context)
    context = {'COMPLAINT_TYPE_CHOICES': COMPLAINT_TYPE_CHOICES, 'FACILITY_CHOICES': FACILITY_CHOICES, }
    return render(request, 'complaint_form.html', context)


@login_required(login_url='/dang-nhap/')
def complaint_history_view(request):
    if request.user.has_perm('crmg2.can_manage_all_complaints'):
        return redirect('complaint_manager')
    complaints = Complaint.objects.filter(user=request.user).order_by('-submitted_at')
    context = {'complaints': complaints}
    return render(request, 'complaint_history.html', context)


@login_required(login_url='/dang-nhap/')
def complaint_detail_view(request, complaint_id):
    complaint = get_object_or_404(Complaint, complaint_id=complaint_id)
    is_manager = request.user.has_perm('crmg2.can_manage_all_complaints')
    if not is_manager and complaint.user != request.user:
        messages.error(request, "Bạn không có quyền xem chi tiết khiếu nại này.")
        return redirect('complaint_history')
    staff_users = []
    if is_manager:
        staff_users = User.objects.filter(is_staff=True).order_by('username')
    context = {'complaint': complaint, 'is_manager': is_manager, 'staff_users': staff_users,
               'STATUS_CHOICES': STATUS_CHOICES, }
    return render(request, 'complaint_detail.html', context)


@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.can_manage_all_complaints', raise_exception=True)
def complaint_manager_view(request):
    complaints = Complaint.objects.all().order_by('-submitted_at')
    complaint_type_filter = request.GET.get('complaint_type')
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search')
    if complaint_type_filter and complaint_type_filter != 'Tất cả':
        complaints = complaints.filter(complaint_type=complaint_type_filter)
    if status_filter and status_filter != 'Tất cả':
        complaints = complaints.filter(status=status_filter)
    if search_query:
        complaints = complaints.filter(complaint_id__icontains=search_query)
    context = {'complaints': complaints, 'COMPLAINT_TYPE_CHOICES': COMPLAINT_TYPE_CHOICES,
               'STATUS_CHOICES': STATUS_CHOICES, 'selected_type': complaint_type_filter or 'Tất cả',
               'selected_status': status_filter or 'Tất cả', 'search_query': search_query or '', }
    return render(request, 'complaint_manager.html', context)


@require_POST
@permission_required('crmg2.delete_complaint', login_url='/dang-nhap/')
def delete_complaint_view(request, complaint_id):
    # Hàm này giữ lại cho Admin nếu cần, nhưng UI sẽ ẩn đi
    get_object_or_404(Complaint, complaint_id=complaint_id).delete()
    messages.success(request, "Đã xóa khiếu nại.")
    return redirect('complaint_manager')

@require_POST
@login_required(login_url='/dang-nhap/')
def cancel_complaint_customer_view(request, complaint_id):
    complaint = get_object_or_404(Complaint, complaint_id=complaint_id, user=request.user)
    if complaint.status == 'RECEIVED':
        complaint.status = 'CANCELLED'
        complaint.save()
        messages.success(request, f"Đã hủy khiếu nại {complaint_id} thành công.")
    elif complaint.status == 'CANCELLED':
        messages.warning(request, "Khiếu nại này đã được hủy trước đó.")
    else:
        messages.error(request, "Không thể hủy khiếu nại đang xử lý hoặc đã xong.")
    return redirect('complaint_history')

@require_POST
@permission_required('crmg2.can_update_status', login_url='/dang-nhap/')
def update_complaint_status_view(request, complaint_id):
    try:
        complaint = Complaint.objects.get(complaint_id=complaint_id)
        new_status = request.POST.get('new_status')
        responsible_staff_id = request.POST.get('responsible_staff_id')
        status_keys = [choice[0] for choice in STATUS_CHOICES]
        if new_status and new_status in status_keys:
            complaint.status = new_status
        if responsible_staff_id:
            try:
                staff_user = User.objects.filter(pk=responsible_staff_id, is_staff=True).first()
                complaint.responsible_staff = staff_user
            except Exception:
                complaint.responsible_staff = None
        complaint.save()
        messages.success(request,
                         f"Đã cập nhật trạng thái khiếu nại {complaint_id} thành '{complaint.get_status_display()}' thành công.")
    except Complaint.DoesNotExist:
        messages.error(request, f"Lỗi: Không tìm thấy khiếu nại mã {complaint_id}.")
    except Exception as e:
        messages.error(request, f"Lỗi không xác định khi cập nhật trạng thái: {e}")
    return redirect('complaint_detail', complaint_id=complaint_id)


# --- CHỨC NĂNG GÓI HỘI VIÊN (Gói GOLD, VIP) ---
# (Toàn bộ các hàm package_* và member_* giữ nguyên)

def package_list_view(request):
    if request.user.is_authenticated and request.user.has_perm('crmg2.can_manage_packages'):
        return redirect('package_manager_view')
    packages = Service.objects.filter(is_active=True).order_by('price')
    context = {'packages': packages}
    return render(request, 'package_detail.html', context)


@login_required(login_url='/dang-nhap/')
def register_package_view(request, package_id):
    package = get_object_or_404(Service, pk=package_id)
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        cccd = request.POST.get('cccd')
        phone_number = request.POST.get('phone_number')
        if not all([full_name, cccd, phone_number]):
            messages.error(request, "Vui lòng điền đủ thông tin đăng ký.")
        else:
            try:
                MemberPackage.objects.create(user=request.user, package=package, full_name=full_name, cccd=cccd,
                                             phone_number=phone_number)
                messages.success(request, f"Đăng ký gói {package.name} thành công! Vui lòng chờ xác nhận.")
                return redirect('home')
            except Exception as e:
                messages.error(request, f"Lỗi đăng ký: {e}")
    context = {'package': package, 'user_name': request.user.get_full_name() or request.user.username, }
    return render(request, 'package_register.html', context)


@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.can_manage_packages', raise_exception=True)
def package_manager_view(request):
    packages = Service.objects.all().order_by('name')
    context = {'packages': packages}
    return render(request, 'package_manager.html', context)


@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.can_manage_packages', raise_exception=True)
def update_package_view(request, package_id):
    package = get_object_or_404(Service, pk=package_id)
    if request.method == 'POST':
        package.name = request.POST.get('name', package.name)
        package.price = request.POST.get('price', package.price)
        package.duration_months = request.POST.get('duration_months', package.duration_months)
        package.description = request.POST.get('description', package.description)
        try:
            package.save()
            messages.success(request, f"Cập nhật gói {package.name} thành công.")
            return redirect('package_manager_view')
        except Exception as e:
            messages.error(request, f"Lỗi cập nhật gói: {e}")
    context = {'package': package, }
    return render(request, 'package_update.html', context)


@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.can_view_member_list', raise_exception=True)
def member_list_view(request):
    members = MemberPackage.objects.all().order_by('-registration_date')
    search_query = request.GET.get('search')
    if search_query:
        members = members.filter(Q(full_name__icontains=search_query) | Q(cccd__icontains=search_query) | Q(
            package__name__icontains=search_query))
    context = {'members': members, 'search_query': search_query or ''}
    return render(request, 'member_manager.html', context)


@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.can_view_member_list', raise_exception=True)
def member_detail_view(request, member_card_id):
    member = get_object_or_404(MemberPackage, membership_card_id=member_card_id)
    context = {'member': member}
    return render(request, 'member_detail.html', context)


# --- (ĐOẠN CODE MỚI) CHỨC NĂNG DỊCH VỤ (Yoga, Dance, PT) ---
# (Đã điều chỉnh tên Model và Form)

def service_list_view(request):
    return render(request, 'service_list.html', {
        'spa_services': get_spa_services(),
    })


# --- Hàm Quản lý Danh sách Dịch vụ (Admin - Read & Search) ---
@login_required(login_url='/dang-nhap/')  # Đã có login_view
@permission_required('crmg2.change_serviceitem', raise_exception=True)  # Giả định quyền
def admin_service_item_list(request):
    """
    Quản lý danh sách các Mục Dịch vụ (ServiceItem)
    (Thay thế cho service_list)
    """
    service_items = ServiceItem.objects.all()
    query = request.GET.get('q')

    if query:
        service_items = service_items.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ).distinct()

    context = {
        'services': service_items,  # Vẫn dùng 'services' trong context để khớp template
        'query': query
    }
    return render(request, 'service_items.html', context)


# --- Hàm Thêm Dịch vụ (Admin - Create) ---
@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.add_serviceitem', raise_exception=True)
def add_service_item(request):
    """
    Thêm Mục Dịch vụ (ServiceItem) mới
    (Thay thế cho add_service)
    """
    if request.method == 'POST':
        form = ServiceItemForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save()
            messages.success(request, f"Đã thêm dịch vụ '{service.name}' thành công.")
            return redirect('admin_service_item_list')
        else:
            messages.error(request, "Lỗi khi thêm dịch vụ. Vui lòng kiểm tra lại.")
    else:
        form = ServiceItemForm()

    context = {
        'form': form,
        'action': 'Thêm mới'
    }
    return render(request, 'service_form.html', context)


# --- Hàm Sửa Dịch vụ (Admin - Update) ---
@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.change_serviceitem', raise_exception=True)
def edit_service_item(request, pk):
    """
    Cập nhật Mục Dịch vụ (ServiceItem)
    (Thay thế cho edit_service)
    """
    service_item = get_object_or_404(ServiceItem, pk=pk)

    if request.method == 'POST':
        form = ServiceItemForm(request.POST, request.FILES, instance=service_item)
        if form.is_valid():
            form.save()
            messages.success(request, f"Đã cập nhật dịch vụ '{service_item.name}'.")
            return redirect('admin_service_item_list')
    else:
        form = ServiceItemForm(instance=service_item)

    context = {
        'form': form,
        'service_item': service_item,
        'action': 'Cập nhật'
    }
    return render(request, 'service_form.html', context)


# --- Hàm Xóa Dịch vụ (Admin - Delete) ---
@require_POST  # Đảm bảo chỉ POST mới xóa được
@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.delete_serviceitem', raise_exception=True)
def delete_service_item(request, pk):
    """
    Xóa Mục Dịch vụ (ServiceItem)
    (Thay thế cho delete_service)
    """
    service_item = get_object_or_404(ServiceItem, pk=pk)

    if request.method == 'POST':
        service_item.delete()
        return redirect('admin_service_item_list')

    return redirect('admin_service_item_list')


# --- (BỔ SUNG) CHỨC NĂNG ĐẶT LỊCH TẬP THỬ ---
# (Code gốc từ pthaohoang247-a11y, điều chỉnh để yêu cầu đăng nhập)

@login_required(login_url='/dang-nhap/')
def trial_booking(request):
    """Trang đặt lịch tập thử (Yêu cầu đăng nhập)"""
    if request.method == 'POST':
        form = TrialBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = request.user  # Gán user đã đăng nhập
            booking.status = 'pending'  # Đảm bảo trạng thái ban đầu
            booking.is_cancelled = False
            booking.save()

            messages.success(request, "Đăng ký tập thử thành công! Vui lòng kiểm tra lịch hẹn của bạn.")
            return redirect('booking_list')  # Chuyển đến trang xem lịch hẹn
        else:
            messages.error(request, "Thông tin không hợp lệ, vui lòng kiểm tra lại.")
    else:
        # Lấy thông tin user để điền sẵn vào form
        form = TrialBookingForm(initial={
            'full_name': request.user.get_full_name() or request.user.username,
            # Bạn có thể lấy SĐT từ các model khác nếu muốn, tạm thời để trống
            'phone': ''
        })

    return render(request, 'trial_booking.html', {'form': form})


@login_required(login_url='/dang-nhap/')
@login_required(login_url='/dang-nhap/')
def booking_list(request):

    # Người có quyền quản lý được chuyển
    # sang trang xem toàn bộ lịch hẹn
    if request.user.has_perm('crmg2.can_manage_bookings'):
        return redirect('booking_manager_view')

    # Khách chỉ được xem lịch của tài khoản mình
    my_bookings = TrialBooking.objects.filter(
        user=request.user
    ).order_by(
        '-register_date',
        '-appointment_time',
        '-pk'
    )

    bookings = []

    for index, booking in enumerate(my_bookings, start=1):

        can_cancel = (
            booking.status in ('pending', 'confirmed')
            and not booking.is_cancelled
        )

        bookings.append({
            'index': index,
            'obj': booking,
            'can_cancel': can_cancel,
            'cancel_action': reverse(
                'cancel_booking',
                args=[booking.pk]
            ),
        })

    return render(
        request,
        'booking_list.html',
        {'bookings': bookings}
    )

@login_required(login_url='/dang-nhap/')
@require_POST  # Đảm bảo chỉ request POST mới chạy hàm này
@login_required(login_url='/dang-nhap/')
@require_POST
def cancel_booking(request, pk):

    # Chỉ cho phép hủy lịch thuộc tài khoản đang đăng nhập
    booking = get_object_or_404(
        TrialBooking,
        pk=pk,
        user=request.user
    )

    if (
        booking.status in ('pending', 'confirmed')
        and not booking.is_cancelled
    ):

        booking.status = 'cancelled'
        booking.is_cancelled = True
        booking.cancelled_at = timezone.now()

        booking.save(
            update_fields=[
                'status',
                'is_cancelled',
                'cancelled_at'
            ]
        )

        messages.success(
            request,
            'Đã hủy lịch hẹn thành công. '
            'Số chỗ đã được hoàn lại.'
        )

    elif booking.status == 'cancelled' or booking.is_cancelled:

        messages.info(
            request,
            'Lịch hẹn này đã được hủy trước đó.'
        )

    else:

        messages.warning(
            request,
            'Lịch đã hoàn thành nên không thể hủy.'
        )

    return redirect('booking_list')
# --- (BỔ SUNG) CHỨC NĂNG QUẢN LÝ LỊCH TẬP THỬ (CHO NHÂN VIÊN) ---

@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.can_manage_bookings', raise_exception=True)
def booking_manager_view(request):
    """
    Trang quản lý danh sách lịch tập thử cho nhân viên.
    (Giống complaint_manager_view)
    """
    bookings = TrialBooking.objects.all().order_by('-register_date')

    # Lấy các lựa chọn trạng thái từ Model
    STATUS_CHOICES = TrialBooking.STATUS_CHOICES

    # Lọc và Tìm kiếm
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search')

    if status_filter and status_filter != 'Tất cả':
        bookings = bookings.filter(status=status_filter)

    if search_query:
        bookings = bookings.filter(
            Q(full_name__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    context = {
        'bookings': bookings,
        'STATUS_CHOICES': STATUS_CHOICES,
        'selected_status': status_filter or 'Tất cả',
        'search_query': search_query or '',
    }
    return render(request, 'booking_manager.html', context)


# --- (BỔ SUNG) HÀM XỬ LÝ XÓA LỊCH HẸN (CHO NHÂN VIÊN) ---

@require_POST  # Chỉ cho phép truy cập bằng method POST
@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.can_manage_bookings', raise_exception=True)
def delete_booking_view(request, pk):
    """
    Xử lý logic xóa TrialBooking.
    """
    try:
        # Tìm lịch hẹn theo Primary Key (pk)
        booking = get_object_or_404(TrialBooking, pk=pk)

        # Lưu lại thông tin để hiển thị message
        booking_info = f"{booking.full_name} (ngày {booking.register_date.strftime('%d/%m/%Y')})"

        # Xóa
        booking.delete()

        messages.success(request, f"Đã xóa thành công lịch hẹn của {booking_info}.")

    except Exception as e:
        messages.error(request, f"Lỗi khi xóa lịch hẹn: {e}")

    # Quay lại trang quản lý
    return redirect('booking_manager_view')

# --- (BỔ SUNG) HÀM CẬP NHẬT TRẠNG THÁI LỊCH HẸN (CHO NHÂN VIÊN) ---

@require_POST
@login_required(login_url='/dang-nhap/')
@permission_required('crmg2.can_manage_bookings', raise_exception=True)
def update_booking_status(request, pk):
    """
    Xử lý cập nhật trạng thái mới cho TrialBooking.
    """
    try:
        booking = get_object_or_404(TrialBooking, pk=pk)
        new_status = request.POST.get('new_status')

        # Lấy danh sách key của các lựa chọn hợp lệ
        valid_statuses = [choice[0] for choice in TrialBooking.STATUS_CHOICES]

        if new_status and new_status in valid_statuses:
            booking.status = new_status

            # Nếu nhân viên chọn "Đã hủy", cập nhật luôn 2 trường kia
            if new_status == 'cancelled':
                booking.is_cancelled = True
                booking.cancelled_at = timezone.now()
            # Nếu nhân viên chọn trạng thái khác "Đã hủy" (vd: Đang chờ)
            elif new_status != 'cancelled':
                booking.is_cancelled = False
                booking.cancelled_at = None

            booking.save()
            messages.success(request, f"Cập nhật trạng thái cho {booking.full_name} thành công.")
        else:
            messages.error(request, "Trạng thái mới không hợp lệ.")

    except Exception as e:
        messages.error(request, f"Lỗi khi cập nhật: {e}")

    return redirect('booking_manager_view')

# --- TÍCH HỢP TỪ GLUCOYUH: VIEWS QUẢN LÝ TÀI KHOẢN ---
@login_required
@login_required
def profile(request, username):
    # Bảo mật: Nếu URL khác username thật -> Redirect về đúng URL của họ
    if username != request.user.username:
        return redirect('profile', username=request.user.username)

    if request.user.is_staff:
        messages.error(request, "Trang này chỉ dành cho khách hàng.")
        return redirect('home')

    profile, _ = Customer.objects.get_or_create(user=request.user,
                                                defaults={'email': request.user.email, 'name': request.user.username,
                                                          'phone': '', 'gender': 'Nam'})

    # Sync tên gói (lấy trực tiếp tên, ko capitalize)
    try:
        active = MemberPackage.objects.filter(user=request.user).order_by('-registration_date').first()
        pkg_name = active.package.name if active else 'Không có'
        if profile.membership != pkg_name:
            profile.membership = pkg_name
            profile.save()
    except Exception:
        pass

    return render(request, 'accounts/profile.html', {'profile': profile})


@login_required
def edit_profile(request):
    if request.user.is_staff:
        messages.error(request, "Trang này chỉ dành cho khách hàng.")
        return redirect('home')

    profile = get_object_or_404(Customer, user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Cập nhật thành công!")
            # Redirect về URL có username
            return redirect('profile', username=request.user.username)
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'accounts/edit-profile.html', {'form': form, 'profile': profile})
# --- KẾT THÚC TÍCH HỢP ---

# --- THÊM GÓI ---
@login_required(login_url='/dang-nhap/')
def add_package_view(request):
    # Chỉ Admin mới được vào
    if not request.user.is_superuser:
        messages.error(request, "Bạn không có quyền thực hiện chức năng này.")
        return redirect('package_manager_view')

    if request.method == 'POST':
        form = PackageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Thêm gói hội viên mới thành công!")
            return redirect('package_manager_view')
        else:
            messages.error(request, "Lỗi khi thêm gói. Vui lòng kiểm tra lại.")
    else:
        form = PackageForm()

    context = {
        'form': form,
        'action': 'Thêm Mới',
        'title_text': 'Thêm Gói Hội Viên Mới'
    }
    return render(request, 'package_form.html', context)
# ==========================================
# CHI TIẾT DỊCH VỤ DUYÊN SPA
# ==========================================

from django.http import Http404


SPA_SERVICES = {

    # DỊCH VỤ 1: CHĂM SÓC DA CƠ BẢN

    'cham-soc-da-co-ban': {

        'name': 'Chăm sóc da cơ bản',

        'category': 'CHĂM SÓC DA',

        'image': 'images/duyen-basic.jpg',

        'price': '350.000đ',

        'description': (
            'Dành thời gian yêu thương làn da với '
            'liệu trình làm sạch, cấp ẩm và chăm sóc '
            'da nhẹ nhàng tại Duyên Spa.'
        ),

        'benefits': [
            'Làm sạch bề mặt da',
            'Bổ sung độ ẩm cho da',
            'Mang lại cảm giác thư giãn',
        ],

        'steps': [
            'Tư vấn tình trạng da',
            'Làm sạch da',
            'Chăm sóc và cấp ẩm',
            'Hướng dẫn chăm sóc tại nhà',
        ],

        'suitable': (
            'Khách hàng có nhu cầu chăm sóc da '
            'định kỳ, da khô hoặc thiếu độ ẩm.'
        ),

        'faq': (
            'Liệu trình sẽ được tư vấn dựa trên '
            'tình trạng thực tế của làn da.'
        ),

    },


    # DỊCH VỤ 2: CHĂM SÓC DA MỤN

    'cham-soc-da-mun': {

        'name': 'Chăm sóc da mụn',

        'category': 'ĐIỀU TRỊ DA',

        'image': 'images/duyen-acne.jpg',

        'price': '550.000đ',

        'description': (
            'Giải pháp chăm sóc làn da có mụn, '
            'tập trung vào làm sạch và lựa chọn '
            'phương pháp phù hợp với tình trạng da.'
        ),

        'benefits': [
            'Hỗ trợ làm sạch da',
            'Hỗ trợ kiểm soát dầu thừa',
            'Chăm sóc và bảo vệ hàng rào da',
        ],

        'steps': [
            'Tư vấn và đánh giá tình trạng mụn',
            'Làm sạch làn da',
            'Thực hiện chăm sóc phù hợp',
            'Hướng dẫn chăm sóc da tại nhà',
        ],

        'suitable': (
            'Khách hàng có da dầu, da dễ nổi mụn '
            'hoặc cần tư vấn chăm sóc da mụn.'
        ),

        'faq': (
            'Tùy tình trạng mụn, khách hàng có thể '
            'được khuyến nghị thăm khám bác sĩ da liễu '
            'trước khi thực hiện liệu trình.'
        ),

    },


    # DỊCH VỤ 3: PEEL DA

    'peel-da': {

        'name': 'Peel da',

        'category': 'TRẺ HÓA & PHỤC HỒI',

        'image': 'images/duyen-peel.jpg',

        'price': '650.000đ',

        'description': (
            'Chăm sóc và làm mới làn da với '
            'phương pháp peel được lựa chọn '
            'dựa trên tình trạng da của khách hàng.'
        ),

        'benefits': [
            'Hỗ trợ làm mới bề mặt da',
            'Hỗ trợ cải thiện sắc da',
            'Chăm sóc da theo nhu cầu cá nhân',
        ],

        'steps': [
            'Đánh giá tình trạng và độ nhạy cảm của da',
            'Chuẩn bị làn da',
            'Thực hiện liệu trình phù hợp nếu đủ điều kiện',
            'Hướng dẫn phục hồi và chống nắng',
        ],

        'suitable': (
            'Khách hàng có nhu cầu cải thiện bề mặt '
            'da hoặc sắc da không đồng đều. '
            'Cần được đánh giá trước khi thực hiện.'
        ),

        'faq': (
            'Không phải làn da nào cũng phù hợp để peel. '
            'Khách hàng cần được tư vấn về chống chỉ định '
            'và cách chăm sóc sau liệu trình.'
        ),

    },


    # DỊCH VỤ 4: PHUN XĂM

    'phun-xam-tham-my': {

        'name': 'Phun xăm thẩm mỹ',

        'category': 'PHUN XĂM',

        'image': 'images/duyen-brows.jpg',

        'price': '1.500.000đ',

        'description': (
            'Tôn lên vẻ đẹp tự nhiên với dịch vụ '
            'phun xăm thẩm mỹ dành cho môi và chân mày, '
            'hướng đến đường nét hài hòa với khuôn mặt.'
        ),

        'benefits': [
            'Tôn lên đường nét khuôn mặt',
            'Tư vấn dáng và màu sắc phù hợp',
            'Tiết kiệm thời gian trang điểm',
        ],

        'steps': [
            'Tư vấn nhu cầu khách hàng',
            'Lựa chọn dáng và màu sắc',
            'Thực hiện dịch vụ nếu đủ điều kiện',
            'Hướng dẫn chăm sóc sau phun xăm',
        ],

        'suitable': (
            'Khách hàng có nhu cầu cải thiện '
            'đường nét chân mày hoặc màu môi.'
        ),

        'faq': (
            'Dáng chân mày và màu môi sẽ được '
            'trao đổi với khách hàng trước khi thực hiện.'
        ),

    },


    # DỊCH VỤ 5: TÀN NHANG

    'cham-soc-da-tan-nhang': {

        'name': 'Chăm sóc da tàn nhang',

        'category': 'ĐIỀU TRỊ DA',

        'image': 'images/duyen-freckles.jpg',

        'price': 'Liên hệ tư vấn',

        'description': (
            'Tư vấn chăm sóc làn da có tàn nhang '
            'và sắc tố không đồng đều, hướng đến '
            'một chu trình chăm sóc phù hợp.'
        ),

        'benefits': [
            'Đánh giá nhu cầu chăm sóc sắc tố',
            'Tư vấn phương pháp phù hợp',
            'Hướng dẫn bảo vệ làn da',
        ],

        'steps': [
            'Tư vấn tình trạng da',
            'Đánh giá vùng da cần chăm sóc',
            'Đề xuất phương pháp phù hợp',
            'Hướng dẫn chăm sóc và chống nắng',
        ],

        'suitable': (
            'Khách hàng có tàn nhang hoặc '
            'quan tâm đến việc chăm sóc da không đều màu.'
        ),

        'faq': (
            'Chi phí và phương pháp phụ thuộc vào '
            'tình trạng da thực tế. Một số trường hợp '
            'cần được bác sĩ da liễu đánh giá.'
        ),

    },

}




# DUYÊN SPA - DỊCH VỤ CÓ THỂ CHỈNH TỪ DASHBOARD
def get_spa_services(include_inactive=False):
    from copy import deepcopy
    from .spa_admin_models import SpaServiceOverride
    data = deepcopy(SPA_SERVICES)
    category_tags = {
        'cham-soc-da-co-ban': 'care recovery',
        'cham-soc-da-mun': 'treatment',
        'peel-da': 'treatment recovery',
        'phun-xam-tham-my': 'makeup',
        'cham-soc-da-tan-nhang': 'treatment',
    }
    for slug, item in data.items():
        price_string = str(item.get('price', '0'))
        item['raw_price'] = int(''.join(c for c in price_string if c.isdigit()) or '0')
        item['is_active'] = True
        item['slug'] = slug
        item['filter_categories'] = category_tags.get(slug, 'care')
    for override in SpaServiceOverride.objects.all():

        slug = override.slug

        # Loại bỏ dịch vụ đã xóa khỏi danh sách
        if override.is_deleted:
            data.pop(slug, None)
            continue
        if slug not in data:
            data[slug] = {
                'category': 'CHĂM SÓC DA',
                'image': 'images/duyen-basic.jpg',
                'benefits': ['Được tư vấn theo nhu cầu'],
                'steps': ['Tư vấn', 'Thực hiện dịch vụ', 'Hướng dẫn chăm sóc'],
                'suitable': 'Khách hàng được tư vấn trước khi sử dụng.',
                'faq': 'Vui lòng liên hệ spa để được hướng dẫn cụ thể.',
            }
        obj = data[slug]
        obj.update(name=override.name, price=f"{override.price:,}".replace(',', '.') + 'đ',
                   raw_price=override.price, description=override.description,
                   is_active=override.is_active, slug=slug,
                   filter_categories=category_tags.get(slug, 'care'))
    if not include_inactive:
        data = {k: v for k, v in data.items() if v.get('is_active', True)}
    return data

# HÀM HIỂN THỊ CHI TIẾT DỊCH VỤ

def spa_service_detail(request, slug):

    service = get_spa_services().get(slug)

    if service is None:
        raise Http404("Không tìm thấy dịch vụ")

    related_services = [

        (key, item)

        for key, item in get_spa_services().items()

        if key != slug

    ]

    context = {
        'service': service,
        'related_services': related_services,
        'service_slug': slug,
    }

    return render(
        request,
        'service_detail.html',
        context
    )
# ==========================================
# HỆ THỐNG ĐẶT LỊCH DUYÊN SPA
# ==========================================

from datetime import date, time
from zoneinfo import ZoneInfo
from django import forms as spa_forms
from django.http import JsonResponse
from django.db import IntegrityError, OperationalError
import re


# CÁC KHUNG GIỜ SPA NHẬN LỊCH

SPA_BOOKING_HOURS = [
    '09:00',
    '10:00',
    '11:00',
    '13:00',
    '14:00',
    '15:00',
    '16:00',
    '17:00',
]


# MÚI GIỜ VIỆT NAM

def spa_now():

    return timezone.now().astimezone(
        ZoneInfo('Asia/Ho_Chi_Minh')
    )


# KIỂM TRA CÁC KHUNG GIỜ CÒN TRỐNG
from django.db.models import Sum

# SỨC CHỨA TỐI ĐA MỖI KHUNG GIỜ

SPA_SLOT_CAPACITY = 3


# TÍNH SỐ CHỖ CÒN TRỐNG

def spa_slot_remaining(selected_date):
    """Lấy chỗ trống thực tế, kể cả các điều chỉnh của chủ spa."""
    from .spa_admin_models import SpaSlotRule, SpaDayClosure
    now = spa_now()
    hours = SPA_BOOKING_HOURS
    capacities = {h: SPA_SLOT_CAPACITY for h in hours}
    if selected_date < now.date():
        return {h: 0 for h in hours}
    if SpaDayClosure.objects.filter(day=selected_date, is_closed=True).exists():
        return {h: 0 for h in hours}
    for rule in SpaSlotRule.objects.filter(day=selected_date):
        h = rule.appointment_time.strftime('%H:%M')
        if h in capacities:
            capacities[h] = rule.capacity
    booked = TrialBooking.objects.filter(
        register_date=selected_date,
        status__in=['pending', 'confirmed', 'completed'],
        is_cancelled=False, appointment_time__isnull=False,
    ).values('appointment_time').annotate(total_people=Sum('party_size'))
    remaining = dict(capacities)
    for r in booked:
        hour = r['appointment_time'].strftime('%H:%M')
        if hour in remaining:
            remaining[hour] = max(0, capacities[hour] - (r['total_people'] or 0))
    for hour in hours:
        if selected_date == now.date() and time.fromisoformat(hour) <= now.time():
            remaining[hour] = 0
    return remaining



# DANH SÁCH GIỜ CÒN NHẬN LỊCH

def spa_available_hours(selected_date):

    remaining = spa_slot_remaining(selected_date)

    return [
        hour
        for hour, seats in remaining.items()
        if seats > 0
    ]



# KIỂM TRA DỮ LIỆU KHÁCH HÀNG NHẬP

class SpaBookingForm(spa_forms.Form):
    party_size = spa_forms.IntegerField(
        min_value=1,
        max_value=SPA_SLOT_CAPACITY,
        error_messages={
            'required': 'Vui lòng chọn số người.',
            'min_value': 'Số người tối thiểu là 1.',
            'max_value': 'Mỗi khung giờ tối đa 3 người.',
            'invalid': 'Số lượng người không hợp lệ.'
        }
    )

    service = spa_forms.ChoiceField(
        choices=[],
        error_messages={
            'required': 'Vui lòng chọn dịch vụ.',
            'invalid_choice': 'Dịch vụ không hợp lệ.'
        }
    )

    register_date = spa_forms.DateField(
        input_formats=['%Y-%m-%d'],
        error_messages={
            'required': 'Vui lòng chọn ngày hẹn.',
            'invalid': 'Ngày hẹn không hợp lệ.'
        }
    )

    appointment_time = spa_forms.ChoiceField(
        choices=[
            (hour, hour)
            for hour in SPA_BOOKING_HOURS
        ],
        error_messages={
            'required': 'Vui lòng chọn khung giờ.',
            'invalid_choice': 'Khung giờ không hợp lệ.'
        }
    )

    full_name = spa_forms.CharField(
        max_length=100,
        error_messages={
            'required': 'Vui lòng nhập họ và tên.'
        }
    )

    phone = spa_forms.RegexField(
        regex=r'^\+?[0-9]{8,15}\Z',
        max_length=20,
        error_messages={
            'required': 'Vui lòng nhập số điện thoại.',
            'invalid': 'Số điện thoại không hợp lệ.'
        }
    )

    email = spa_forms.EmailField(
        error_messages={
            'required': 'Vui lòng nhập email.',
            'invalid': 'Email không hợp lệ.'
        }
    )

    notes = spa_forms.CharField(
        required=False,
        max_length=1000
    )

    contact_consent = spa_forms.BooleanField(
        required=True,
        error_messages={
            'required': 'Bạn cần đồng ý để spa liên hệ.'
        }
    )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields['service'].choices = [
            (slug, item['name'])
            for slug, item in get_spa_services().items()
        ]


# HÀM HIỂN THỊ VÀ XỬ LÝ ĐẶT LỊCH

def spa_booking(request):
    # Nhan vien chi duoc xu ly lich tren trang rieng, khong tao lich nhu khach.
    if request.user.is_authenticated and request.user.is_staff and not request.user.is_superuser:
        if request.method == 'POST':
            return JsonResponse({'success': False, 'error': 'Nhan vien khong duoc dat lich.'}, status=403)
        return redirect('staff_appointments')


    # --------------------------------
    # LẤY DANH SÁCH GIỜ CÒN TRỐNG
    # --------------------------------

    if (
        request.method == 'GET'
        and request.GET.get('action') == 'slots'
    ):

        try:

            selected_date = date.fromisoformat(
                request.GET.get('date', '')
            )

        except ValueError:

            return JsonResponse({
                'success': False,
                'error': 'Ngày không hợp lệ.'
            }, status=400)
        remaining = spa_slot_remaining(selected_date)

        return JsonResponse({

            'success': True,

            'capacity': SPA_SLOT_CAPACITY,

            'remaining': remaining,

            'available': [
                hour
                for hour, seats in remaining.items()
                if seats > 0
            ]

        })


    # --------------------------------
    # LƯU YÊU CẦU ĐẶT LỊCH
    # --------------------------------

    if request.method == 'POST':

        data = request.POST.copy()

        data['phone'] = re.sub(
            r'[\s().-]',
            '',
            data.get('phone', '')
        )

        form = SpaBookingForm(data)

        if not form.is_valid():

            errors = [
                str(error)
                for field_errors in form.errors.values()
                for error in field_errors
            ]

            return JsonResponse({
                'success': False,
                'error': ' '.join(errors)
            }, status=400)

        cleaned = form.cleaned_data

        selected_service = get_spa_services()[
            cleaned['service']
        ]

        selected_date = cleaned['register_date']

        selected_hour = cleaned['appointment_time']

        party_size = cleaned['party_size']

        remaining_seats = spa_slot_remaining(
            selected_date
        ).get(selected_hour, 0)

        if party_size > remaining_seats:
            return JsonResponse({

                'success': False,

                'error': (
                    f'Khung giờ này chỉ còn '
                    f'{remaining_seats} chỗ. '
                    'Vui lòng giảm số người '
                    'hoặc chọn khung giờ khác.'
                )

            }, status=409)

        # LƯU THÔNG TIN VÀO DATABASE
        guest_code = (
            secrets.token_hex(16)
            if not request.user.is_authenticated
            else None
        )
        try:

            booking = TrialBooking.objects.create( cancel_code=guest_code,

                user=(
                    request.user
                    if request.user.is_authenticated
                    else None
                ),

                full_name=cleaned['full_name'],

                phone=cleaned['phone'],

                email=cleaned['email'],

                service=selected_service['name'],

                register_date=selected_date,

                appointment_time=time.fromisoformat(
                    selected_hour
                ),
                party_size=party_size,

                notes=cleaned['notes'],

                contact_consent=True,

                status='confirmed',

                is_cancelled=False

            )

        except IntegrityError:

            return JsonResponse({
                'is_guest': booking.user_id is None,

                'manage_url': (
                    reverse(
                        'guest_booking_detail',
                        args=[booking.cancel_code]
                    )
                    if booking.user_id is None
                    else reverse('booking_list')
                ),
                'success': False,
                'error': (
                    'Không thể lưu lịch này. '
                    'Khung giờ có thể vừa được đặt.'
                )
            }, status=409)

        except OperationalError:

            return JsonResponse({
                'success': False,
                'error': (
                    'Hệ thống đang bận. '
                    'Vui lòng thử lại.'
                )
            }, status=503)


        # CHỈ BÁO THÀNH CÔNG KHI ĐÃ LƯU

        return JsonResponse({

            'success': True,

            'booking_id': booking.pk,
            'party_size': booking.party_size,

            'service': booking.service,

            'date': booking.register_date.isoformat(),

            'time': booking.appointment_time.strftime(
                '%H:%M'
            ),

        }, status=201)


    # --------------------------------
    # HIỂN THỊ GIAO DIỆN ĐẶT LỊCH
    # --------------------------------

    selected_slug = request.GET.get('service', '')

    if selected_slug not in get_spa_services():

        selected_slug = next(iter(get_spa_services()), "")

    context = {

        'spa_services': get_spa_services(),

        'selected_slug': selected_slug,

        'hours': SPA_BOOKING_HOURS,

        'today': spa_now().date().isoformat(),

        'initial_name': (
            request.user.get_full_name()
            or request.user.username
        ) if request.user.is_authenticated else '',

        'initial_email': (
            request.user.email
            if request.user.is_authenticated
            else ''
        ),

    }

    return render(
        request,
        'trial_booking.html',
        context
    )

@csrf_protect
def guest_booking_detail(request, code):

    booking = get_object_or_404(
        TrialBooking,
        cancel_code=code,
        user__isnull=True
    )

    if request.method == 'POST':

        if (
            booking.status in ('pending', 'confirmed')
            and not booking.is_cancelled
        ):

            booking.status = 'cancelled'
            booking.is_cancelled = True
            booking.cancelled_at = timezone.now()

            booking.save(
                update_fields=[
                    'status',
                    'is_cancelled',
                    'cancelled_at'
                ]
            )

            messages.success(
                request,
                'Đã hủy lịch hẹn thành công.'
            )

        else:

            messages.info(
                request,
                'Lịch này đã hủy hoặc đã hoàn thành.'
            )

        return redirect(
            'guest_booking_detail',
            code=code
        )

    if request.method != 'GET':

        from django.http import HttpResponseNotAllowed

        return HttpResponseNotAllowed(['GET', 'POST'])

    row = {
        'index': 1,
        'obj': booking,
        'can_cancel': (
            booking.status in ('pending', 'confirmed')
            and not booking.is_cancelled
        ),
        'cancel_action': reverse(
            'guest_booking_detail',
            args=[code]
        ),
    }

    response = render(
        request,
        'booking_list.html',
        {
            'bookings': [row],
            'guest_link': True,
        }
    )

    response['Cache-Control'] = 'private, no-store'
    response['Referrer-Policy'] = 'no-referrer'

    return response