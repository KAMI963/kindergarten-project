from django import forms
from .models import Menu, WeeklyMenuPlan

class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = [
            'group', 'day_of_week', 'meal_type', 'dish_name', 'description',
            'calories', 'proteins', 'fats', 'carbohydrates', 'weight'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            'meal_type': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'group': 'Группа',
            'day_of_week': 'День недели',
            'meal_type': 'Тип питания',
            'dish_name': 'Название блюда',
            'description': 'Описание',
            'calories': 'Калории',
            'proteins': 'Белки (г)',
            'fats': 'Жиры (г)',
            'carbohydrates': 'Углеводы (г)',
            'weight': 'Вес (г)',
        }

class WeeklyMenuPlanForm(forms.ModelForm):
    class Meta:
        model = WeeklyMenuPlan
        fields = ['group', 'week_start_date']
        widgets = {
            'week_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'group': 'Группа',
            'week_start_date': 'Начало недели',
        }

class MenuApprovalForm(forms.Form):
    is_approved = forms.BooleanField(
        required=False,
        label='Утвердить меню',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    signature = forms.CharField(
        max_length=100,
        required=True,
        label='Подпись',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ФИО заведующей'})
    )
