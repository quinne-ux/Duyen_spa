# -*- coding: utf-8 -*-
"""Tich hop 2 trang nhan vien rieng cho Duyen Spa Admin V6.

Co sao luu, kiem tra canh bao truoc khi ghi. Khong thao tac SQLite.
Chay: py cai_dat_nhan_vien_duyen_spa.py (tai thu muc chua manage.py).
"""
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
FILES_TO_PATCH = ('crmg2/urls.py', 'crmg2/views.py', 'crmg2/spa_admin.py')
FILES_TO_ADD = (
    'crmg2/staff_portal.py',
    'crmg2/templates/staff/base.html',
    'crmg2/templates/staff/appointments.html',
    'crmg2/templates/staff/history.html',
    'static/css/staff-appointments.css',
    'static/js/staff-appointments.js',
)


def check(cond, explanation):
    if not cond:
        raise RuntimeError(explanation)


def modify_urls(src):
    check('from . import views' in src, 'crmg2/urls.py: khong tim thay from . import views.')
    check('urlpatterns = [' in src, 'crmg2/urls.py: khong tim thay urlpatterns.')
    check('staff_appointments' not in src and 'staff_confirmation_history' not in src,
          'Duong dan nhan vien da ton tai; khong tu ghi de.')
    src = src.replace('from . import views', 'from . import views\nfrom . import staff_portal', 1)
    insertion = '''urlpatterns = [
    # Duyen Spa: he thong nhan vien rieng, 2 trang
    path('nhan-vien/lich-hen/', staff_portal.appointments, name='staff_appointments'),
    path('nhan-vien/lich-su/', staff_portal.confirmation_history, name='staff_confirmation_history'),
    path('nhan-vien/lich-hen/<int:pk>/xac-nhan/', staff_portal.confirm_arrival, name='staff_arrival'),
    path('nhan-vien/lich-hen/<int:pk>/khong-den/', staff_portal.no_show, name='staff_no_show'),'''
    return src.replace('urlpatterns = [', insertion, 1)


def modify_views(src):
    previous = "return redirect('spa_admin_home' if user.is_superuser else 'spa_admin_bookings')"
    check(previous in src,
          'crmg2/views.py: khong tim thay dieu huong dang nhap cu cua nhan vien.\n'
          'Khong tu sua de tranh ghi de thay doi cua ban.')
    src = src.replace(previous,
                      "return redirect('spa_admin_home' if user.is_superuser else 'staff_appointments')", 1)
    marker = 'def spa_booking(request):'
    check(marker in src, 'crmg2/views.py: khong tim thay ham spa_booking.')
    i = src.index(marker)
    check('staff_appointments' not in src[i:i+450],
          'crmg2/views.py: spa_booking da co chan nhan vien; dung de tranh cai chong.')
    guard = '''def spa_booking(request):
    # Nhan vien chi duoc xu ly lich tren trang rieng, khong tao lich nhu khach.
    if request.user.is_authenticated and request.user.is_staff and not request.user.is_superuser:
        if request.method == 'POST':
            return JsonResponse({'success': False, 'error': 'Nhan vien khong duoc dat lich.'}, status=403)
        return redirect('staff_appointments')
'''
    return src.replace(marker, guard, 1)


def modify_admin(src):
    # Chuyen nhan vien ra khoi hai trang danh sach cua sidebar chu spa.
    fn_start = src.find('def _viewer(fn):')
    fn_end = src.find('\ndef _owner(fn):', fn_start)
    check(fn_start >= 0 and fn_end > fn_start,
          'crmg2/spa_admin.py: khong tim thay decorator _viewer cua Admin V6.')
    fn = src[fn_start:fn_end]
    needle = '        timezone.activate(TZ)'
    check(needle in fn, 'crmg2/spa_admin.py: _viewer khong dung timezone.activate(TZ) nhu ban V6.')
    check("return redirect('staff_appointments')" not in fn,
          'crmg2/spa_admin.py: da co chuyen huong nhan vien; khong cai chong.')
    fn = fn.replace(needle,
                    "        if not request.user.is_superuser:\n            return redirect('staff_appointments')\n" + needle, 1)
    return src[:fn_start] + fn + src[fn_end:]


MODIFIERS = {
    'crmg2/urls.py': modify_urls,
    'crmg2/views.py': modify_views,
    'crmg2/spa_admin.py': modify_admin,
}


def install():
    check((ROOT / 'manage.py').is_file(), 'Khong thay manage.py. Hay chay trong thu muc goc du an.')
    check((ROOT / 'crmg2/spa_admin_models.py').is_file(),
          'Chua co bo Admin V6. Can cai va migrate Dashboard chu spa truoc.')
    for name in FILES_TO_PATCH + FILES_TO_ADD:
        check((ROOT / name).is_file(), f'Thieu {name}. Hay giai nen va chep day du tep trong ZIP.')
    check('class SpaBookingEvent' in (ROOT / 'crmg2/spa_admin_models.py').read_text(encoding='utf-8')
          and 'class SpaVisitRecord' in (ROOT / 'crmg2/spa_admin_models.py').read_text(encoding='utf-8'),
          'Thieu bang ghi nhan khach den cua Admin V6.')

    # Buoc 1: kiem tra HET file truoc khi sua, de tranh sua nua chung.
    updated = {}
    for name, modifier in MODIFIERS.items():
        raw = (ROOT / name).read_text(encoding='utf-8')
        newer = modifier(raw)
        check(newer != raw, f'Khong co thay doi trong {name}; can kiem tra lai du an.')
        compile(newer, name, 'exec')
        updated[name] = newer
    compile((ROOT / 'crmg2/staff_portal.py').read_text(encoding='utf-8'),
            'crmg2/staff_portal.py', 'exec')

    # Buoc 2: sao luu cac file se sua.
    backup_dir = ROOT / ('_backup_nhan_vien_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    for name in FILES_TO_PATCH:
        dest = backup_dir / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)

    # Buoc 3: ghi code, neu loi tra lai ban sao luu.
    try:
        for name, content in updated.items():
            (ROOT / name).write_text(content, encoding='utf-8')
    except OSError:
        for name in FILES_TO_PATCH:
            shutil.copy2(backup_dir / name, ROOT / name)
        raise

    print('THANH CONG: Da cai 2 trang nhan vien Duyen Spa.')
    print('Trang 1: http://127.0.0.1:8000/nhan-vien/lich-hen/')
    print('Trang 2: http://127.0.0.1:8000/nhan-vien/lich-su/')
    print('Ban sao luu code goc:', backup_dir)
    print('KHONG thay doi database, khong can makemigrations hay migrate.')
    print('Tiep theo chay: py manage.py check')


if __name__ == '__main__':
    try:
        install()
    except (RuntimeError, OSError, SyntaxError) as exc:
        sys.exit('DUNG CAI DAT: ' + str(exc))
