from django.db import models
from accounts.models import CustomUser


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('invite', 'Приглашение на оформление'),
        ('status', 'Изменение статуса'),
        ('enrollment', 'Зачисление'),
        ('info', 'Информация'),
        ('warning', 'Предупреждение'),
    )
    
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        verbose_name='Пользователь'
    )
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    message = models.TextField(verbose_name='Сообщение')
    notification_type = models.CharField(
        max_length=20, 
        choices=NOTIFICATION_TYPES, 
        default='info',
        verbose_name='Тип уведомления'
    )
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    link = models.CharField(max_length=200, blank=True, null=True, verbose_name='Ссылка')
    related_object_id = models.IntegerField(blank=True, null=True, verbose_name='ID связанного объекта')
    related_object_type = models.CharField(max_length=50, blank=True, null=True, verbose_name='Тип связанного объекта')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
    
    def __str__(self):
        return f"{self.title} - {self.user.get_full_name() or self.user.username}"