
from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parent

LOGIN = ROOT / "crmg2/templates/login.html"
REGISTER = ROOT / "crmg2/templates/register.html"
CSS = ROOT / "static/css/duyen-auth.css"

if not (ROOT / "manage.py").exists():
    raise SystemExit(
        "Hãy đặt file này trong thư mục chứa manage.py"
    )

if not LOGIN.exists() or not REGISTER.exists():
    raise SystemExit(
        "Không tìm thấy login.html hoặc register.html"
    )


# ======================================
# GIAO DIỆN ĐĂNG NHẬP & ĐĂNG KÝ
# ======================================

page = r'''
{% extends 'base.html' %}
{% load static %}

{% block title %}__TITLE__ | Duyên Spa{% endblock title %}
{% block body_class %}ds-inner-page ds-auth-page{% endblock body_class %}
{% block legacy_css %}{% endblock legacy_css %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/duyen-auth.css' %}">
{% endblock extra_css %}

{% block content %}

<section class="spa-auth">
  <div class="spa-auth-card">

    <div class="spa-auth-form">

      <p class="spa-auth-kicker">
        DUYÊN SPA · CHĂM SÓC DA & LÀM ĐẸP
      </p>

      <h1>__TITLE__</h1>
      <p class="spa-auth-subtitle">__SUBTITLE__</p>

      <form action="__ACTION__" method="post">
        {% csrf_token %}

        {% if form.non_field_errors %}
        <div class="spa-auth-alert" role="alert">
          {{ form.non_field_errors }}
        </div>
        {% endif %}

        {% for field in form %}

          {% if field.is_hidden %}
            {{ field }}
          {% else %}

          <div class="spa-auth-field">

            <label for="{{ field.id_for_label }}">
              {% if field.name == 'username' %}
                Tên đăng nhập
              {% elif field.name == 'password' or field.name == 'password1' %}
                Mật khẩu
              {% elif field.name == 'password2' %}
                Nhập lại mật khẩu
              {% elif field.name == 'first_name' %}
                Họ
              {% elif field.name == 'last_name' %}
                Tên
              {% else %}
                {{ field.label }}
              {% endif %}
            </label>

            {{ field }}

            {% if field.errors %}
            <div class="spa-auth-error" role="alert">
              {{ field.errors }}
            </div>
            {% endif %}

            {% if field.help_text %}
            <div class="spa-auth-help">
              {{ field.help_text }}
            </div>
            {% endif %}

          </div>

          {% endif %}
        {% endfor %}

        <button class="spa-auth-submit" type="submit">
          __BUTTON__
          <i class="fa fa-arrow-right" aria-hidden="true"></i>
        </button>

      </form>

      <p class="spa-auth-switch">__SWITCH__</p>

    </div>

    <aside class="spa-auth-photo"
      style="background-image:
        linear-gradient(
          0deg,
          rgba(14,50,31,.68),
          rgba(14,50,31,0) 65%
        ),
        url('{% static 'images/duyen-banner.jpg' %}');">

      <div class="spa-auth-photo-content">
        <span>DUYÊN SPA</span>

        <h2>
          Chăm sóc làn da,<br>
          nâng niu vẻ đẹp tự nhiên.
        </h2>

        <p>
          Không gian thư giãn dành riêng cho bạn.
        </p>
      </div>

    </aside>

  </div>
</section>

{% endblock content %}
'''


pages = {

    LOGIN: (
        page
        .replace("__TITLE__", "Đăng nhập")
        .replace(
            "__SUBTITLE__",
            "Chào mừng bạn trở lại Duyên Spa. "
            "Vui lòng đăng nhập để tiếp tục."
        )
        .replace(
            "__ACTION__",
            "{% url 'login' %}"
            "{% if request.GET.next %}"
            "?next={{ request.GET.next|urlencode }}"
            "{% endif %}"
        )
        .replace("__BUTTON__", "Đăng nhập")
        .replace(
            "__SWITCH__",
            "Chưa có tài khoản? "
            "<a href=\"{% url 'register' %}\">"
            "Đăng ký ngay</a>"
        )
    ),

    REGISTER: (
        page
        .replace("__TITLE__", "Đăng ký")
        .replace(
            "__SUBTITLE__",
            "Tạo tài khoản để đặt lịch và "
            "theo dõi lịch hẹn của bạn."
        )
        .replace(
            "__ACTION__",
            "{% url 'register' %}"
        )
        .replace("__BUTTON__", "Tạo tài khoản")
        .replace(
            "__SWITCH__",
            "Đã có tài khoản? "
            "<a href=\"{% url 'login' %}\">"
            "Đăng nhập</a>"
        )
    )
}


# ======================================
# CSS PHONG CÁCH DUYÊN SPA
# ======================================

css = r'''

.ds-auth-page {
    background: #faf7ef;
    color: #17452e;
    font-family: 'Be Vietnam Pro', Arial, sans-serif;
}

.ds-auth-page .ds-main {
    padding-top: var(--ds-head, 76px);
}

.spa-auth {
    max-width: 1160px;
    margin: 0 auto;
    padding: 36px 20px 70px;
}

.spa-auth-card {
    display: grid;
    grid-template-columns: 54% 46%;
    min-height: 570px;
    background: #fffdf9;
    border: 1px solid #e9e3d8;
    border-radius: 24px;
    overflow: hidden;
    box-shadow: 0 15px 50px rgba(23,69,46,.06);
}

.spa-auth-form {
    padding: clamp(28px, 5vw, 64px);
    align-self: center;
}

.spa-auth-kicker {
    font-size: 10px !important;
    letter-spacing: 2px;
    font-weight: 700;
    color: #6a8b6e !important;
    margin: 0 0 13px;
}

.spa-auth-form h1 {
    font-family: 'Be Vietnam Pro', Arial, sans-serif;
    font-size: clamp(26px, 3vw, 38px);
    font-weight: 600;
    line-height: 1.4;
    color: #17452e;
    margin: 0 0 12px;
}

.spa-auth-subtitle {
    font-size: 13px;
    color: #718073;
    line-height: 1.8;
    margin: 0 0 26px;
}

.spa-auth-field {
    margin-bottom: 17px;
}

.spa-auth-field label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: #17452e;
    margin: 0 0 8px;
}

.spa-auth-field input:not([type=checkbox]),
.spa-auth-field select,
.spa-auth-field textarea {
    display: block;
    width: 100%;
    height: 46px;
    background: #fff;
    border: 1px solid #d8e0d7;
    border-radius: 11px;
    padding: 10px 14px;
    font: 400 13px 'Be Vietnam Pro', Arial, sans-serif;
    color: #17452e;
    outline: none;
    box-shadow: none;
}

.spa-auth-field input:focus,
.spa-auth-field select:focus {
    border-color: #648b6b;
    box-shadow: 0 0 0 3px #648b6b20;
}

.spa-auth-submit {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 11px;
    width: 100%;
    min-height: 48px;
    background: #17452e;
    color: #fff;
    border: 0;
    border-radius: 999px;
    font: 600 13px 'Be Vietnam Pro', Arial, sans-serif;
    margin-top: 23px;
    cursor: pointer;
    transition: background .2s;
}

.spa-auth-submit:hover {
    background: #286342;
}

.spa-auth-switch {
    margin: 21px 0 0;
    text-align: center;
    font-size: 12px;
    color: #718073;
}

.spa-auth-switch a {
    font-weight: 600;
    color: #17452e;
    text-decoration: underline;
    text-underline-offset: 3px;
}

.spa-auth-error,
.spa-auth-alert {
    color: #a0443b;
    background: #fff4f2;
    border: 1px solid #ead1ca;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 12px;
    line-height: 1.6;
    margin-top: 6px;
}

.spa-auth-error ul,
.spa-auth-alert ul {
    margin: 0;
    padding-left: 20px;
}

.spa-auth-help,
.spa-auth-help * {
    font-size: 11px;
    color: #738175;
    line-height: 1.7;
    margin-top: 5px;
}

.spa-auth-photo {
    position: relative;
    background-color: #d5d8c8;
    background-size: cover;
    background-position: center;
    min-height: 570px;
    display: flex;
    align-items: flex-end;
}

.spa-auth-photo-content {
    position: relative;
    z-index: 1;
    padding: 42px;
    color: #fff;
    text-shadow: 0 2px 10px #17392b70;
}

.spa-auth-photo-content span {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2.4px;
}

.spa-auth-photo-content h2 {
    color: #fff;
    font-family: 'Cormorant Garamond', Georgia, serif;
    font-size: clamp(31px, 3vw, 47px);
    font-weight: 600;
    line-height: 1.15;
    margin: 12px 0;
}

.spa-auth-photo-content p {
    color: #fff;
    font-size: 12px;
}

@media (max-width: 800px) {
    .spa-auth-card {
        grid-template-columns: 1fr;
        min-height: 0;
    }

    .spa-auth-photo {
        display: none;
    }

    .spa-auth {
        padding: 22px 15px 45px;
    }

    .spa-auth-form {
        padding: 32px 23px;
    }
}

'''


# ======================================
# SAO LƯU CODE CŨ
# ======================================

backup = ROOT / (
    "_backup_auth_" +
    datetime.now().strftime("%Y%m%d_%H%M%S")
)

for path in (LOGIN, REGISTER, CSS):
    if path.exists():

        target = backup / path.relative_to(ROOT)

        target.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(path, target)


# ======================================
# TỰ ĐỘNG CẬP NHẬT 3 FILE
# ======================================

for path, content in {**pages, CSS: css}.items():

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        content,
        encoding="utf-8"
    )

    print("OK:", path.relative_to(ROOT))


print("HOÀN TẤT CẬP NHẬT GIAO DIỆN DUYÊN SPA")
print("Không thay đổi database hoặc tài khoản.")
print("Bản sao lưu:", backup)
