from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse  # Cần thiết cho get_absolute_url

# --- CÁC MODEL KHIẾU NẠI VÀ GÓI TẬP HIỆN TẠI (GIỮ NGUYÊN) ---

# Định nghĩa các lựa chọn cho Loại khiếu nại (UC-4.1)
COMPLAINT_TYPE_CHOICES = [
    ('FACILITY', 'Cơ sở vật chất'),
    ('SERVICE', 'Dịch vụ'),
    ('STAFF', 'Nhân viên'),
    ('OTHER', 'Khác'),
]

# Định nghĩa các lựa chọn cho Trạng thái xử lý (UC-4.4)
STATUS_CHOICES = [
    ('RECEIVED', 'Đã tiếp nhận'),  # Trạng thái ban đầu
    ('IN_PROGRESS', 'Đang xử lý'),
    ('RESOLVED', 'Đã xử lý'),
    ('CANCELLED', 'Đã hủy')
]

# Danh sách cơ sở (Tùy chỉnh nếu cần)
FACILITY_CHOICES = [
    ('HXH_DANANG', 'Hồ Xuân Hương, Đà Nẵng'),
    ('OTHER_HN', 'Cơ sở khác, Hà Nội'),
]


class Complaint(models.Model):
    # Khách hàng và thông tin cá nhân (Pre-Condition: Người dùng đã đăng nhập)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Người dùng"))
    name = models.CharField(max_length=100, verbose_name=_("Họ và Tên"))
    email = models.EmailField(verbose_name=_("Email"))
    phone_number = models.CharField(max_length=15, verbose_name=_("Số điện thoại"), blank=True, null=True)

    # Thông tin Khiếu nại (UC-4.1)
    complaint_id = models.CharField(max_length=10, unique=True, verbose_name=_("Mã khiếu nại"), blank=True)
    complaint_type = models.CharField(max_length=50, choices=COMPLAINT_TYPE_CHOICES, verbose_name=_("Loại khiếu nại"),
                                      default='OTHER')
    facility = models.CharField(max_length=100, choices=FACILITY_CHOICES, verbose_name=_("Cơ sở"), blank=True,
                                null=True)
    incident_date = models.DateField(verbose_name=_("Ngày xảy ra sự việc"), blank=True, null=True)
    title = models.CharField(max_length=255, verbose_name=_("Tiêu đề Khiếu nại"))
    content = models.TextField(verbose_name=_("Nội dung Khiếu nại"))

    # Xử lý nội bộ (UC-4.2, UC-4.3)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, verbose_name=_("Trạng thái"), default='RECEIVED')
    responsible_staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='complaints_handled', verbose_name=_("Người phụ trách"))

    # Thời gian
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Ngày gửi"))

    class Meta:
        verbose_name = _("Khiếu nại")
        verbose_name_plural = _("Khiếu nại")
        permissions = [
            ("can_manage_all_complaints", "Có thể quản lý và thống kê tất cả khiếu nại"),
            ("can_update_status", "Có thể cập nhật trạng thái xử lý khiếu nại"),
        ]

    def __str__(self):
        return f"{self.complaint_id} - {self.name} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Tự động tạo Mã khiếu nại (ví dụ: KN-001)
        if not self.complaint_id:
            last_complaint = Complaint.objects.all().order_by('id').last()
            if last_complaint and last_complaint.complaint_id and last_complaint.complaint_id.startswith('KN-'):
                try:
                    last_id = int(last_complaint.complaint_id.split('-')[1])
                except ValueError:
                    last_id = 0
                new_id = last_id + 1
            else:
                new_id = 1
            self.complaint_id = f'KN-{new_id:03d}'
        super().save(*args, **kwargs)


# Định nghĩa các lựa chọn cho loại gói tập (Membership Type)
# PACKAGE_TYPE_CHOICES = [
  #  ('GOLD', 'Gold'),
  #  ('VIP', 'VIP'),
  #  ('DIAMOND', 'Diamond'),
# ]


