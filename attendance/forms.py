# attendance/forms.py
from django import forms
from .models import AttendanceSheet, AttendanceRecord, ProductionCalendar, AbsenceDocument
from datetime import date


class AttendanceSheetForm(forms.ModelForm):
    """Форма для создания табеля на месяц"""
    
    class Meta:
        model = AttendanceSheet
        fields = ['group', 'month', 'year']
        widgets = {
            'group': forms.Select(attrs={'class': 'form-select'}),
            'month': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2020, 'max': 2030}),
        }
        labels = {
            'group': 'Группа',
            'month': 'Месяц',
            'year': 'Год',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = date.today().year
        
        month_choices = [
            (1, 'Январь'), (2, 'Февраль'), (3, 'Март'),
            (4, 'Апрель'), (5, 'Май'), (6, 'Июнь'),
            (7, 'Июль'), (8, 'Август'), (9, 'Сентябрь'),
            (10, 'Октябрь'), (11, 'Ноябрь'), (12, 'Декабрь')
        ]
        self.fields['month'].widget = forms.Select(choices=month_choices, attrs={'class': 'form-select'})
        
        year_choices = [(year, str(year)) for year in range(current_year - 1, current_year + 2)]
        self.fields['year'].widget = forms.Select(choices=year_choices, attrs={'class': 'form-select'})


class AttendanceRecordForm(forms.ModelForm):
    """Форма для отметки посещаемости ребенка за месяц"""
    
    class Meta:
        model = AttendanceRecord
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        sheet = kwargs.pop('sheet', None)
        super().__init__(*args, **kwargs)
        
        if sheet:
            total_days = sheet.get_total_days()
            status_choices = [
                ('', '-'),
                ('present', 'Я'),
                ('absent', 'Н'),
                ('sick', 'НБ'),
                ('vacation', 'НУ'),
            ]
            
            for day in range(1, total_days + 1):
                field_name = f'day_{day}'
                initial_status = getattr(self.instance, field_name, '') if self.instance else ''
                
                self.fields[field_name] = forms.ChoiceField(
                    choices=status_choices,
                    initial=initial_status,
                    widget=forms.Select(attrs={
                        'class': 'form-select form-select-sm day-status',
                        'data-day': day
                    }),
                    label=f'День {day}',
                    required=False
                )


class ProductionCalendarForm(forms.ModelForm):
    """Форма для производственного календаря"""
    
    class Meta:
        model = ProductionCalendar
        fields = ['date', 'is_holiday', 'holiday_name', 'is_working_saturday']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'holiday_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название праздника'}),
            'is_holiday': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_working_saturday': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'date': 'Дата',
            'is_holiday': 'Выходной/праздничный день',
            'holiday_name': 'Название праздника',
            'is_working_saturday': 'Рабочая суббота',
        }


class BulkProductionCalendarForm(forms.Form):
    """Массовое заполнение производственного календаря"""
    year = forms.IntegerField(label='Год', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    auto_generate_weekends = forms.BooleanField(
        required=False, 
        label='Автоматически отметить все субботы и воскресенья',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    
class AbsenceDocumentForm(forms.ModelForm):
    """Форма для загрузки документов о болезни/отпуске"""
    
    class Meta:
        model = AbsenceDocument
        fields = ['document_type', 'document_file', 'document_number', 'issue_date', 'start_date', 'end_date', 'description']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'document_file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.png'}),
            'document_number': forms.TextInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
