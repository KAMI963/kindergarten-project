# staff/forms.py - исправленные импорты

from django import forms
from django.utils import timezone
from datetime import date, timedelta
from .models import (
    Employee, HireOrder, PersonalFile, PassportData, INN, SNILS,
    EducationDocument, QualificationCourse, Attestation,
    MedicalExamination, CriminalRecordCheck, StaffPosition,
    StaffUnit, Vacancy, VacancyCandidate, LaborContract,
    AdditionalAgreement, WorkSchedule,  # Убрали WorkScheduleEntry
    Timesheet, TimesheetEntry, LeaveSchedule, LeaveRequest,
    DisciplinaryAction, Encouragement, DispensaryRecord,
    SalaryCalculation
)


class EmployeeForm(forms.ModelForm):
    """Форма сотрудника"""
    
    class Meta:
        model = Employee
        fields = [
            'full_name', 'employee_type', 'position', 'phone', 'email',
            'address', 'birth_date', 'birth_place', 'hire_date',
            'is_active', 'dismissal_date', 'dismissal_reason', 'photo'
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'dismissal_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'employee_type': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 999-99-99'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'birth_place': forms.TextInput(attrs={'class': 'form-control'}),
            'dismissal_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'full_name': 'ФИО *',
            'employee_type': 'Категория *',
            'position': 'Должность *',
            'phone': 'Телефон *',
            'email': 'Email *',
            'address': 'Адрес проживания *',
            'birth_date': 'Дата рождения *',
            'birth_place': 'Место рождения *',
            'hire_date': 'Дата приема *',
            'is_active': 'Работает в настоящее время',
            'dismissal_date': 'Дата увольнения',
            'dismissal_reason': 'Причина увольнения',
        }


class PassportDataForm(forms.ModelForm):
    """Форма паспортных данных"""
    
    class Meta:
        model = PassportData
        fields = ['series', 'number', 'issued_by', 'issue_date', 'department_code', 'scan']
        widgets = {
            'series': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '1234'}),
            'number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '567890'}),
            'issued_by': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'department_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123-456'}),
            'scan': forms.FileInput(attrs={'class': 'form-control'}),
        }


class INNForm(forms.ModelForm):
    """Форма ИНН"""
    
    class Meta:
        model = INN
        fields = ['inn_number', 'scan']
        widgets = {
            'inn_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123456789012'}),
            'scan': forms.FileInput(attrs={'class': 'form-control'}),
        }


class SNILSForm(forms.ModelForm):
    """Форма СНИЛС"""
    
    class Meta:
        model = SNILS
        fields = ['snils_number', 'scan']
        widgets = {
            'snils_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123-456-789 01'}),
            'scan': forms.FileInput(attrs={'class': 'form-control'}),
        }


