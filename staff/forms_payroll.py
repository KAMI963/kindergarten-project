# staff/forms_payroll.py
from django import forms
from .models import PayrollType, EmployeePayrollAssignment, WorkSchedule, EmployeeWorkSchedule
import json
from decimal import Decimal

class PayrollTypeForm(forms.ModelForm):
    """Форма для вида начисления"""
    
    seniority_scale_json = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'class': 'form-control font-monospace'}),
        required=False,
        label='Шкала за стаж (JSON)',
        help_text='Пример: [{"years_from": 0, "years_to": 3, "percent": 5}, {"years_from": 3, "years_to": 5, "percent": 10}]'
    )
    
    class Meta:
        model = PayrollType
        fields = [
            'code', 'name', 'description', 'calculation_type', 'base_value',
            'is_accrual', 'is_taxable', 'include_in_average', 'is_active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SALARY_HOURLY'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Оплата по окладу (по часам)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'calculation_type': forms.Select(attrs={'class': 'form-select'}),
            'base_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = {
            'code': 'Код',
            'name': 'Наименование',
            'description': 'Описание',
            'calculation_type': 'Тип расчета',
            'base_value': 'Базовое значение',
            'is_accrual': 'Это начисление',
            'is_taxable': 'Облагается налогом',
            'include_in_average': 'Учитывается в среднем заработке',
            'is_active': 'Активно',
        }
    
    def clean_seniority_scale_json(self):
        data = self.cleaned_data['seniority_scale_json']
        if data:
            try:
                parsed = json.loads(data)
                # Валидация структуры
                for item in parsed:
                    if not all(k in item for k in ['years_from', 'years_to', 'percent']):
                        raise forms.ValidationError('Каждый элемент должен содержать years_from, years_to, percent')
                return parsed
            except json.JSONDecodeError:
                raise forms.ValidationError('Некорректный JSON')
        return None
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('seniority_scale_json'):
            instance.seniority_scale = self.cleaned_data['seniority_scale_json']
        if commit:
            instance.save()
        return instance


class EmployeePayrollAssignmentForm(forms.ModelForm):
    """Форма для назначения начислений сотруднику"""
    
    class Meta:
        model = EmployeePayrollAssignment
        fields = [
            'payroll_type', 'start_date', 'end_date', 'custom_value',
            'calculation_base', 'order_number', 'order_date', 'is_active'
        ]
        widgets = {
            'payroll_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'custom_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'calculation_base': forms.Select(attrs={'class': 'form-select'}),
            'order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        labels = {
            'payroll_type': 'Вид начисления',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания (если срочное)',
            'custom_value': 'Индивидуальное значение',
            'calculation_base': 'База для расчета',
            'order_number': 'Номер приказа',
            'order_date': 'Дата приказа',
            'is_active': 'Активно',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', 'Дата окончания должна быть позже даты начала')
        
        return cleaned_data


class WorkScheduleForm(forms.ModelForm):
    """Форма для графика работы (соответствует существующей модели)"""
    
    class Meta:
        model = WorkSchedule
        fields = ['name', 'schedule_type', 'employee_types', 'weekly_hours', 'daily_hours', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'schedule_type': forms.Select(attrs={'class': 'form-select'}),
            'employee_types': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'teacher,assistant,guard'}),
            'weekly_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'daily_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# staff/forms_payroll.py - исправленная форма

class EmployeeWorkScheduleForm(forms.ModelForm):
    """Форма для назначения графика сотруднику"""
    
    class Meta:
        model = EmployeeWorkSchedule
        fields = ['employee', 'schedule_template', 'start_date', 'end_date', 'is_active']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'schedule_template': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        labels = {
            'employee': 'Сотрудник',
            'schedule_template': 'График работы',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания',
            'is_active': 'Активно',
        }
