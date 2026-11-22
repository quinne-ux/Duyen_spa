"""Các bảng bổ sung cho quản trị Duyên Spa; không thay đổi dữ liệu đặt lịch cũ."""
from django.conf import settings
from django.db import models
from django.db.models import Q


class SpaVisitRecord(models.Model):
    booking = models.OneToOneField('crmg2.TrialBooking', related_name='spa_visit', on_delete=models.CASCADE)
    actual_arrivals = models.PositiveSmallIntegerField('Số khách thực tế')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lần xác nhận khách đến'
        constraints = [models.CheckConstraint(condition=Q(actual_arrivals__gte=1, actual_arrivals__lte=3), name='spa_visit_count_1_to_3')]


class SpaBookingSource(models.Model):
    SOURCES = [
        ('website', 'Website'), ('zalo', 'Facebook / Zalo'),
        ('phone', 'Điện thoại'), ('walkin', 'Trực tiếp'),
    ]
    booking = models.OneToOneField('crmg2.TrialBooking', on_delete=models.CASCADE, related_name='spa_source')
    source = models.CharField(max_length=15, choices=SOURCES, default='website')


class SpaBookingEvent(models.Model):
    EVENTS = [
        ('created', 'Tạo lịch thủ công'), ('completed', 'Xác nhận đến'),
        ('no_show', 'Không đến'),
    ]
    booking = models.ForeignKey('crmg2.TrialBooking', on_delete=models.CASCADE, related_name='spa_events')
    action = models.CharField(max_length=20, choices=EVENTS)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SpaSlotRule(models.Model):
    day = models.DateField()
    appointment_time = models.TimeField()
    # Giới hạn gốc của hệ thống hiện tại là 3. Không nâng >3 khi chưa sửa ràng buộc SQLite.
    capacity = models.PositiveSmallIntegerField(default=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['day', 'appointment_time'], name='spa_slot_unique_day_time'),
            models.CheckConstraint(condition=Q(capacity__gte=0, capacity__lte=3), name='spa_slot_cap_0_to_3'),
        ]


class SpaDayClosure(models.Model):
    day = models.DateField(unique=True)
    is_closed = models.BooleanField(default=True)


class SpaServiceOverride(models.Model):

    slug = models.SlugField(
        max_length=90,
        unique=True
    )

    name = models.CharField(
        max_length=100
    )

    price = models.PositiveIntegerField(
        default=0
    )

    description = models.TextField(
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    # Đánh dấu dịch vụ đã bị xóa
    is_deleted = models.BooleanField(
        default=False
    )

    def __str__(self):
        return self.name


class SpaSiteSettings(models.Model):
    name = models.CharField(max_length=100, default='Duyên Spa')
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=150, default='Đà Nẵng, Việt Nam')
    slogan = models.CharField(max_length=255, default='Chăm sóc làn da, nâng niu vẻ đẹp tự nhiên.')
