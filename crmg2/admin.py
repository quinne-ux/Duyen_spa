from django.contrib import admin
from django.contrib.auth.models import User
from .models import Complaint, Service, MemberPackage, ServiceCategory, ServiceItem, TrialBooking


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('complaint_id', 'name', 'email', 'complaint_type', 'status', 'submitted_at', 'responsible_staff')
    list_filter = ('complaint_type', 'status', 'facility', 'submitted_at', 'responsible_staff')
    search_fields = ('complaint_id', 'name', 'email', 'content')
    date_hierarchy = 'submitted_at'
    readonly_fields = ('complaint_id', 'submitted_at', 'user')

    fieldsets = (
        ('Thông tin Khách hàng', {
            'fields': ('user', 'name', 'email', 'phone_number'),
        }),
        ('Chi tiết Khiếu nại', {
            'fields': ('complaint_id', 'complaint_type', 'facility', 'incident_date', 'title', 'content',
                       'submitted_at'),
        }),
        ('Thông tin Xử lý (UC-4.4)', {
            'fields': ('status', 'responsible_staff'),
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "responsible_staff":
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        if not request.user.has_perm('crmg2.can_manage_all_complaints'):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not request.user.has_perm('crmg2.can_manage_all_complaints'):
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('package_id', 'name', 'price', 'duration_months', 'is_active')
    list_filter = ('is_active', 'name')
    search_fields = ('package_id', 'name')


@admin.register(MemberPackage)
class MemberPackageAdmin(admin.ModelAdmin):
    list_display = ('membership_card_id', 'full_name', 'package', 'phone_number', 'registration_date', 'end_date')
    list_filter = ('package', 'end_date')
    search_fields = ('membership_card_id', 'full_name', 'cccd', 'phone_number')
    date_hierarchy = 'registration_date'
    readonly_fields = ('end_date', 'registration_date')

    fieldsets = (
        (None, {'fields': ('user', 'package', 'full_name', 'cccd', 'phone_number')}),
        ('Thông tin Thẻ & Thời hạn', {'fields': ('membership_card_id', 'registration_date', 'end_date')}),
    )

@admin.register(ServiceCategory) # Sửa ServiceType -> ServiceCategory
class ServiceCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug', 'description')
    search_fields = ('name', 'description')

# --- ĐĂNG KÝ MODEL MỚI: SERVICE ITEM (ĐÃ SỬA TÊN) ---
@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('service_id', 'name', 'slug', 'status', 'display_order')
    list_filter = ('status',)
    search_fields = ('name', 'description')
    list_editable = ('display_order', 'status')
    ordering = ('display_order', 'service_id')


# --- BỔ SUNG: ĐĂNG KÝ TRIAL BOOKING VỚI ADMIN ---
@admin.register(TrialBooking)
class TrialBookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'phone', 'service', 'register_date', 'status', 'is_cancelled')
    list_filter = ('status', 'is_cancelled', 'register_date')
    search_fields = ('full_name', 'phone', 'user__username')
    readonly_fields = ('created_at', 'cancelled_at')

    # Sắp xếp các trường trong trang chi tiết admin
    fieldsets = (
        ('Thông tin Đặt lịch', {
            'fields': (
                'user',
                'full_name',
                'phone',
                'email',
                'service',
                'register_date',
                'appointment_time',
                'notes',
                'contact_consent'
            )
        }),
        ('Trạng thái (Nội bộ)', {
            'fields': ('status', 'is_cancelled', 'cancelled_at', 'cancel_code', 'created_at')
        }),
    )