class Service(models.Model):
    """Model cho các gói tập (Membership Packages) - (Gói GOLD, VIP, DIAMOND)"""
    package_id = models.CharField(max_length=10, unique=True, verbose_name="Mã gói tập")
    name = models.CharField(max_length=100, verbose_name="Tên gói")
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Giá tiền (VND)")
    duration_months = models.IntegerField(verbose_name="Hạn sử dụng (Tháng)")
    description = models.TextField(verbose_name="Mô tả", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Gói Hội viên (Service)"
        verbose_name_plural = "Gói Hội viên (Service)"
        permissions = [
            ("can_manage_packages", "Có thể quản lý và cập nhật thông tin Gói Hội viên"),
        ]

    def __str__(self):
        return f"{self.name} ({self.duration_months} tháng)"

    def get_price_display(self):
        return f"{self.price:,.0f} VND/Tháng"


class MemberPackage(models.Model):
    """Model lưu trữ thông tin đăng ký gói của từng Hội viên"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Hội viên (User)")
    package = models.ForeignKey(Service, on_delete=models.PROTECT, verbose_name="Gói đã đăng ký")
    full_name = models.CharField(max_length=100, verbose_name="Họ và Tên")
    cccd = models.CharField(max_length=20, verbose_name="CCCD")
    phone_number = models.CharField(max_length=15, verbose_name="Số điện thoại")

    # Thông tin thẻ Hội viên
    membership_card_id = models.CharField(max_length=20, unique=True, verbose_name="Mã thẻ Hội viên", blank=True)

    # Thời gian
    registration_date = models.DateTimeField(auto_now_add=True, verbose_name="Ngày đăng ký")
    end_date = models.DateField(verbose_name="Ngày hết hạn")

    class Meta:
        verbose_name = "Đăng ký Gói Hội viên"
        verbose_name_plural = "Đăng ký Gói Hội viên"
        permissions = [
            ("can_view_member_list", "Có thể xem danh sách và chi tiết Hội viên"),
        ]

    def __str__(self):
        return f"{self.full_name} - {self.package.name}"

    def save(self, *args, **kwargs):
        # 1. Tự động tính ngày hết hạn
        if not self.registration_date:
            self.registration_date = timezone.now()

        self.end_date = self.registration_date.date() + timedelta(days=self.package.duration_months * 30)

        # 2. Tự động tạo Mã thẻ Hội viên
        if not self.membership_card_id:
            import uuid
            self.membership_card_id = f'MB-{uuid.uuid4().hex[:10].upper()}'

        super().save(*args, **kwargs)


# --- BỔ SUNG: CÁC MODEL DỊCH VỤ MỚI (ĐÃ ĐỔI TÊN) ---

class ServiceCategory(models.Model):
    """
    Model cho Danh mục dịch vụ (ví dụ: GYM, YOGA, DANCE)
    """
    name = models.CharField(max_length=100, verbose_name="Tên danh mục")
    slug = models.SlugField(max_length=50, unique=True, verbose_name="Slug (URL)")
    description = models.TextField(blank=True, null=True, verbose_name="Mô tả")
    image = models.ImageField(upload_to='service_categories/', blank=True, null=True, verbose_name="Ảnh")

    class Meta:
        verbose_name = "Danh mục Dịch vụ"
        verbose_name_plural = "Các Danh mục Dịch vụ"

    def __str__(self):
        return self.name


class ServiceItem(models.Model):
    """
    Model cho một Dịch vụ cụ thể (ví dụ: Lớp Yoga Phục Hồi)
    """

    # --- ĐÃ DI CHUYỂN VÀO ĐÂY ---
    STATUS_CHOICES = (
        ('draft', 'Bản nháp (Ẩn)'),
        ('published', 'Công khai (Hiện)'),
        ('archived', 'Lưu trữ'),
    )
    # --- KẾT THÚC THAY ĐỔI ---

    service_id = models.AutoField(primary_key=True, verbose_name="Mã Dịch vụ")
    name = models.CharField(max_length=100, unique=True, verbose_name="Tên Dịch vụ")
    slug = models.SlugField(max_length=50, unique=True, verbose_name="Slug (URL)")
    description = models.TextField(verbose_name="Mô tả chi tiết")
    image = models.ImageField(upload_to='service_items/', blank=True, null=True, verbose_name="Ảnh đại diện")

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,  # Dòng này giờ sẽ hoạt động
        default='draft',
        verbose_name='Trạng thái'
    )

    display_order = models.IntegerField(default=0, verbose_name="Thứ tự hiển thị")

    # (Tùy chọn) Liên kết với Danh mục
    # category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Dịch vụ"
        verbose_name_plural = "Các Dịch vụ"
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

# --- BỔ SUNG: MODEL ĐẶT LỊCH TẬP THỬ (TRIAL BOOKING) ---

class TrialBooking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Đang chờ'),
        ('confirmed', 'Đã xác nhận'),  # <-- Trạng thái mới
        ('completed', 'Đã hoàn thành'),  # <-- Trạng thái mới
        ('cancelled', 'Đã hủy'),
        ('no_show', 'Không đến'),
    )

    # Liên kết với User (Yêu cầu đăng nhập)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_("Người dùng"), null=True, blank=True)

    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    service = models.CharField(max_length=255) # Lưu dạng 'Gym, Yoga'
    register_date = models.DateField()
    appointment_time = models.TimeField(null=True, blank=True)
    party_size = models.PositiveSmallIntegerField(default=1)
    email = models.EmailField(blank=True, default='')
    notes = models.TextField(blank=True, default='')
    contact_consent = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    cancel_code = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        unique=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # --- THÊM ĐOẠN NÀY ---
    class Meta:
        verbose_name = _("Lịch hẹn")
        verbose_name_plural = _("Các lịch hẹn")

        permissions = [
            ("can_manage_bookings", "Có thể quản lý lịch tập thử"),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    party_size__gte=1,
                    party_size__lte=3
                ),
                name='valid_spa_party_size'
            ),
        ]

    # --- KẾT THÚC THÊM ---

    def __str__(self):
        return f"{self.full_name} - {self.phone}"

# --- TÍCH HỢP TỪ GLUCOYUH: MODEL QUẢN LÝ TÀI KHOẢN ---
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    GENDER_CHOICES = [
        ('Nam', 'Nam'),
        ('Nữ', 'Nữ'),
    ]
   # MEMBERSHIP_CHOICES = [
    #    ('', 'Không có'),
    #   ('Gold', 'Gold'),
    #   ('Diamond', 'Diamond'),
    #    ('VIP', 'VIP'),
   # ]
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    address = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=15)
    membership = models.CharField(
        max_length=100,  # Tăng độ dài lên cho chắc
        blank=True,
        null=True,
        default='Không có'  # Đặt mặc định
    )

    def __str__(self):
        return self.user.username
# --- KẾT THÚC TÍCH HỢP ---

# Duyên Spa: các model quản trị bổ sung
from .spa_admin_models import SpaVisitRecord, SpaBookingSource, SpaBookingEvent, SpaSlotRule, SpaDayClosure, SpaServiceOverride, SpaSiteSettings
