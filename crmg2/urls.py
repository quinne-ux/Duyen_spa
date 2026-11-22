from django.urls import path, include
from . import views
from . import staff_portal

urlpatterns = [
    # Duyen Spa: he thong nhan vien rieng, 2 trang
    path('nhan-vien/lich-hen/', staff_portal.appointments, name='staff_appointments'),
    path('nhan-vien/lich-su/', staff_portal.confirmation_history, name='staff_confirmation_history'),
    path('nhan-vien/lich-hen/<int:pk>/xac-nhan/', staff_portal.confirm_arrival, name='staff_arrival'),
    path('nhan-vien/lich-hen/<int:pk>/khong-den/', staff_portal.no_show, name='staff_no_show'),
    path('quan-ly/', include('crmg2.spa_admin_urls')),
    path('', views.home_view, name='home'),

    # Auth URLs
    path('dang-ky/', views.register_view, name='register'),
    path('dang-nhap/', views.login_view, name='login'),
    path('dang-xuat/', views.logout_view, name='logout'),


    path('khieu-nai/', views.complaint_history_view, name='complaint_history'),
    path('khieu-nai/gui/', views.complaint_submission_view, name='complaint_form'),
    path('khieu-nai/<str:complaint_id>/', views.complaint_detail_view, name='complaint_detail'),
    path('khieu-nai/huy/<str:complaint_id>/', views.cancel_complaint_customer_view, name='cancel_complaint_customer'),
    path('quan-ly/khieu-nai/', views.complaint_manager_view, name='complaint_manager'),
    path('quan-ly/khieu-nai/xoa/<str:complaint_id>/', views.delete_complaint_view, name='delete_complaint'),
    path('quan-ly/khieu-nai/cap-nhat/<str:complaint_id>/', views.update_complaint_status_view, name='update_complaint_status'),
    path('goi-hoi-vien/', views.package_list_view, name='package_list'),
    path('goi-hoi-vien/dang-ky/<int:package_id>/', views.register_package_view, name='register_package'),
    path('quan-ly/goi-tap/', views.package_manager_view, name='package_manager_view'),
    path('quan-ly/goi-tap/cap-nhat/<int:package_id>/', views.update_package_view, name='update_package'),
    path('quan-ly/goi-tap/them/', views.add_package_view, name='add_package'),
    path('quan-ly/hoi-vien/', views.member_list_view, name='member_list_view'),
    path('quan-ly/hoi-vien/chi-tiet/<str:member_card_id>/', views.member_detail_view, name='member_detail_view'),
    path('dich-vu/', views.service_list_view, name='service_list'),
    path('dich-vu/<slug:slug>/', views.spa_service_detail, name='spa_service_detail'),
    path('quan-ly/dich-vu/', views.admin_service_item_list, name='admin_service_item_list'),
    path('quan-ly/dich-vu/them/', views.add_service_item, name='add_service_item'),
    path('quan-ly/dich-vu/sua/<int:pk>/', views.edit_service_item, name='edit_service_item'),
    path('quan-ly/dich-vu/xoa/<int:pk>/', views.delete_service_item, name='delete_service_item'),
    path('dat-lich/', views.spa_booking, name='trial_booking'),
path(
    'dat-lich/lich-hen/khach/<str:code>/',
    views.guest_booking_detail,
    name='guest_booking_detail'
),
    path('dat-lich/lich-hen/', views.booking_list, name='booking_list'),
    path('dat-lich/huy-lich/<int:pk>/', views.cancel_booking, name='cancel_booking'),
    path('quan-ly/dat-lich/', views.booking_manager_view, name='booking_manager_view'),
    path('quan-ly/dat-lich/xoa/<int:pk>/', views.delete_booking_view, name='delete_booking'),
    path('quan-ly/dat-lich/cap-nhat/<int:pk>/', views.update_booking_status, name='update_booking_status'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/<str:username>/', views.profile, name='profile'),
]