# children/forms.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

from django import forms
from django.utils import timezone
from datetime import date
from .models import Child, Group, ChildParent, PersonalFile, DocumentCheckHistory
from accounts.models import CustomUser, ParentProfile


class ChildForm(forms.ModelForm):
    class Meta:
        model = Child
        fields = [
            'full_name', 'birth_date', 'gender', 'group',
            'birth_certificate', 'birth_certificate_issued_by', 'birth_certificate_issue_date',
            'medical_card_number', 'policy_oms_number', 'snils',
            'registration_address', 'actual_address',
            'blood_type', 'allergies', 'chronic_diseases', 'special_needs', 'disability_certificate',
            'is_active', 'photo'
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'birth_certificate_issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'registration_address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'actual_address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'allergies': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'chronic_diseases': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'special_needs': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'full_name': 'ФИО ребенка',
            'birth_date': 'Дата рождения',
            'gender': 'Пол',
            'group': 'Группа',
            'birth_certificate': 'Свидетельство о рождении',
            'birth_certificate_issued_by': 'Кем выдано свидетельство',
            'birth_certificate_issue_date': 'Дата выдачи свидетельства',
            'medical_card_number': 'Номер медицинской карты',
            'policy_oms_number': 'Полис ОМС',
            'snils': 'СНИЛС',
            'registration_address': 'Адрес регистрации',
            'actual_address': 'Фактический адрес проживания',
            'blood_type': 'Группа крови',
            'allergies': 'Аллергии',
            'chronic_diseases': 'Хронические заболевания',
            'special_needs': 'Особые потребности',
            'disability_certificate': 'Справка об инвалидности',
            'is_active': 'Активен в системе',
            'photo': 'Фотография',
        }


class ChildParentForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=ParentProfile.objects.all(),
        label='Родитель',
        required=True
    )
    
    class Meta:
        model = ChildParent
        fields = ['parent', 'relation', 'is_primary']
        labels = {
            'parent': 'Родитель',
            'relation': 'Родство',
            'is_primary': 'Основной контакт',
        }
        widgets = {
            'relation': forms.Select(attrs={'class': 'form-select'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ChildCreateForm(forms.ModelForm):
    class Meta:
        model = Child
        fields = [
            'full_name', 'birth_date', 'gender',
            'birth_certificate', 'birth_certificate_issued_by', 'birth_certificate_issue_date',
            'registration_address', 'actual_address',
            'blood_type', 'allergies', 'chronic_diseases', 'special_needs'
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'birth_certificate_issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'registration_address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'actual_address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'allergies': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'chronic_diseases': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'special_needs': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
        }


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'age_category', 'teacher', 'capacity', 'room_number']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: Младшая группа №1'}),
            'age_category': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: 101'}),
        }
        labels = {
            'name': 'Название группы',
            'age_category': 'Возрастная категория',
            'teacher': 'Воспитатель',
            'capacity': 'Вместимость',
            'room_number': 'Номер комнаты',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = CustomUser.objects.filter(role='teacher')


# ==================== НОВЫЕ ФОРМЫ ДЛЯ ЛИЧНЫХ ДЕЛ ====================

class PersonalFileForm(forms.ModelForm):
    """Форма для личного дела с контролем сроков"""
    
    class Meta:
        model = PersonalFile
        fields = [
            'registration_expiry_date', 'medical_card_expiry_date', 'policy_expiry_date',
            'additional_documents', 'status'
        ]
        widgets = {
            'registration_expiry_date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control'
            }),
            'medical_card_expiry_date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control'
            }),
            'policy_expiry_date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control'
            }),
            'additional_documents': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4, 'placeholder': 'Перечень дополнительных документов (каждый с новой строки)'
            }),
            'status': forms.Select(attrs={'class': 'form-select'})
        }
        labels = {
            'registration_expiry_date': 'Срок действия регистрации',
            'medical_card_expiry_date': 'Срок действия медкарты',
            'policy_expiry_date': 'Срок действия полиса ОМС',
            'additional_documents': 'Дополнительные документы',
            'status': 'Статус дела',
        }


