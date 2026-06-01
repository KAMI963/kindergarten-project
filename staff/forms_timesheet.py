# staff/forms_timesheet.py

from django import forms
from .models import TimesheetEntry, Employee, OvertimeTracking
from datetime import date, datetime

class QuickTimesheetEntryForm(forms.Form):
    """Форма для быстрого редактирования записи в табеле"""
    
    REASON_CHOICES = [
        ('sick', 'Болеет (больничный)'),
        ('leave_out_of_schedule', 'В отпуске (вне графика)'),
        ('dispensary', 'Диспансеризация'),
        ('family_reasons', 'Семейные обстоятельства (без сохранения зарплаты)'),
        ('no_show', 'Не вышел (прогул)'),
        ('business_trip', 'Командировка'),
        ('training', 'Повышение квалификации'),
        ('parental_leave', 'Отпуск по уходу за ребенком'),
        ('other', 'Другое'),
    ]
    
    DOCUMENT_TYPES = [
        ('sick_leave', 'Больничный лист'),
        ('medical_certificate', 'Медицинская справка'),
        ('parent_statement', 'Заявление родителя'),
        ('dispensary_certificate', 'Справка о диспансеризации'),
        ('business_trip_order', 'Приказ о командировке'),
        ('training_certificate', 'Удостоверение о повышении квалификации'),
        ('other', 'Другое'),
    ]
    
    action = forms.ChoiceField(
        choices=[('absent', 'Отсутствует'), ('overtime', 'Сверхурочная работа'), ('night', 'Ночная работа')],
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    reason = forms.ChoiceField(choices=REASON_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    hours = forms.DecimalField(max_digits=4, decimal_places=1, required=False, min_value=0, max_value=24, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm'}))
    
    # Поля для документа
    document_type = forms.ChoiceField(choices=DOCUMENT_TYPES, required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    document_file = forms.FileField(required=False, widget=forms.FileInput(attrs={'class': 'form-control form-control-sm'}))
    document_number = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Номер документа'}))
    document_start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    document_end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}))
    
    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        self.date = kwargs.pop('date', None)
        self.entry = kwargs.pop('entry', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        reason = cleaned_data.get('reason')
        hours = cleaned_data.get('hours')
        document_type = cleaned_data.get('document_type')
        document_file = cleaned_data.get('document_file')
        
        if action == 'absent' and reason == 'sick' and not document_file:
            self.add_error('document_file', 'Для отметки болезни необходимо прикрепить документ')
        
        if action == 'absent' and reason == 'dispensary' and not document_file:
            self.add_error('document_file', 'Для диспансеризации необходима справка')
        
        if action == 'absent' and reason and not document_type and not document_file:
            self.add_error('document_type', 'Выберите тип документа')
        
        if action == 'overtime' and not hours:
            self.add_error('hours', 'Укажите количество сверхурочных часов')
        
        if action == 'overtime' and hours:
            # Проверка лимита сверхурочных за год
            year = self.date.year if self.date else date.today().year
            tracking, created = OvertimeTracking.objects.get_or_create(
                employee=self.employee,
                year=year,
                defaults={'total_hours': 0}
            )
            
            if not tracking.can_add_hours(hours):
                remaining = 120 - tracking.total_hours
                self.add_error('hours', f'Превышение годового лимита. Можно добавить не более {remaining} часов')
        
        return cleaned_data
    
    def get_attendance_code(self):
        """Получить код для табеля на основе выбранного действия"""
        action = self.cleaned_data.get('action')
        reason = self.cleaned_data.get('reason')
        
        if action == 'absent':
            mapping = {
                'sick': 'B',
                'leave_out_of_schedule': 'OT',
                'dispensary': 'DD',
                'family_reasons': 'OZ',
                'no_show': 'G',
                'business_trip': 'K',
                'training': 'UO',
                'parental_leave': 'DO',
                'other': 'NN',
            }
            return mapping.get(reason, 'NN')
        
        elif action == 'overtime':
            return 'C'
        
        elif action == 'night':
            return 'N'
        
        return 'I'


class TimesheetQuickEditForm(forms.Form):
    """Форма для быстрого редактирования ячейки табеля"""
    
    ABSENCE_REASONS = [
        ('sick', 'Болезнь (больничный)'),
        ('vacation', 'Отпуск'),
        ('dispensary', 'Диспансеризация'),
        ('family_reasons', 'Семейные обстоятельства'),
        ('no_show', 'Прогул'),
        ('business_trip', 'Командировка'),
        ('training', 'Повышение квалификации'),
        ('parental_leave', 'Отпуск по уходу за ребенком'),
        ('other', 'Другое'),
    ]
    
    DOCUMENT_TYPES = [
        ('sick_leave', 'Больничный лист'),
        ('medical_certificate', 'Медицинская справка'),
        ('parent_statement', 'Заявление родителя'),
        ('dispensary_certificate', 'Справка о диспансеризации'),
        ('business_trip_order', 'Приказ о командировке'),
        ('training_certificate', 'Удостоверение о повышении квалификации'),
        ('vacation_application', 'Заявление на отпуск'),
        ('other', 'Другое'),
    ]
    
    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        self.day = kwargs.pop('day', None)
        self.current_code = kwargs.pop('current_code', None)
        self.entry = kwargs.pop('entry', None)
        super().__init__(*args, **kwargs)
        
        # Определяем выбор в зависимости от текущего кода
        if self.current_code in ['I', 'N', 'RV', 'C']:
            self.fields['action'] = forms.ChoiceField(
                choices=[
                    ('', '---'),
                    ('absent', 'Отметить отсутствие'),
                    ('overtime', 'Сверхурочная работа'),
                    ('night', 'Ночная работа'),
                ],
                required=False,
                widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
            )
        else:
            self.fields['action'] = forms.ChoiceField(
                choices=[
                    ('', '---'),
                    ('present', 'Отметить явку'),
                ],
                required=False,
                widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
            )
        
        # Причины отсутствия
        self.fields['reason'] = forms.ChoiceField(
            choices=[('', '---')] + self.ABSENCE_REASONS,
            required=False,
            widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
        )
        
        self.fields['reason_description'] = forms.CharField(
            required=False,
            widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2, 'placeholder': 'Дополнительное описание причины...'}),
            label='Описание причины'
        )
        
        self.fields['hours'] = forms.DecimalField(
            max_digits=4,
            decimal_places=1,
            required=False,
            min_value=0,
            max_value=24,
            widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'часы'})
        )
        
        # Документы
        self.fields['document_type'] = forms.ChoiceField(
            choices=[('', '---')] + self.DOCUMENT_TYPES,
            required=False,
            widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
        )
        
        self.fields['document_file'] = forms.FileField(
            required=False,
            widget=forms.FileInput(attrs={'class': 'form-control form-control-sm', 'accept': '.pdf,.jpg,.png,.jpeg,.doc,.docx'}),
            label='Прикрепить документ'
        )
        
        self.fields['document_number'] = forms.CharField(
            max_length=100,
            required=False,
            widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Номер документа'})
        )
        
        self.fields['document_start_date'] = forms.DateField(
            required=False,
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            label='Дата начала (если период)'
        )
        
        self.fields['document_end_date'] = forms.DateField(
            required=False,
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            label='Дата окончания (если период)'
        )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        reason = cleaned_data.get('reason')
        document_type = cleaned_data.get('document_type')
        document_file = cleaned_data.get('document_file')
        
        if action == 'absent':
            if not reason:
                self.add_error('reason', 'Укажите причину отсутствия')
            
            if reason == 'sick' and not document_file:
                self.add_error('document_file', 'Для отметки болезни необходим подтверждающий документ')
            
            if reason == 'dispensary' and not document_file:
                self.add_error('document_file', 'Для диспансеризации необходима справка')
            
            if reason and document_file and not document_type:
                self.add_error('document_type', 'Выберите тип документа')
        
        return cleaned_data