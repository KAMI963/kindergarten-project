from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth import password_validation
from .models import CustomUser, EmailVerificationCode, ParentProfile, PasswordResetCode
from django.core.validators import RegexValidator
from django.utils import timezone
import re



class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш email',
        })
    )
    
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        required=True,
        initial='parent',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role', 'password1', 'password2')
    
    # ВАЖНО: УДАЛЯЕМ ИЛИ КОММЕНТИРУЕМ ВЕСЬ МЕТОД clean_email
    # def clean_email(self):
    #     email = self.cleaned_data.get('email')
    #     return email  # Просто возвращаем email без проверки
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('Пользователь с таким логином уже существует.')
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']
        user.email_verified = False
        if commit:
            user.save()
        return user

class EmailVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': 'Введите 6-значный код',
            'autocomplete': 'one-time-code',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        
        if not self.user:
            raise forms.ValidationError('Пользователь не найден.')
        
        try:
            verification_code = EmailVerificationCode.objects.filter(
                user=self.user,
                code=code,
                is_used=False
            ).latest('created_at')
        except EmailVerificationCode.DoesNotExist:
            raise forms.ValidationError('Неверный код подтверждения.')
        
        if not verification_code.is_valid():
            raise forms.ValidationError('Срок действия кода истек. Запросите новый код.')
        
        self.verification_code = verification_code
        return code

class ResendVerificationForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш email'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = CustomUser.objects.get(email=email, email_verified=False)
            self.user = user
        except CustomUser.DoesNotExist:
            raise forms.ValidationError('Пользователь с таким email не найден или уже подтвержден.')
        return email

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(  # Меняем с EmailField на CharField!
        label='Логин / Email',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите логин или email',
            'autocomplete': 'username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Пароль',
            'autocomplete': 'current-password'
        })
    )
    
    error_messages = {
        'invalid_login': 'Пожалуйста, введите правильный логин/email и пароль.',
        'inactive': 'Ваш аккаунт не активирован. Пожалуйста, подтвердите email.',
    }
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username = username.strip()
        return username
    
    def confirm_login_allowed(self, user):
        if not user.email_verified:
            raise forms.ValidationError(
                'Ваш email не подтвержден. Пожалуйста, проверьте почту и подтвердите регистрацию.',
                code='inactive',
            )
        super().confirm_login_allowed(user)

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваш email',
            'autocomplete': 'email'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = CustomUser.objects.get(email=email)
            if not user.email_verified:
                raise forms.ValidationError('Email не подтвержден. Пожалуйста, сначала подтвердите регистрацию.')
            self.user = user
        except CustomUser.DoesNotExist:
            raise forms.ValidationError('Пользователь с таким email не найден.')
        return email

class PasswordResetCodeForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': 'Введите 6-значный код',
            'autocomplete': 'off',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        
        if not self.user:
            raise forms.ValidationError('Пользователь не найден.')
        
        try:
            reset_code = PasswordResetCode.objects.filter(
                user=self.user,
                code=code,
                is_used=False
            ).latest('created_at')
        except PasswordResetCode.DoesNotExist:
            raise forms.ValidationError('Неверный код восстановления.')
        
        if not reset_code.is_valid():
            raise forms.ValidationError('Срок действия кода истек. Запросите новый код.')
        
        self.reset_code = reset_code
        return code

class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password'
        }),
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label='Подтверждение пароля',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'autocomplete': 'new-password'
        }),
    )
    
    
class ProfileEditForm(forms.ModelForm):
    """Форма редактирования профиля"""
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'birth_date', 'address']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Фамилия'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 999-99-99'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Адрес проживания'}),
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'email': 'Email',
            'phone': 'Телефон',
            'birth_date': 'Дата рождения',
            'address': 'Адрес',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поля необязательными
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        self.fields['phone'].required = False
        self.fields['birth_date'].required = False
        self.fields['address'].required = False
        
        
# accounts/forms.py
from .models import TeacherProfile, DirectorProfile

