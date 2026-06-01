# communication/forms.py

from django import forms
from django.contrib.auth import get_user_model
from .models import Message
from children.models import Child
from accounts.models import ParentProfile

User = get_user_model()

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content', 'file']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control message-input',
                'placeholder': 'Введите сообщение...',
                'rows': 1,
                'style': 'resize: none;'
            }),
            'file': forms.FileInput(attrs={
                'class': 'd-none',
                'id': 'file-input'
            })
        }
        labels = {
            'content': '',
            'file': ''
        }

class NewConversationForm(forms.Form):
    recipient = forms.ChoiceField(
        choices=[],
        label='Выберите получателя',
        widget=forms.Select(attrs={'class': 'form-select-custom'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        choices = []
        
        if user and user.role == 'teacher':
            # Воспитатель - родители его детей + заведующая
            from children.models import Group
            groups = Group.objects.filter(teacher=user)
            for group in groups:
                children = Child.objects.filter(group=group, is_active=True)
                for child in children:
                    parents = child.parent_relations.all()
                    for child_parent in parents:
                        choices.append(
                            (f'parent_{child_parent.parent.id}_{child.id}', 
                             f"👪 {child_parent.parent.user.get_full_name()} ({child.full_name})")
                        )
            
            # Заведующая
            directors = User.objects.filter(role='director')
            for director in directors:
                choices.append(
                    (f'director_{director.id}', 
                     f"👩‍💼 {director.get_full_name()} (Заведующая)")
                )
        
        elif user and user.role == 'parent':
            # Родитель - воспитатели его детей + заведующая
            children = Child.objects.filter(parent_relations__parent__user=user, is_active=True)
            for child in children:
                if child.group and child.group.teacher:
                    choices.append(
                        (f'teacher_{child.group.teacher.id}_{child.id}',
                         f"👩‍🏫 {child.group.teacher.get_full_name()} (Воспитатель {child.full_name})")
                    )
            
            # Заведующая
            directors = User.objects.filter(role='director')
            for director in directors:
                choices.append(
                    (f'director_{director.id}',
                     f"👩‍💼 {director.get_full_name()} (Заведующая)")
                )
        
        elif user and user.role == 'director':
            # Заведующая - все воспитатели + все родители
            teachers = User.objects.filter(role='teacher')
            for teacher in teachers:
                choices.append(
                    (f'teacher_{teacher.id}', 
                     f"👩‍🏫 {teacher.get_full_name()} (Воспитатель)")
                )
            
            parents = ParentProfile.objects.all()
            for parent in parents:
                choices.append(
                    (f'parent_{parent.id}', 
                     f"👪 {parent.user.get_full_name()} (Родитель)")
                )
        
        self.fields['recipient'].choices = choices