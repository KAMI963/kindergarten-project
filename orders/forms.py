from django import forms
from django.utils import timezone
from datetime import date
from .models import EnrollmentOrder
from children.models import Child, Group
from applications.models import ChildApplication

class GroupedBulkEnrollmentForm(forms.Form):
    """Форма для массового создания приказов с выбором группы"""
    
    group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'group_select',
            'onchange': 'loadApplicationsForGroup()'
        }),
        label='Выберите группу*',
        empty_label="-- Выберите группу --"
    )
    
    order_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='Дата приказа*',
        initial=date.today
    )
    
    enrollment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control'
        }),
        label='Дата зачисления*',
        initial=date.today
    )
    
    basis_documents = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'На основании: заявления родителей, свидетельства о рождении, медицинской карты...'
        }),
        label='Основание*',
        initial='На основании заявления родителей, свидетельства о рождении, медицинской карты'
    )
    
    # ИСПРАВЛЕНИЕ: Используем ModelMultipleChoiceField вместо MultipleChoiceField
    applications = forms.ModelMultipleChoiceField(
        queryset=ChildApplication.objects.none(),  # Пустой queryset, будет заполняться динамически
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input application-checkbox'
        }),
        label='Выберите заявления для зачисления'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Показываем все группы
        self.fields['group'].queryset = Group.objects.all()

class EnrollmentOrderForm(forms.ModelForm):
    """Форма создания/редактирования приказа о зачислении"""
    
    class Meta:
        model = EnrollmentOrder
        fields = ['order_date', 'enrollment_date', 'child', 'group', 'basis_documents', 'notes']
        widgets = {
            'order_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'enrollment_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'child': forms.Select(attrs={
                'class': 'form-select'
            }),
            'group': forms.Select(attrs={
                'class': 'form-select'
            }),
            'basis_documents': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }
        labels = {
            'order_date': 'Дата приказа*',
            'enrollment_date': 'Дата зачисления*',
            'child': 'Ребенок*',
            'group': 'Группа*',
            'basis_documents': 'Основание*',
            'notes': 'Примечания',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Ограничиваем выбор детей только теми, кто еще не имеет активного приказа о зачислении
        if self.instance.pk is None:  # Только для новых приказов
            children_with_orders = EnrollmentOrder.objects.filter(
                is_active=True
            ).values_list('child_id', flat=True)
            self.fields['child'].queryset = Child.objects.exclude(
                id__in=children_with_orders
            ).filter(is_active=True)
        else:
            self.fields['child'].queryset = Child.objects.filter(is_active=True)
        
        self.fields['group'].queryset = Group.objects.all()