class ChildConsentForm(forms.ModelForm):
    """Форма для согласий"""
    
    class Meta:
        model = Child
        fields = [
            'consent_data_processing', 'consent_photo_video', 'consent_medical_intervention'
        ]
        widgets = {
            'consent_data_processing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consent_photo_video': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consent_medical_intervention': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'consent_data_processing': 'Согласие на обработку персональных данных',
            'consent_photo_video': 'Согласие на фото- и видеосъемку',
            'consent_medical_intervention': 'Согласие на медицинское вмешательство',
        }
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Автоматически проставляем даты подписания
        if self.cleaned_data.get('consent_data_processing') and not instance.consent_data_processing_date:
            instance.consent_data_processing_date = date.today()
        if self.cleaned_data.get('consent_photo_video') and not instance.consent_photo_video_date:
            instance.consent_photo_video_date = date.today()
        if self.cleaned_data.get('consent_medical_intervention') and not instance.consent_medical_intervention_date:
            instance.consent_medical_intervention_date = date.today()
        
        if commit:
            instance.save()
        return instance


class DocumentCheckForm(forms.ModelForm):
    """Форма для проверки документов"""
    
    class Meta:
        model = DocumentCheckHistory
        fields = ['registration_valid', 'medical_valid', 'policy_valid', 'notes']
        widgets = {
            'registration_valid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'medical_valid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'policy_valid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Замечания по проверке...'}),
        }
        labels = {
            'registration_valid': 'Регистрация действительна',
            'medical_valid': 'Медкарта действительна',
            'policy_valid': 'Полис действителен',
            'notes': 'Примечания',
        }


class ChildMedicalForm(forms.ModelForm):
    """Форма для медицинских данных ребенка"""
    
    class Meta:
        model = Child
        fields = [
            'blood_type', 'allergies', 'chronic_diseases', 'special_needs',
            'disability_certificate', 'medical_card_number', 'medical_card_file'
        ]
        widgets = {
            'blood_type': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('', '---------'),
                ('I+', 'I (0) Rh+'),
                ('I-', 'I (0) Rh-'),
                ('II+', 'II (A) Rh+'),
                ('II-', 'II (A) Rh-'),
                ('III+', 'III (B) Rh+'),
                ('III-', 'III (B) Rh-'),
                ('IV+', 'IV (AB) Rh+'),
                ('IV-', 'IV (AB) Rh-'),
            ]),
            'allergies': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Укажите аллергии (если есть)'}),
            'chronic_diseases': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Укажите хронические заболевания (если есть)'}),
            'special_needs': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Укажите особые потребности (если есть)'}),
            'disability_certificate': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер справки об инвалидности'}),
            'medical_card_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер медицинской карты'}),
            'medical_card_file': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'blood_type': 'Группа крови',
            'allergies': 'Аллергии',
            'chronic_diseases': 'Хронические заболевания',
            'special_needs': 'Особые потребности',
            'disability_certificate': 'Справка об инвалидности',
            'medical_card_number': 'Номер медицинской карты',
            'medical_card_file': 'Файл медкарты',
        }


class ChildDocumentsForm(forms.ModelForm):
    """Форма для документов ребенка"""
    
    class Meta:
        model = Child
        fields = [
            'birth_certificate', 'birth_certificate_issued_by', 'birth_certificate_issue_date',
            'snils', 'policy_oms_number', 'registration_certificate', 'registration_issued_date'
        ]
        widgets = {
            'birth_certificate': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: III-АМ 123456'}),
            'birth_certificate_issued_by': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Кем выдано свидетельство'}),
            'birth_certificate_issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'snils': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123-456-789 01'}),
            'policy_oms_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Номер полиса ОМС'}),
            'registration_certificate': forms.FileInput(attrs={'class': 'form-control'}),
            'registration_issued_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        labels = {
            'birth_certificate': 'Свидетельство о рождении',
            'birth_certificate_issued_by': 'Кем выдано',
            'birth_certificate_issue_date': 'Дата выдачи',
            'snils': 'СНИЛС',
            'policy_oms_number': 'Полис ОМС',
            'registration_certificate': 'Свидетельство о регистрации (файл)',
            'registration_issued_date': 'Дата выдачи регистрации',
        }
