from django import forms
from .models import Payment, Tariff, AdditionalService, ServiceEnrollment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'})
        }


class TariffForm(forms.ModelForm):
    class Meta:
        model = Tariff
        fields = [
            'age_category', 'year',
            'total_amount', 'content_amount', 'food_amount',
            'daily_rate', 'food_daily_rate'
        ]
        widgets = {
            'age_category': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'content_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'food_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'daily_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'food_daily_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


class AdditionalServiceForm(forms.ModelForm):
    class Meta:
        model = AdditionalService
        fields = [
            'name', 'service_type', 'description',
            'price_per_month', 'price_per_lesson',
            'age_min', 'age_max',
            'teacher', 'teacher_user',
            'schedule', 'program',
            'is_active', 'max_students',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название кружка'}),
            'service_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price_per_month': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'price_per_lesson': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'age_min': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '18'}),
            'age_max': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '18'}),
            'teacher': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ФИО преподавателя (текстом)'}),
            'teacher_user': forms.Select(attrs={'class': 'form-select'}),
            'schedule': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Пн, Ср 15:00-16:00'}),
            'program': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_students': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        age_min = cleaned_data.get('age_min')
        age_max = cleaned_data.get('age_max')
        if age_min and age_max and age_min > age_max:
            raise forms.ValidationError("Минимальный возраст не может быть больше максимального.")
        return cleaned_data


class ServiceEnrollmentForm(forms.ModelForm):
    class Meta:
        model = ServiceEnrollment
        fields = ['service', 'start_date', 'notes']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }