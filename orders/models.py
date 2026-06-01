# orders/models.py - добавьте поле contract
from django.db import models
from django.urls import reverse
from children.models import Child, Group
from accounts.models import CustomUser
from applications.models import ChildApplication
from contracts.models import EducationContract  # Добавьте импорт
import uuid
from datetime import date

class EnrollmentOrder(models.Model):
    """Модель приказа о зачислении"""
    
    ORDER_TYPES = (
        ('enrollment', 'О зачислении'),
        ('transfer', 'О переводе'),
        ('expulsion', 'Об отчислении'),
    )
    
    ORDER_STATUS_CHOICES = (
        ('draft', 'Черновик'),
        ('issued', 'Издан'),
        ('executed', 'Исполнен'),
    )
    
    # Основная информация
    order_number = models.CharField(max_length=50, unique=True, verbose_name='Номер приказа')
    order_date = models.DateField(default=date.today, verbose_name='Дата приказа')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, default='enrollment', verbose_name='Тип приказа')
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='draft', verbose_name='Статус приказа')
    
    # Связь с договором - ОБЯЗАТЕЛЬНОЕ поле
    contract = models.OneToOneField(
        EducationContract,
        on_delete=models.CASCADE,
        verbose_name='Договор',
        related_name='enrollment_order',
        null=True,  # Временно для совместимости
        blank=True
    )
    
    # Связанные объекты
    child = models.ForeignKey(
        Child, 
        on_delete=models.SET_NULL, 
        verbose_name='Ребенок',
        null=True,  # Будет заполнено при создании
        blank=True
    )
    group = models.ForeignKey(
        Group, 
        on_delete=models.CASCADE, 
        verbose_name='Группа'
    )
    
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        verbose_name='Заведующая',
        related_name='created_orders'
    )
    
    # Связь с заявлением (для обратной совместимости)
    application = models.ForeignKey(
        ChildApplication, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Заявление',
        related_name='enrollment_orders'
    )
    
    # Основание
    basis_documents = models.TextField(
        verbose_name='Основание',
        help_text='Перечень документов, на основании которых издается приказ'
    )
    
    # Дополнительная информация
    enrollment_date = models.DateField(verbose_name='Дата зачисления')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    # Системные поля
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Приказ о зачислении'
        verbose_name_plural = 'Приказы о зачислении'
        ordering = ['-order_date', '-created_at']
    
    def __str__(self):
        if self.child_id and self.child:
            child_name = self.child.full_name
        else:
            child_name = "Ребенок не указан"
        return f"Приказ №{self.order_number} от {self.order_date} - {child_name}"
    
    def get_absolute_url(self):
        return reverse('orders:order_detail', kwargs={'pk': self.pk})
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Генерируем номер приказа
            year = self.order_date.year
            last_order = EnrollmentOrder.objects.filter(
                order_date__year=year
            ).order_by('-id').first()
            
            if last_order and last_order.order_number:
                try:
                    last_num = int(last_order.order_number.split('-')[-1])
                    new_num = last_num + 1
                except:
                    new_num = 1
            else:
                new_num = 1
                
            self.order_number = f"{year}-{new_num:04d}"
        
        # Автоматически устанавливаем заведующую
        if not self.created_by_id:
            director = CustomUser.objects.filter(role='director').first()
            if director:
                self.created_by = director
        
        super().save(*args, **kwargs)