class TeacherProfileForm(forms.ModelForm):
    class Meta:
        model = TeacherProfile
        fields = ['education', 'specialization', 'experience']
        widgets = {
            'education': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
            'experience': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

class DirectorProfileForm(forms.ModelForm):
    class Meta:
        model = DirectorProfile
        fields = ['education', 'management_experience']
        widgets = {
            'education': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'management_experience': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
        
class ParentProfileForm(forms.ModelForm):
    """Форма для заполнения анкеты родителя"""
    
    # Валидатор для телефона
    phone_validator = RegexValidator(
        regex=r'^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$',
        message='Телефон должен быть в формате +7 (XXX) XXX-XX-XX'
    )
    
    class Meta:
        model = ParentProfile
        fields = [
            # Основные сведения
            'full_name', 'birth_date', 'nationality',
            # Паспортные данные
            'passport_series', 'passport_number', 'passport_issue_date', 'passport_issued_by',
            # Социальные условия
            'registration_address', 'actual_address', 'address_same_as_registration',
            # Телефоны
            'mobile_phone', 'home_phone', 'work_phone',
            # Место работы
            'workplace', 'position', 'not_working',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Иванов Иван Иванович'
            }),
            'birth_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'nationality': forms.TextInput(attrs={
                'class': 'form-control nationality-input',
                'placeholder': 'Начните вводить национальность...',
                'autocomplete': 'off'
            }),
            'passport_series': forms.TextInput(attrs={
                'class': 'form-control passport-masked',
                'placeholder': 'XXXX',
                'maxlength': 4
            }),
            'passport_number': forms.TextInput(attrs={
                'class': 'form-control passport-masked',
                'placeholder': 'XXXXXX',
                'maxlength': 6
            }),
            'passport_issue_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'passport_issued_by': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Отделом УФМС России по г. Москве'
            }),
            'registration_address': forms.Textarea(attrs={
                'class': 'form-control address-input',
                'rows': 3,
                'placeholder': 'Индекс, город, улица, дом, квартира\nПример: 123456, г. Москва, ул. Примерная, д. 1, кв. 1'
            }),
            'actual_address': forms.Textarea(attrs={
                'class': 'form-control address-input',
                'rows': 3,
                'placeholder': 'Индекс, город, улица, дом, квартира'
            }),
            'address_same_as_registration': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleActualAddress(this)'
            }),
            'mobile_phone': forms.TextInput(attrs={
                'class': 'form-control phone-mask',
                'placeholder': '+7 (XXX) XXX-XX-XX'
            }),
            'home_phone': forms.TextInput(attrs={
                'class': 'form-control phone-mask',
                'placeholder': '+7 (XXX) XXX-XX-XX'
            }),
            'work_phone': forms.TextInput(attrs={
                'class': 'form-control phone-mask',
                'placeholder': '+7 (XXX) XXX-XX-XX'
            }),
            'workplace': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название организации'
            }),
            'position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Должность'
            }),
            'not_working': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleWorkFields(this)'
            }),
        }
        labels = {
            'full_name': 'ФИО родителя',
            'birth_date': 'Дата рождения',
            'nationality': 'Национальность',
            'passport_series': 'Серия паспорта',
            'passport_number': 'Номер паспорта',
            'passport_issue_date': 'Дата выдачи',
            'passport_issued_by': 'Кем выдан',
            'registration_address': 'Адрес места прописки (регистрации)',
            'actual_address': 'Адрес места проживания',
            'address_same_as_registration': 'Совпадает с адресом прописки',
            'mobile_phone': 'Мобильный телефон',
            'home_phone': 'Домашний телефон',
            'work_phone': 'Рабочий телефон',
            'workplace': 'Место работы',
            'position': 'Должность',
            'not_working': 'Не работаю',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Устанавливаем обязательные поля
        required_fields = [
            'full_name', 'birth_date', 'passport_series', 'passport_number',
            'passport_issue_date', 'passport_issued_by', 'registration_address',
            'mobile_phone'
        ]
        
        for field_name in required_fields:
            self.fields[field_name].required = True
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['required'] = 'required'
        
        # Добавляем подсказки
        self.fields['registration_address'].help_text = 'Укажите полный адрес: индекс, город, улицу, номер дома и квартиры'
        self.fields['mobile_phone'].help_text = 'Обязательное поле для связи'
        
        # Если пользователь отмечен как "Не работаю", делаем поля работы необязательными
        if self.instance and self.instance.not_working:
            self.fields['workplace'].required = False
            self.fields['position'].required = False
    
    def clean_mobile_phone(self):
        """Валидация мобильного телефона"""
        phone = self.cleaned_data.get('mobile_phone', '')
        if not phone:
            raise forms.ValidationError('Мобильный телефон обязателен для заполнения')
        return self._clean_phone_number(phone)
    
    def clean_home_phone(self):
        """Валидация домашнего телефона"""
        phone = self.cleaned_data.get('home_phone', '')
        if phone:
            return self._clean_phone_number(phone)
        return phone
    
    def clean_work_phone(self):
        """Валидация рабочего телефона"""
        phone = self.cleaned_data.get('work_phone', '')
        if phone:
            return self._clean_phone_number(phone)
        return phone
    
    def _clean_phone_number(self, phone):
        """Очистка номера телефона"""
        import re
        # Удаляем все нецифровые символы
        cleaned = re.sub(r'\D', '', phone)
        
        # Приводим к формату +7XXXXXXXXXX
        if cleaned.startswith('8') and len(cleaned) == 11:
            cleaned = '7' + cleaned[1:]
        elif len(cleaned) == 10:
            cleaned = '7' + cleaned
        
        # Форматируем
        if len(cleaned) == 11 and cleaned.startswith('7'):
            return f'+7({cleaned[1:4]}){cleaned[4:7]}-{cleaned[7:9]}-{cleaned[9:11]}'
        
        return phone
    
    def clean_passport_series(self):
        """Валидация серии паспорта"""
        series = self.cleaned_data.get('passport_series', '')
        import re
        if series and not re.match(r'^\d{4}$', series):
            raise forms.ValidationError('Серия паспорта должна состоять из 4 цифр')
        return series
    
    def clean_passport_number(self):
        """Валидация номера паспорта"""
        number = self.cleaned_data.get('passport_number', '')
        import re
        if number and not re.match(r'^\d{6}$', number):
            raise forms.ValidationError('Номер паспорта должен состоять из 6 цифр')
        return number
    
    def clean(self):
        cleaned_data = super().clean()
        not_working = cleaned_data.get('not_working', False)
        
        # Если родитель работает, проверяем заполнение полей о работе
        if not not_working:
            workplace = cleaned_data.get('workplace', '')
            position = cleaned_data.get('position', '')
            
            if not workplace:
                self.add_error('workplace', 'Укажите место работы')
            if not position:
                self.add_error('position', 'Укажите должность')
        
        return cleaned_data
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        
        # Если включен флаг "Совпадает с адресом прописки", копируем адрес
        if profile.address_same_as_registration:
            profile.actual_address = profile.registration_address
        
        if commit:
            profile.save()
            
            # Обновляем данные пользователя
            if self.request and self.request.user:
                user = self.request.user
                user.phone = profile.mobile_phone
                user.birth_date = profile.birth_date
                user.save()
        
        return profile


class ParentProfileFullForm(forms.ModelForm):
    """Полная форма для анкеты родителя"""
    
    address_same_as_registration = forms.BooleanField(
        required=False,
        label='Совпадает с адресом прописки',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    not_working = forms.BooleanField(
        required=False,
        label='Не работаю',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = ParentProfile
        fields = [
            'full_name', 'birth_date', 'nationality',
            'passport_series', 'passport_number', 'passport_issue_date', 'passport_issued_by',
            'registration_address', 'actual_address',
            'mobile_phone', 'home_phone', 'work_phone',
            'workplace', 'position',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Иванов Иван Иванович'}),
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Начните вводить национальность...'}),
            'passport_series': forms.TextInput(attrs={'class': 'form-control passport-masked', 'placeholder': 'XXXX'}),
            'passport_number': forms.TextInput(attrs={'class': 'form-control passport-masked', 'placeholder': 'XXXXXX'}),
            'passport_issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'passport_issued_by': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Кем выдан паспорт'}),
            'registration_address': forms.Textarea(attrs={'class': 'form-control address-input', 'rows': 3, 'placeholder': 'Индекс, город, улица, дом, квартира'}),
            'actual_address': forms.Textarea(attrs={'class': 'form-control address-input', 'rows': 3, 'placeholder': 'Индекс, город, улица, дом, квартира'}),
            'mobile_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '+7 (XXX) XXX-XX-XX'}),
            'home_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '+7 (XXX) XXX-XX-XX'}),
            'work_phone': forms.TextInput(attrs={'class': 'form-control phone-mask', 'placeholder': '+7 (XXX) XXX-XX-XX'}),
            'workplace': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название организации'}),
            'position': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Должность'}),
        }
        labels = {
            'full_name': 'ФИО родителя',
            'birth_date': 'Дата рождения',
            'nationality': 'Национальность',
            'passport_series': 'Серия паспорта',
            'passport_number': 'Номер паспорта',
            'passport_issue_date': 'Дата выдачи',
            'passport_issued_by': 'Кем выдан',
            'registration_address': 'Адрес места прописки (регистрации)',
            'actual_address': 'Адрес места проживания',
            'mobile_phone': 'Мобильный телефон',
            'home_phone': 'Домашний телефон',
            'work_phone': 'Рабочий телефон',
            'workplace': 'Место работы',
            'position': 'Должность',
        }



class PrimaryParentToggleForm(forms.Form):
    """Форма для переключения основного родителя"""
    is_primary = forms.BooleanField(
        required=False,
        label='Основной родитель',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input toggle-switch',
            'data-toggle': 'primary-parent'
        })
    )
    
    primary_parent_name = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ФИО основного родителя'
        }),
        label='ФИО основного родителя'
    )
