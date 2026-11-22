# -*- coding: utf-8 -*-
"""Cài giao diện quản trị Duyên Spa V6 vào dự án Django hiện có.
Chạy tại thư mục chứa manage.py: py cai_dat_admin_duyen_spa.py
Không chạy migrate, không đụng tới db.sqlite3 hoặc lịch hẹn đã lưu.
"""
from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
HERE = ROOT
REQUIRED = [ROOT/'manage.py', ROOT/'crmg2/views.py', ROOT/'crmg2/models.py',
            ROOT/'crmg2/urls.py', ROOT/'templates/base.html', ROOT/'gymx2/settings.py',
            ROOT/'crmg2/context_processors.py', ROOT/'crmg2/templates/service_list.html',
            ROOT/'crmg2/templates/home.html']
missing = [p for p in REQUIRED if not p.is_file()]
if missing:
    raise SystemExit('THIẾU FILE DỰ ÁN:\n' + '\n'.join(str(x) for x in missing))

if not re.search(r'^\s*appointment_time\s*=\s*models\.TimeField', (ROOT/'crmg2/models.py').read_text(encoding='utf-8'), re.M):
    raise SystemExit('DỪNG: model TrialBooking chưa có appointment_time. Cần khôi phục trường này trước khi cài quản trị (tránh lỗi đặt lịch cũ).')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def update_text(path, replacer):
    original = path.read_text(encoding='utf-8')
    changed = replacer(original)
    require(changed != original, f'Không tìm thấy vị trí thay đổi trong {path}. Dự án có thể đã thay đổi; chưa ghi file nào.')
    return changed


def patch_models(s):
    if 'from .spa_admin_models import SpaVisitRecord' not in s:
        s += '\n\n# Duyên Spa: các model quản trị bổ sung\nfrom .spa_admin_models import SpaVisitRecord, SpaBookingSource, SpaBookingEvent, SpaSlotRule, SpaDayClosure, SpaServiceOverride, SpaSiteSettings\n'
    # Thêm giá trị no_show vào STATUS_CHOICES nhưng không đụng các trạng thái đang lưu.
    if "('no_show'," not in s:
        needle = "('cancelled', 'Đã hủy'),"
        require(needle in s, 'Không tìm thấy STATUS_CHOICES của TrialBooking trong models.py.')
        s = s.replace(needle, needle + "\n        ('no_show', 'Không đến'),", 1)
    return s


def patch_urls(s):
    if "include('crmg2.spa_admin_urls')" in s:
        raise RuntimeError('Các URL quản trị đã được cài từ trước.')
    require('urlpatterns = [' in s, 'urls.py không có urlpatterns chuẩn.')
    if 'from django.urls import path, include' not in s:
        s = s.replace('from django.urls import path', 'from django.urls import path, include', 1)
    s = s.replace('urlpatterns = [', "urlpatterns = [\n    path('quan-ly/', include('crmg2.spa_admin_urls')),", 1)
    return s

SERVICE_GETTER = '''\n\n# DUYÊN SPA - DỊCH VỤ CÓ THỂ CHỈNH TỪ DASHBOARD\ndef get_spa_services(include_inactive=False):
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
\n'''

SLOT_METHOD = '''def spa_slot_remaining(selected_date):
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
\n\n'''


def patch_views(s):
    require('SPA_SERVICES = {' in s and 'def spa_booking(' in s, 'views.py không giống phiên bản Duyên Spa hiện tại.')
    require('appointment_time' in s, 'views.py thiếu appointment_time. Hãy sửa lỗi schema đặt lịch trước.')
    if 'def get_spa_services(' in s:
        raise RuntimeError('views.py đã có get_spa_services; không tự động ghi đè để tránh mất code.')
    marker = '# HÀM HIỂN THỊ CHI TIẾT DỊCH VỤ'
    require(marker in s, 'Không tìm được vùng chèn hàm dịch vụ.')
    s = s.replace(marker, SERVICE_GETTER + marker, 1)
    start = s.find('def service_list_view(request):')
    end = s.find('\n# --- Hàm Quản lý Danh sách Dịch vụ', start)
    require(start != -1 and end != -1, 'Không tìm thấy hàm service_list_view theo bố cục cũ.')
    s = s[:start] + '''def service_list_view(request):
    return render(request, 'service_list.html', {
        'spa_services': get_spa_services(),
    })

''' + s[end:]
    # Không đụng vào các trường, popup, form hay JS của trang đặt lịch.
    # Thẻ dịch vụ nổi bật trên trang chủ cũng dùng đúng nguồn dữ liệu dịch vụ.
    old_home = "return render(request, 'home.html')"
    require(old_home in s, 'Không tìm được home_view() để kết nối dịch vụ nổi bật.')
    s = s.replace(old_home, "return render(request, 'home.html', {'featured_services': list(get_spa_services().values())[:4]})", 1)
    s = s.replace('service = SPA_SERVICES.get(slug)', 'service = get_spa_services().get(slug)')
    s = s.replace('for key, item in SPA_SERVICES.items()', 'for key, item in get_spa_services().items()')
    s = s.replace('for slug, item in SPA_SERVICES.items()', 'for slug, item in get_spa_services().items()')
    s = s.replace('selected_service = SPA_SERVICES[', 'selected_service = get_spa_services()[')
    s = s.replace('if selected_slug not in SPA_SERVICES:', 'if selected_slug not in get_spa_services():')
    s = s.replace('selected_slug = next(iter(SPA_SERVICES))', 'selected_slug = next(iter(get_spa_services()), "")')
    s = s.replace("'spa_services': SPA_SERVICES,", "'spa_services': get_spa_services(),")
    # Thay đúng hàm tính chỗ, giữ các phần code khác.
    r = re.compile(r'def spa_slot_remaining\(selected_date\):.*?(?=\n# DANH SÁCH GIỜ CÒN NHẬN LỊCH)', re.S)
    require(bool(r.search(s)), 'Không tìm được ranh giới hàm spa_slot_remaining.')
    s = r.sub(SLOT_METHOD, s, count=1)
    # Trang đăng nhập của chủ/nhân viên mở thẳng giao diện mới.
    needle = "return redirect('admin_service_item_list')"
    if needle in s:
        s = s.replace(needle, "return redirect('spa_admin_home' if user.is_superuser else 'spa_admin_bookings')", 1)
    # Chỉ cập nhật status trong hàm spa_booking, nếu vẫn là pending.
    start = s.find('def spa_booking(request):')
    require(start != -1, 'Không thấy spa_booking.')
    before, rest = s[:start], s[start:]
    rest = rest.replace("status='pending',", "status='confirmed',", 1)
    s = before + rest
    return s


def patch_service_template(s):
    require('spa-service-grid' in s and 'spa-price-note' in s, 'service_list.html khác cấu trúc tham chiếu.')
    # Chỉ thay vùng các card, giữ nguyên banner, bộ lọc, CSS và JS.
    start = s.find('<div class="spa-service-grid">')
    end = s.find('<p class="spa-price-note">', start)
    require(start != -1 and end != -1 and start < end, 'Không tìm được vùng card dịch vụ.')
    new_cards = '''<div class="spa-service-grid">
            {% for slug, item in spa_services.items %}
            <article class="spa-service-card" data-category="{{ item.filter_categories }}">
                <div class="spa-card-image"><img src="{% static item.image %}" alt="{{ item.name }}"></div>
                <div class="spa-card-content">
                    <h2><a href="{% url 'spa_service_detail' slug %}" class="stretched-link text-reset text-decoration-none">{{ item.name }}</a></h2>
                    <p>{{ item.description }}</p>
                    <div class="spa-card-bottom">
                        <span class="spa-card-price"><i class="fa fa-tag"></i> {{ item.price }}</span>
                        <a class="spa-booking-btn" href="{% url 'trial_booking' %}?service={{ slug }}">Đặt lịch <i class="fa fa-long-arrow-right"></i></a>
                    </div>
                </div>
            </article>
            {% empty %}<p>Hiện chưa có dịch vụ đang mở.</p>{% endfor %}
        </div>

        '''
    return s[:start] + new_cards + s[end:]



def patch_home_template(s):
    marker = '<div class="ds-service-grid">'
    start = s.find(marker)
    end = s.find('\n    </div>\n</section>', start)
    require(start >= 0 and end > start, 'Không tìm được vùng thẻ dịch vụ nổi bật trong home.html.')
    repl = '''<div class="ds-service-grid">
            {% for item in featured_services %}
            <article class="ds-service-card">
                <div class="ds-photo ds-service-photo">
                    <img src="{% static item.image %}" alt="{{ item.name }}" loading="lazy" onerror="this.hidden=true">
                    <span class="ds-photo-placeholder"><i class="fa fa-leaf" aria-hidden="true"></i></span>
                </div>
                <div class="ds-card-copy">
                    <h3>{{ item.name }}</h3>
                    <p>{{ item.description|truncatechars:110 }}</p>
                    <a href="{% url 'spa_service_detail' item.slug %}">Xem dịch vụ <i class="fa fa-long-arrow-right" aria-hidden="true"></i></a>
                </div>
            </article>
            {% endfor %}
        </div>'''
    return s[:start] + repl + s[end:]


