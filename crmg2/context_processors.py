# gymx2/crmg2/context_processors.py

from .models import ServiceCategory, TrialBooking

def service_categories_processor(request):

    context = {
        'service_categories': ServiceCategory.objects.all(),
        'user_has_bookings': False  # Mặc định là False
    }

    if request.user.is_authenticated:
        # Kiểm tra xem user này có bất kỳ lịch hẹn nào (chưa bị hủy) không
        has_bookings = TrialBooking.objects.filter(
            user=request.user,
            status='pending'  # Chỉ tính các lịch "đang chờ"
        ).exists()

        context['user_has_bookings'] = has_bookings

    return context

# Cấu hình hiển thị cho giao diện khách hàng.
def spa_public_settings_processor(request):
    from django.db.utils import OperationalError, ProgrammingError
    from .spa_admin_models import SpaSiteSettings
    try:
        config = SpaSiteSettings.objects.filter(pk=1).first()
    except (OperationalError, ProgrammingError):
        config = None
    return {'spa_public_config': config}