class EducationDocumentForm(forms.ModelForm):
    """Форма документа об образовании"""
    
    class Meta:
        model = EducationDocument
        fields = [
            'education_level', 'document_type', 'series', 'number',
            'issue_date', 'institution', 'qualification', 'specialization',
            'valid_until', 'scan'
        ]
        widgets = {
            'education_level': forms.Select(attrs={'class': 'form-select'}),
            'document_type': forms.TextInput(attrs={'class': 'form-control'}),
            'series': forms.TextInput(attrs={'class': 'form-control'}),
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'institution': forms.TextInput(attrs={'class': 'form-control'}),
            'qualification': forms.TextInput(attrs={'class': 'form-control'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'scan': forms.FileInput(attrs={'class': 'form-control'}),
        }


class QualificationCourseForm(forms.ModelForm):
    """Форма курсов повышения квалификации"""
    
    class Meta:
        model = QualificationCourse
        fields = [
            'course_name', 'provider', 'start_date', 'end_date',
            'hours', 'document_number', 'document_date', 'scan'
        ]
        widgets = {
            'course_name': forms.TextInput(attrs={'class': 'form-control'}),
            'provider': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'document_number': forms.TextInput(attrs={'class': 'form-control'}),
            'document_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'scan': forms.FileInput(attrs={'class': 'form-control'}),
        }


class AttestationForm(forms.ModelForm):
    """Форма аттестации"""
    
    class Meta:
        model = Attestation
        fields = [
            'attestation_date', 'result', 'category',
            'protocol_number', 'protocol_date', 'valid_until',
            'scan', 'notes'
        ]
        widgets = {
            'attestation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'result': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'protocol_number': forms.TextInput(attrs={'class': 'form-control'}),
            'protocol_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'scan': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class MedicalExaminationForm(forms.ModelForm):
    """Форма медосмотра"""
    
    class Meta:
        model = MedicalExamination
        fields = [
            'examination_type', 'examination_date', 'valid_until',
            'medical_book_number', 'medical_book_scan', 'is_allowed', 'notes'
        ]
        widgets = {
            'examination_type': forms.Select(attrs={'class': 'form-select'}),
            'examination_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'medical_book_number': forms.TextInput(attrs={'class': 'form-control'}),
            'medical_book_scan': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class CriminalRecordCheckForm(forms.ModelForm):
    """Форма справки об отсутствии судимости"""
    
    class Meta:
        model = CriminalRecordCheck
        fields = ['check_date', 'document_number', 'issued_by', 'valid_until', 'scan']
        widgets = {
            'check_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'document_number': forms.TextInput(attrs={'class': 'form-control'}),
            'issued_by': forms.TextInput(attrs={'class': 'form-control'}),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'scan': forms.FileInput(attrs={'class': 'form-control'}),
        }


class StaffPositionForm(forms.ModelForm):
    """Форма должности штатного расписания"""
    
    class Meta:
        model = StaffPosition
        fields = [
            'code', 'title', 'category', 'tariff_category', 'base_salary',
            'hazardous_bonus', 'irregular_bonus', 'education_requirements', 'description'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'tariff_category': forms.TextInput(attrs={'class': 'form-control'}),
            'base_salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hazardous_bonus': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'irregular_bonus': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'education_requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class StaffUnitForm(forms.ModelForm):
    """Форма штатной единицы"""
    
    class Meta:
        model = StaffUnit
        fields = [
            'position', 'quantity', 'salary_coefficient',
            'has_hazardous', 'has_irregular', 'additional_payment', 'notes'
        ]
        widgets = {
            'position': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25', 'min': '0'}),
            'salary_coefficient': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'additional_payment': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class VacancyForm(forms.ModelForm):
    """Форма вакансии"""
    
    class Meta:
        model = Vacancy
        fields = ['requirements', 'responsibilities', 'conditions', 'is_published', 'closing_date']
        widgets = {
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'responsibilities': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'closing_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }


class VacancyCandidateForm(forms.ModelForm):
    """Форма кандидата на вакансию"""
    
    class Meta:
        model = VacancyCandidate
        fields = ['full_name', 'phone', 'email', 'resume', 'status', 'interview_date', 'notes']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (999) 999-99-99'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'resume': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'interview_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class LaborContractForm(forms.ModelForm):
    """Форма трудового договора"""
    
    class Meta:
        model = LaborContract
        fields = [
            'contract_number', 'contract_type', 'start_date', 'end_date',
            'probation_period', 'probation_passed', 'contract_file'
            # Убрали 'notes' из fields
        ]
        widgets = {
            'contract_number': forms.TextInput(attrs={'class': 'form-control'}),
            'contract_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'probation_period': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'contract_file': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        contract_type = cleaned_data.get('contract_type')
        end_date = cleaned_data.get('end_date')
        
        if contract_type == 'fixed_term' and not end_date:
            self.add_error('end_date', 'Для срочного договора укажите дату окончания')
        
        return cleaned_data

class AdditionalAgreementForm(forms.ModelForm):
    """Форма доп. соглашения"""
    
    class Meta:
        model = AdditionalAgreement
        fields = ['agreement_number', 'agreement_date', 'changes_description', 'file']
        widgets = {
            'agreement_number': forms.TextInput(attrs={'class': 'form-control'}),
            'agreement_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'changes_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }


class WorkScheduleForm(forms.ModelForm):
    """Форма графика работы"""
    
    class Meta:
        model = WorkSchedule
        fields = ['name', 'schedule_type', 'employee_types', 'weekly_hours', 'daily_hours', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'schedule_type': forms.Select(attrs={'class': 'form-select'}),
            'employee_types': forms.TextInput(attrs={'class': 'form-control'}),
            'weekly_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'daily_hours': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class TimesheetEntryForm(forms.ModelForm):
    """Форма записи в табеле"""
    
    class Meta:
        model = TimesheetEntry
        fields = [
            'employee', 'suspension_start', 'suspension_end', 'suspension_reason',
            'suspension_order', 'notes'
        ]
        # Добавляем поля для каждого дня
        for day in range(1, 32):
            fields.append(f'day_{day}')
        
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'suspension_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'suspension_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'suspension_reason': forms.TextInput(attrs={'class': 'form-control'}),
            'suspension_order': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        
        # Добавляем виджеты для каждого дня
        for day in range(1, 32):
            widgets[f'day_{day}'] = forms.Select(attrs={'class': 'form-select form-select-sm'})


class LeaveScheduleForm(forms.ModelForm):
    """Форма графика отпусков"""
    
    class Meta:
        model = LeaveSchedule
        fields = [
            'employee', 'year', 'leave_type', 'start_date', 'end_date',
            'category_duration', 'status', 'application_date', 'application_file',
            'order_number', 'order_date', 'order_file', 'replacement_employee', 'notes'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': '2020'}),
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'category_duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'application_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'application_file': forms.FileInput(attrs={'class': 'form-control'}),
            'order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'order_file': forms.FileInput(attrs={'class': 'form-control'}),
            'replacement_employee': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class LeaveRequestForm(forms.ModelForm):
    """Форма заявления на отпуск"""
    
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'duration', 'comments']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                self.add_error('end_date', 'Дата окончания должна быть позже даты начала')
            
            # Автоматический расчет длительности
            duration = (end_date - start_date).days + 1
            cleaned_data['duration'] = duration
        
        return cleaned_data


class DisciplinaryActionForm(forms.ModelForm):
    """Форма дисциплинарного взыскания"""
    
    class Meta:
        model = DisciplinaryAction
        fields = [
            'action_type', 'violation_description', 'order_number', 'order_date',
            'order_file', 'issue_date', 'valid_until', 'notes'
        ]
        widgets = {
            'action_type': forms.Select(attrs={'class': 'form-select'}),
            'violation_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'order_file': forms.FileInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class EncouragementForm(forms.ModelForm):
    """Форма поощрения"""
    
    class Meta:
        model = Encouragement
        fields = [
            'encouragement_type', 'description', 'order_number', 'order_date',
            'order_file', 'bonus_amount'
        ]
        widgets = {
            'encouragement_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'order_file': forms.FileInput(attrs={'class': 'form-control'}),
            'bonus_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class DispensaryRecordForm(forms.ModelForm):
    """Форма диспансеризации"""
    
    class Meta:
        model = DispensaryRecord
        fields = [
            'year', 'exemption_start', 'exemption_end', 'exemption_days',
            'medical_certificate', 'status', 'notes'
        ]
        widgets = {
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': '2020'}),
            'exemption_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'exemption_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'exemption_days': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'medical_certificate': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('exemption_start')
        end_date = cleaned_data.get('exemption_end')
        
        if start_date and end_date:
            if start_date > end_date:
                self.add_error('exemption_end', 'Дата окончания должна быть позже даты начала')
            
            # Автоматический расчет дней освобождения
            days = (end_date - start_date).days + 1
            cleaned_data['exemption_days'] = days
        
        return cleaned_data
    
    
class HireOrderForm(forms.ModelForm):
    """Форма для создания приказа о приеме"""
    
    class Meta:
        model = HireOrder
        fields = [
            'order_date', 'hire_date', 'position', 'department',
            'employment_condition', 'tariff_rate', 'has_bonus',
            'bonus_description', 'bonus_amount', 'probation_period',
            'basis_documents', 'employee_acquainted', 'acquainted_date'
        ]
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hire_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'employment_condition': forms.Select(attrs={'class': 'form-select'}),
            'tariff_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'bonus_description': forms.TextInput(attrs={'class': 'form-control'}),
            'bonus_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'probation_period': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'basis_documents': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'acquainted_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        labels = {
            'order_date': 'Дата приказа',
            'hire_date': 'Дата приема на работу',
            'position': 'Должность',
            'department': 'Подразделение',
            'employment_condition': 'Условия приема',
            'tariff_rate': 'Тарифная ставка (оклад)',
            'has_bonus': 'Есть надбавки',
            'bonus_description': 'Описание надбавок',
            'bonus_amount': 'Сумма надбавок',
            'probation_period': 'Испытательный срок (мес.)',
            'basis_documents': 'Основание',
            'employee_acquainted': 'Сотрудник ознакомлен',
            'acquainted_date': 'Дата ознакомления',
        }
    
    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)
        
        if self.employee:
            self.fields['position'].initial = self.employee.position
            self.fields['hire_date'].initial = self.employee.hire_date
