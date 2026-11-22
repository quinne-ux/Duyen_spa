# gymx2/crmg2/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import ServiceItem, TrialBooking, Customer, Service

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    # Định nghĩa các trường bổ sung: First Name, Last Name, Email
    first_name = forms.CharField(max_length=150, required=True, label='Họ')
    last_name = forms.CharField(max_length=150, required=True, label='Tên')
    email = forms.EmailField(max_length=254, required=True, label='Email')

    class Meta:
        # Kế thừa các trường username và password mặc định
        model = User
        # Sắp xếp các trường hiển thị theo thứ tự mong muốn
        fields = ('first_name', 'last_name', 'email', 'username') + UserCreationForm.Meta.fields

    def save(self, commit=True):
        # Hàm save được tùy chỉnh để lưu email, first_name và last_name
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class ServiceItemForm(forms.ModelForm):
    class Meta:
        model = ServiceItem
        # service_id là AutoField nên loại bỏ
        fields = ['name', 'description', 'image','status', 'display_order']

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'status': forms.Select(choices=ServiceItem.STATUS_CHOICES),
        }


# --- BỔ SUNG: FORM ĐẶT LỊCH TẬP THỬ (TRIAL BOOKING FORM) ---

class TrialBookingForm(forms.ModelForm):
    SERVICE_CHOICES = [
        ('Gym', 'Gym'),
        ('Yoga', 'Yoga'),
        ('Dance', 'Dance'),
    ]

    # Ghi đè trường 'service' để dùng Checkbox
    service = forms.MultipleChoiceField(
        choices=SERVICE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Dịch vụ'
    )

    # Tùy chỉnh widget cho ngày đăng ký
    register_date = forms.DateField(
        label='Ngày đăng ký',
        widget=forms.DateInput(
            attrs={
                'class': 'booking-input',  # Class này từ trial_booking.html
                'type': 'date',
                'onkeydown': 'return false;',  # Không cho gõ tay
                'onfocus': 'this.showPicker && this.showPicker();',
            }
        ),
        input_formats=['%Y-%m-%d'],
    )

    class Meta:
        model = TrialBooking
        # Bỏ 'user' khỏi fields, vì ta sẽ lấy tự động từ request
        fields = ['full_name', 'phone', 'service', 'register_date']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'booking-input',
                'placeholder': 'Nhập họ và tên'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'booking-input',
                'placeholder': 'Nhập số điện thoại',
                'type': 'tel'
            }),
        }
        labels = {
            'full_name': 'Họ và tên',
            'phone': 'Số điện thoại',
            'register_date': 'Ngày đăng ký',
        }

    def clean_service(self):
        """Chuyển đổi list services (vd: ['Gym','Yoga']) thành string 'Gym, Yoga' để lưu vào CharField"""
        services = self.cleaned_data['service']
        return ', '.join(services)

# --- TÍCH HỢP TỪ GLUCOYUH: FORM CHỈNH SỬA PROFILE ---
class ProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address', 'gender', 'membership']
        widgets = {
            'gender': forms.RadioSelect(choices=Customer.GENDER_CHOICES),
            # --- SỬA: Đổi từ Select sang TextInput và set readonly (vì khách không được tự sửa gói) ---
            'membership': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }
# --- KẾT THÚC TÍCH HỢP ---

# --- THÊM FORM MỚI CHO ADMIN NHẬP GÓI ---
class PackageForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['package_id', 'name', 'price', 'duration_months', 'description', 'is_active']

        labels = {
            'package_id': 'Mã Gói Tập',
            'name': 'Tên Gói',
            'price': 'Giá Tiền (VND)',
            'duration_months': 'Thời Hạn (Tháng)',
            'description': 'Mô Tả',
            'is_active': 'Kích Hoạt',
        }

        widgets = {
            'package_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: GT005'}),
            # Dùng TextInput để nhập tùy ý
            'name': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Nhập tên gói (VD: Super VIP, Mùa Hè...)'}),
            'price': forms.NumberInput(attrs={'class': 'form-control'}),
            'duration_months': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }