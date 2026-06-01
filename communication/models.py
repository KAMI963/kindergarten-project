from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from children.models import Child
from accounts.models import ParentProfile
import os

User = get_user_model()

class Conversation(models.Model):
    CONVERSATION_TYPES = [
        ('teacher_parent', 'Воспитатель-Родитель'),
        ('teacher_director', 'Воспитатель-Заведующая'),
        ('director_parent', 'Заведующая-Родитель'),
    ]
    
    conversation_type = models.CharField(max_length=20, choices=CONVERSATION_TYPES)
    teacher = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        limit_choices_to={'role': 'teacher'},
        related_name='teacher_conversations'
    )
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, null=True, blank=True)
    director = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        limit_choices_to={'role': 'director'},
        related_name='director_conversations'
    )
    child = models.ForeignKey(Child, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [
            ['teacher', 'parent', 'child'],
            ['teacher', 'director'],
            ['director', 'parent']
        ]
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.conversation_type == 'teacher_parent':
            return f"Чат: {self.teacher.get_full_name()} - {self.parent.user.get_full_name()} ({self.child})"
        elif self.conversation_type == 'teacher_director':
            return f"Чат: {self.teacher.get_full_name()} - {self.director.get_full_name()}"
        elif self.conversation_type == 'director_parent':
            return f"Чат: {self.director.get_full_name()} - {self.parent.user.get_full_name()}"
    
    def get_absolute_url(self):
        return f"{reverse('communication:dashboard')}?conversation={self.id}"
    
    
    def get_display_name(self, current_user):
        """Получить отображаемое имя чата для текущего пользователя"""
        if current_user.role == 'teacher':
            if self.parent:
                if self.child:
                    return f"{self.parent.user.get_full_name()} ({self.child.full_name})"
                return self.parent.user.get_full_name()
            elif self.director:
                return self.director.get_full_name()
        
        elif current_user.role == 'parent':
            if self.teacher:
                if self.child:
                    return self.teacher.get_full_name()
                return self.teacher.get_full_name()
            elif self.director:
                return self.director.get_full_name()
        
        elif current_user.role == 'director':
            if self.teacher:
                return f"{self.teacher.get_full_name()} (Воспитатель)"
            elif self.parent:
                if self.child:
                    return f"{self.parent.user.get_full_name()} ({self.child.full_name})"
                return self.parent.user.get_full_name()
        
        return "Чат"


def message_file_path(instance, filename):
    """Генерация пути для сохранения файла"""
    return f'communication/messages/{instance.conversation.id}/{filename}'


class Message(models.Model):
    FILE_TYPES = [
        ('image', 'Изображение'),
        ('document', 'Документ'),
        ('other', 'Другое'),
    ]
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to=message_file_path, blank=True, null=True)
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='other')
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.IntegerField(blank=True, null=True)  # размер в байтах
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        if self.content:
            return f"{self.sender.username}: {self.content[:50]}"
        else:
            return f"{self.sender.username}: [Файл] {self.file_name}"
    
    def get_file_icon(self):
        """Возвращает иконку для файла"""
        if self.file_type == 'image':
            return 'fas fa-image'
        elif self.file_type == 'document':
            if self.file_name:
                ext = self.file_name.split('.')[-1].lower()
                if ext == 'pdf':
                    return 'fas fa-file-pdf'
                elif ext in ['doc', 'docx']:
                    return 'fas fa-file-word'
                elif ext in ['xls', 'xlsx']:
                    return 'fas fa-file-excel'
                elif ext in ['ppt', 'pptx']:
                    return 'fas fa-file-powerpoint'
                elif ext in ['zip', 'rar', '7z']:
                    return 'fas fa-file-archive'
            return 'fas fa-file-alt'
        else:
            return 'fas fa-paperclip'
    
    def get_file_size_display(self):
        """Возвращает читаемый размер файла"""
        if not self.file_size:
            return ''
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} ТБ"