# contracts/forms.py
from django import forms
from django.utils import timezone
from .models import EducationContract, ContractRegistry
from children.models import Child, Group
from accounts.models import ParentProfile
from applications.models import ChildApplication
from datetime import date

class EducationContractForm(forms.ModelForm):
    """Форма создания/редактирования договора"""
    
    class Meta:
        model = EducationContract
        fields = [
            'child', 'parent', 'enrollment_date', 'group_name',
            'contract_start_date', 'contract_end_date',
            'educational_program', 'study_period', 'stay_regimen',
            'parent_fee', 'subscription_fee', 'food_fee',
            'basis_documents', 'notes', 'status'
        ]
        widgets = {
            'enrollment_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'contract_start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'contract_end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'educational_program': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'stay_regimen': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: пятидневная неделя, 12 часов'
            }),
            'basis_documents': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'На основании: заявления родителей, направления, медицинского заключения...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'group_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Младшая группа №1'
            }),
            'parent_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'subscription_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'food_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'study_period': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '7'
            }),
            'child': forms.Select(attrs={
                'class': 'form-select'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
        labels = {
            'child': 'Воспитанник*',
            'parent': 'Родитель (законный представитель)*',
            'enrollment_date': 'Дата зачисления*',
            'group_name': 'Наименование группы*',
            'contract_start_date': 'Дата заключения договора*',
            'contract_end_date': 'Дата окончания договора',
            'educational_program': 'Образовательная программа',
            'study_period': 'Срок освоения программы (лет)*',
            'stay_regimen': 'Режим пребывания*',
            'parent_fee': 'Родительская плата (всего)*',
            'subscription_fee': 'Абонентская плата*',
            'food_fee': 'Питание*',
            'basis_documents': 'Основание*',
            'notes': 'Примечания',
            'status': 'Статус договора',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Ограничиваем выбор детей только активными
        self.fields['child'].queryset = Child.objects.filter(is_active=True)
        
        # Ограничиваем выбор родителей
        self.fields['parent'].queryset = ParentProfile.objects.all()
        
        # Устанавливаем значения по умолчанию
        if not self.instance.pk:
            self.fields['contract_start_date'].initial = date.today()
            self.fields['study_period'].initial = 5
            self.fields['stay_regimen'].initial = 'пятидневная неделя (понедельник – пятница), 12 часов (с 6.00 до 18.00)'
            self.fields['educational_program'].initial = 'Основная общеобразовательная программа дошкольного образования муниципального бюджетного дошкольного образовательного учреждения Карабашский детский сад общеразвивающего вида №1 «Рябинушка» Бугульминского муниципального района Республики Татарстан'
    
    def clean(self):
        cleaned_data = super().clean()
        enrollment_date = cleaned_data.get('enrollment_date')
        contract_start_date = cleaned_data.get('contract_start_date')
        contract_end_date = cleaned_data.get('contract_end_date')
        
        # Проверка, что дата зачисления не раньше даты заключения договора
        if enrollment_date and contract_start_date and enrollment_date < contract_start_date:
            raise forms.ValidationError('Дата зачисления не может быть раньше даты заключения договора.')
        
        # Проверка даты окончания (если указана)
        if contract_end_date and contract_start_date and contract_end_date < contract_start_date:
            raise forms.ValidationError('Дата окончания договора не может быть раньше даты начала.')
        
        # Проверка сумм
        parent_fee = cleaned_data.get('parent_fee')
        subscription_fee = cleaned_data.get('subscription_fee')
        food_fee = cleaned_data.get('food_fee')
        
        if parent_fee and subscription_fee and food_fee:
            if abs(parent_fee - (subscription_fee + food_fee)) > 0.01:  # Допустимая погрешность
                raise forms.ValidationError('Родительская плата должна равняться сумме абонентской платы и платы за питание.')
        
        return cleaned_data


class ContractFromApplicationForm(forms.Form):
    """
    Форма для создания договора из заявления (Этап 3)
    """
    enrollment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Планируемая дата зачисления*',
        initial=date.today
    )
    
    group_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: Младшая группа №1'
        }),
        label='Планируемая группа*'
    )
    
    contract_start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Дата заключения договора*',
        initial=date.today
    )
    
    study_period = forms.IntegerField(
        min_value=1,
        max_value=7,
        initial=5,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Срок освоения программы (лет)*'
    )
    
    stay_regimen = forms.CharField(
        max_length=200,
        initial='пятидневная неделя (понедельник – пятница), 12 часов (с 6.00 до 18.00)',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Режим пребывания*'
    )
    
    # ДОБАВЬТЕ ЭТО ПОЛЕ
    educational_program = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3
        }),
        label='Образовательная программа',
        required=False,
        initial='Основная общеобразовательная программа дошкольного образования муниципального бюджетного дошкольного образовательного учреждения Карабашский детский сад общеразвивающего вида №1 «Рябинушка» Бугульминского муниципального района Республики Татарстан'
    )
    
    parent_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'id': 'id_parent_fee'
        }),
        label='Родительская плата (всего)*'
    )
    
    subscription_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'id': 'id_subscription_fee'
        }),
        label='Абонентская плата*'
    )
    
    food_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'id': 'id_food_fee'
        }),
        label='Питание*'
    )
    
    basis_documents = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'На основании: заявления родителей, свидетельства о рождении, медицинской карты...'
        }),
        label='Основание*'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Импортируем модель внутри метода, чтобы избежать циклических импортов
        from applications.models import ChildApplication
        
        # Устанавливаем queryset для заявлений со статусом 'approved' или 'enrolled'
        # Исключаем заявления, по которым уже есть договоры
        self.fields['application'] = forms.ModelChoiceField(
            queryset=ChildApplication.objects.filter(
                status='queue'
            ).exclude(
                id__in=EducationContract.objects.filter(
                    application__isnull=False
                ).values_list('application_id', flat=True)
            ).order_by('-created_at'),
            widget=forms.Select(attrs={
                'class': 'form-select',
                'id': 'application_select'
            }),
            label='Выберите заявление*',
            empty_label="-- Выберите заявление --"
        )
    
    def clean(self):
        cleaned_data = super().clean()
        parent_fee = cleaned_data.get('parent_fee')
        subscription_fee = cleaned_data.get('subscription_fee')
        food_fee = cleaned_data.get('food_fee')
        
        if parent_fee and subscription_fee and food_fee:
            if abs(parent_fee - (subscription_fee + food_fee)) > 0.01:
                raise forms.ValidationError('Родительская плата должна равняться сумме абонентской платы и платы за питание')
        
        return cleaned_data


class EducationContractForm(forms.ModelForm):
    """
    Форма редактирования договора
    """
    class Meta:
        model = EducationContract
        fields = [
            'group_name', 'enrollment_date', 'contract_start_date', 'contract_end_date',
            'educational_program', 'study_period', 'stay_regimen',
            'parent_fee', 'subscription_fee', 'food_fee',
            'basis_documents', 'notes', 'status'
        ]
        widgets = {
            'enrollment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'contract_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'contract_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'educational_program': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'stay_regimen': forms.TextInput(attrs={'class': 'form-control'}),
            'basis_documents': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'group_name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'subscription_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'food_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'study_period': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

class ContractRegistryForm(forms.ModelForm):
    """Форма для реестра договоров"""
    
    class Meta:
        model = ContractRegistry
        fields = [
            'has_additional_agreements',
            'additional_agreements_info',
            'last_check_date',
            'check_notes',
            'storage_location'
        ]
        widgets = {
            'has_additional_agreements': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'additional_agreements_info': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'last_check_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'check_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'storage_location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Личное дело воспитанника'
            }),
        }
        labels = {
            'has_additional_agreements': 'Есть дополнительные соглашения',
            'additional_agreements_info': 'Информация о дополнительных соглашениях',
            'last_check_date': 'Дата последней проверки',
            'check_notes': 'Замечания при проверке',
            'storage_location': 'Место хранения',
        }