def patch_base(s):
    require('ds-header' in s and 'ds-footer' in s, 'base.html chưa phải bản Duyên Spa.')
    # Menu chủ/nhân viên thay cho menu quản lý GymX.
    first = s.find('{% if user.is_authenticated and user.is_staff %}')
    require(first >= 0, 'Không tìm thấy nhánh menu quản lý trong base.html.')
    stop = s.find('{% else %}', first)
    require(stop >= 0, 'Không tìm thấy đoạn kết menu quản lý.')
    admin_menu = '''{% if user.is_authenticated and user.is_staff %}
                    {% if user.is_superuser %}
                    <li class="nav-item"><a class="nav-link" href="{% url 'spa_admin_home' %}">Bảng quản trị</a></li>
                    {% else %}
                    <li class="nav-item"><a class="nav-link" href="{% url 'spa_admin_bookings' %}">Xem lịch hẹn</a></li>
                    {% endif %}
                '''
    s = s[:first] + admin_menu + s[stop:]
    # Thay nút quản trị ở header, không thay nút dành cho khách.
    old = '''{% if user.is_staff %}<a class="ds-btn ds-btn-primary" href="{% url 'booking_manager_view' %}"><i class="fa fa-calendar-check-o" aria-hidden="true"></i> Quản lý lịch</a>'''
    new = '''{% if user.is_staff %}<a class="ds-btn ds-btn-primary" href="{% if user.is_superuser %}{% url 'spa_admin_home' %}{% else %}{% url 'spa_admin_bookings' %}{% endif %}"><i class="fa fa-calendar-check-o" aria-hidden="true"></i> {% if user.is_superuser %}Bảng quản trị{% else %}Xem lịch{% endif %}</a>'''
    require(old in s, 'Không tìm thấy nút Quản lý lịch trong header để thay.')
    s = s.replace(old, new, 1)
    # Footer nhận cấu hình Spa; nếu thay nội dung website vẫn giữ phong cách.
    s = s.replace('>Duyên Spa</a><p>Chăm sóc làn da, nâng niu vẻ đẹp tự nhiên.</p>',
                  '>{{ spa_public_config.name|default:"Duyên Spa" }}</a><p>{{ spa_public_config.slogan|default:"Chăm sóc làn da, nâng niu vẻ đẹp tự nhiên." }}</p>', 1)
    s = s.replace('Đà Nẵng, Việt Nam</p></div>', '{{ spa_public_config.location|default:"Đà Nẵng, Việt Nam" }}</p></div>', 1)
    s = s.replace('{{ spa_public_config.location|default:"Đà Nẵng, Việt Nam" }}</p></div>',
                  '{{ spa_public_config.location|default:"Đà Nẵng, Việt Nam" }}</p>{% if spa_public_config.phone %}<p><i class="fa fa-phone" aria-hidden="true"></i> {{ spa_public_config.phone }}</p>{% endif %}</div>', 1)
    # Đảm bảo menu dưới được xóa, nếu file người dùng có chưa xóa.
    pattern = re.compile(r'<nav class="ds-bottom-nav".*?</nav>\s*', re.S)
    s = pattern.sub('', s, count=1)
    # Popup thông báo cũ nếu vẫn còn.
    s = re.sub(r'<div class="modal fade" id="dsNotification".*?(?=<script src=)', '', s, count=1, flags=re.S)
    # Không đụng thẻ script Bootstrap/jQuery.
    return s


def patch_context(s):
    if 'def spa_public_settings_processor(' in s:
        raise RuntimeError('Context processor SPA đã tồn tại.')
    return s + '''\n\n# Cấu hình hiển thị cho giao diện khách hàng.
def spa_public_settings_processor(request):
    from django.db.utils import OperationalError, ProgrammingError
    from .spa_admin_models import SpaSiteSettings
    try:
        config = SpaSiteSettings.objects.filter(pk=1).first()
    except (OperationalError, ProgrammingError):
        config = None
    return {'spa_public_config': config}
'''


def patch_settings(s):
    needle = "'crmg2.context_processors.service_categories_processor',"
    require(needle in s, 'Không tìm thấy context processor gốc trong settings.py.')
    return s.replace(needle, needle + "\n                'crmg2.context_processors.spa_public_settings_processor',", 1)

# Tạo các bản vá trong bộ nhớ TRƯỚC khi thay bất kỳ file nào.
modifications = {}
patches = {
    ROOT/'crmg2/models.py': patch_models,
    ROOT/'crmg2/urls.py': patch_urls,
    ROOT/'crmg2/views.py': patch_views,
    ROOT/'crmg2/templates/service_list.html': patch_service_template,
    ROOT/'crmg2/templates/home.html': patch_home_template,
    ROOT/'templates/base.html': patch_base,
    ROOT/'crmg2/context_processors.py': patch_context,
    ROOT/'gymx2/settings.py': patch_settings,
}
try:
    for path, fn in patches.items():
        modifications[path] = update_text(path, fn)
except RuntimeError as exc:
    raise SystemExit(f'DỪNG CÀI ĐẶT: {exc}\nChưa ghi bất kỳ file gốc nào.')

# Sao lưu trước khi ghi và chỉ thay code, không sao chép / ghi đè database.
backup_dir = ROOT/('_backup_duyen_admin_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
backup_dir.mkdir()
for path in modifications:
    dst = backup_dir/path.relative_to(ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)
for path, content in modifications.items():
    path.write_text(content, encoding='utf-8')

print('ĐÃ CÀI CẤU TRÚC VÀ GIAO DIỆN QUẢN TRỊ DUYÊN SPA.')
print('Đã sao lưu 8 file gốc vào:', backup_dir.name)
print('Không thay đổi db.sqlite3. Tiếp tục chạy:')
print('  py manage.py makemigrations crmg2')
print('  py manage.py migrate')
print('  py manage.py check')
print('  py manage.py runserver')
print('Sau đó mở http://127.0.0.1:8000/quan-ly/')
