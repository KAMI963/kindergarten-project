# staff/forms_profile.py
from django import forms
from django.contrib.auth import get_user_model
from .models import Employee
from accounts.models import CustomUser

User = get_user_model()

class EmployeeProfileForm(forms.ModelForm):
    """Форма для редактирования профиля сотрудника"""
    
    class Meta:
        model = Employee
        fields = [
            'phone', 'email', 'address', 'birth_date', 'birth_place', 'photo'
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'neo-input'}),
            'phone': forms.TextInput(attrs={
                'class': 'neo-input',
                'placeholder': '+7 (999) 123-45-67'
            }),
            'email': forms.EmailInput(attrs={'class': 'neo-input'}),
            'address': forms.Textarea(attrs={'class': 'neo-input', 'rows': 3}),
            'birth_place': forms.TextInput(attrs={'class': 'neo-input'}),
            'photo': forms.FileInput(attrs={'class': 'neo-input'}),
        }
        labels = {
            'phone': 'Телефон',
            'email': 'Email',
            'address': 'Адрес проживания',
            'birth_date': 'Дата рождения',
            'birth_place': 'Место рождения',
            'photo': 'Фотография',
        }


class UserProfileForm(forms.ModelForm):
    """Форма для редактирования данных пользователя"""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'neo-input'}),
            'last_name': forms.TextInput(attrs={'class': 'neo-input'}),
            'email': forms.EmailInput(attrs={'class': 'neo-input'}),
            'phone': forms.TextInput(attrs={
                'class': 'neo-input',
                'placeholder': '+7 (999) 123-45-67'
            }),
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'email': 'Email',
            'phone': 'Телефон',
        }


class ChangePasswordForm(forms.Form):
    """Форма смены пароля"""
    
    old_password = forms.CharField(
        label='Текущий пароль',
        widget=forms.PasswordInput(attrs={'class': 'neo-input'})
    )
    new_password = forms.CharField(
        label='Новый пароль',
        widget=forms.PasswordInput(attrs={'class': 'neo-input'})
    )
    confirm_password = forms.CharField(
        label='Подтверждение пароля',
        widget=forms.PasswordInput(attrs={'class': 'neo-input'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', 'Пароли не совпадают')
        
        return cleaned_data
