# lessons/forms.py
from django import forms
from .models import LessonPlan, LessonSchedule, LessonReminder, ActivityTemplate
from children.models import Group

class LessonPlanForm(forms.ModelForm):
    class Meta:
        model = LessonPlan
        fields = [
            'title', 'lesson_type', 'group', 'description', 'objectives',
            'materials', 'duration', 'difficulty', 'age_appropriate',
            'planned_date', 'planned_time'
        ]
        widgets = {
            'planned_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'planned_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'objectives': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'materials': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'lesson_type': forms.Select(attrs={'class': 'form-select'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'max': '120'}),
        }
        labels = {
            'title': 'Название занятия',
            'lesson_type': 'Тип занятия',
            'group': 'Группа',
            'description': 'Описание занятия',
            'objectives': 'Цели и задачи',
            'materials': 'Необходимые материалы',
            'duration': 'Продолжительность (мин)',
            'difficulty': 'Сложность',
            'age_appropriate': 'Соответствует возрасту',
            'planned_date': 'Планируемая дата',
            'planned_time': 'Планируемое время',
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and user.role == 'teacher':
            # Ограничиваем выбор групп только теми, где пользователь воспитатель
            self.fields['group'].queryset = Group.objects.filter(teacher=user)

class LessonCompleteForm(forms.ModelForm):
    class Meta:
        model = LessonPlan
        fields = ['actual_date', 'actual_time', 'notes', 'success_rate']
        widgets = {
            'actual_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'actual_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'success_rate': forms.NumberInput(attrs={
                'class': 'form-control', 
                'min': '1', 
                'max': '5',
                'placeholder': 'Оценка от 1 до 5'
            }),
        }

class LessonScheduleForm(forms.ModelForm):
    class Meta:
        model = LessonSchedule
        fields = ['group', 'day_of_week', 'start_time', 'end_time', 'activity_type', 'description', 'is_regular']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'activity_type': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'day_of_week': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
        }

class LessonReminderForm(forms.ModelForm):
    class Meta:
        model = LessonReminder
        fields = ['title', 'reminder_type', 'group', 'description', 'due_date', 'due_time', 'priority', 'lesson_plan']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'reminder_type': forms.Select(attrs={'class': 'form-select'}),
            'group': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'lesson_plan': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Ограничиваем выбор планов занятий и групп для текущего пользователя
            self.fields['lesson_plan'].queryset = LessonPlan.objects.filter(teacher=user)
            if user.role == 'teacher':
                self.fields['group'].queryset = Group.objects.filter(teacher=user)

class ActivityTemplateForm(forms.ModelForm):
    class Meta:
        model = ActivityTemplate
        fields = [
            'title', 'description', 'age_group', 'lesson_type', 
            'objectives', 'materials', 'duration', 'steps', 'variations', 'is_public'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'objectives': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'materials': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'steps': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'variations': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'age_group': forms.Select(attrs={'class': 'form-select'}),
            'lesson_type': forms.Select(attrs={'class': 'form-select'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'min': '5'}),
        }
