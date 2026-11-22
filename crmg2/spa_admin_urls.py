from django.urls import path
from . import spa_admin

urlpatterns = [
    path('', spa_admin.dashboard, name='spa_admin_home'),
    path('dat-lich/', spa_admin.bookings, name='spa_admin_bookings'),
    path('lich-su/', spa_admin.history, name='spa_admin_history'),
    path('khung-gio/', spa_admin.slots, name='spa_admin_slots'),
    path('dich-vu/', spa_admin.services, name='spa_admin_services'),
    path('bao-cao/', spa_admin.analytics, name='spa_admin_analytics'),
    path('nhan-vien/', spa_admin.staff, name='spa_admin_staff'),
    path('cai-dat/', spa_admin.settings_page, name='spa_admin_settings'),
    path('dat-lich/them/', spa_admin.create_booking, name='spa_admin_booking_create'),
    path('dat-lich/<int:pk>/xac-nhan/', spa_admin.confirm_arrival, name='spa_admin_arrival'),
    path('dat-lich/<int:pk>/khong-den/', spa_admin.no_show, name='spa_admin_no_show'),
    path('dich-vu/luu/', spa_admin.save_service, name='spa_admin_service_save'),
path('dich-vu/xoa/',spa_admin.delete_service,name='spa_admin_service_delete'),
    # Chặn đường dẫn chỉnh/xóa GymX cũ để không bỏ qua phân quyền và quy trình mới.
    path('dat-lich/xoa/<int:pk>/', spa_admin.legacy_disabled, name='spa_admin_legacy_delete'),
    path('dat-lich/cap-nhat/<int:pk>/', spa_admin.legacy_disabled, name='spa_admin_legacy_update'),
    path('dich-vu/them/', spa_admin.legacy_disabled, name='spa_admin_legacy_add_service'),
    path('dich-vu/sua/<int:pk>/', spa_admin.legacy_disabled, name='spa_admin_legacy_edit_service'),
    path('dich-vu/xoa/<int:pk>/', spa_admin.legacy_disabled, name='spa_admin_legacy_delete_service'),
    path('<path:legacy>/', spa_admin.legacy_disabled, name='spa_admin_legacy_general'),
]
