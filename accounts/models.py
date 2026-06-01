# accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
from datetime import timedelta

class CustomUser(AbstractUser):
    email = models.EmailField(blank=True, null=True, unique=False)
    
    ROLE_CHOICES = (
        ('director', 'Заведующая'),
        ('teacher', 'Воспитатель'),
        ('parent', 'Родитель'),
    )
    
    GENDER_CHOICES = (
        ('male', 'Мужской'),
        ('female', 'Женский'),
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True, verbose_name='Пол')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='user_photos/', blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def get_full_name(self):
        return f"{self.last_name} {self.first_name}".strip() or self.username


class EmailVerificationCode(models.Model):
    """Модель для хранения кодов подтверждения email"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='email_verification_codes')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Код подтверждения email'
        verbose_name_plural = 'Коды подтверждения email'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Код для {self.user.email}: {self.code}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        """Проверяет, действителен ли код"""
        return not self.is_used and self.expires_at > timezone.now()


class PasswordResetCode(models.Model):
    """Модель для хранения кодов восстановления пароля"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='password_reset_codes')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Код восстановления пароля'
        verbose_name_plural = 'Коды восстановления пароля'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Код восстановления для {self.user.email}: {self.code}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        """Проверяет, действителен ли код"""
        return not self.is_used and self.expires_at > timezone.now()


class UserLoginLog(models.Model):
    """Лог входов пользователей"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='login_logs')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    login_time = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Лог входа'
        verbose_name_plural = 'Логи входов'
        ordering = ['-login_time']
    
    def __str__(self):
        return f"{self.user.email} - {self.login_time}"


class ParentProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='parentprofile')
    
    # Существующие поля (для обратной совместимости)
    passport_series = models.CharField(max_length=4, blank=True, default='')
    passport_number = models.CharField(max_length=6, blank=True, default='')
    passport_issued_by = models.TextField(blank=True, default='')
    passport_issue_date = models.DateField(null=True, blank=True)
    registration_address = models.TextField(blank=True, default='')
    actual_address = models.TextField(blank=True, default='')
    photo = models.ImageField(
        upload_to='parent_photos/',
        blank=True,
        null=True,
        verbose_name='Фотография родителя'
    )
    
    # Флаг заполнения начальной анкеты
    has_completed_initial_profile = models.BooleanField(
        default=False, 
        verbose_name='Заполнил начальную анкету'
    )
    
    # Новые поля для анкеты родителя
    is_primary_parent = models.BooleanField(default=True, verbose_name='Основной родитель')
    primary_parent_full_name = models.CharField(max_length=200, blank=True, verbose_name='ФИО основного родителя')
    
    # Основные сведения
    full_name = models.CharField(max_length=200, blank=True, verbose_name='ФИО родителя')
    birth_date = models.DateField(null=True, blank=True, verbose_name='Дата рождения')
    nationality = models.CharField(max_length=100, blank=True, verbose_name='Национальность')
    
    # Социальные условия
    address_same_as_registration = models.BooleanField(default=True, verbose_name='Совпадает с адресом прописки')
    
    # Телефоны
    mobile_phone = models.CharField(max_length=20, blank=True, verbose_name='Мобильный телефон')
    home_phone = models.CharField(max_length=20, blank=True, verbose_name='Домашний телефон')
    work_phone = models.CharField(max_length=20, blank=True, verbose_name='Рабочий телефон')
    
    # Место работы
    workplace = models.CharField(max_length=200, blank=True, verbose_name='Место работы')
    position = models.CharField(max_length=100, blank=True, verbose_name='Должность')
    not_working = models.BooleanField(default=False, verbose_name='Не работаю')
    
    # Статус заполнения анкеты
    profile_completed = models.BooleanField(default=False, verbose_name='Анкета заполнена')
    completed_tabs = models.JSONField(default=list, verbose_name='Заполненные вкладки')
    
    
    def get_siblings_in_kindergarten(self):
        """Возвращает детей этого родителя, которые уже посещают детский сад"""
        from children.models import ChildParent, Child
        # Получаем всех детей родителя
        child_parents = ChildParent.objects.filter(parent=self)
        children_ids = child_parents.values_list('child_id', flat=True)
        
        # Фильтруем тех, кто уже в группе (посещает сад)
        siblings = Child.objects.filter(
            id__in=children_ids,
            group__isnull=False,  # Есть назначенная группа
            is_active=True
        )
        return siblings
    
    class Meta:
        verbose_name = 'Профиль родителя'
        verbose_name_plural = 'Профили родителей'
    
    def __str__(self):
        return f"Профиль родителя: {self.user.get_full_name() or self.full_name or self.user.username}"
    
    def get_full_name(self):
        """Возвращает ФИО родителя"""
        return self.full_name or self.user.get_full_name()
    
    def get_completed_tabs_count(self):
        """Возвращает количество заполненных вкладок"""
        return len(self.completed_tabs) if self.completed_tabs else 0
    
    def mark_tab_completed(self, tab_number):
        """Отмечает вкладку как заполненную"""
        if not self.completed_tabs:
            self.completed_tabs = []
        if tab_number not in self.completed_tabs:
            self.completed_tabs.append(tab_number)
            self.save(update_fields=['completed_tabs'])
    
    def mark_tab_incomplete(self, tab_number):
        """Отмечает вкладку как незаполненную"""
        if self.completed_tabs and tab_number in self.completed_tabs:
            self.completed_tabs.remove(tab_number)
            self.save(update_fields=['completed_tabs'])
    
    def save(self, *args, **kwargs):
        # Если адрес проживания не указан и флаг совпадения включен, копируем адрес регистрации
        if self.address_same_as_registration and not self.actual_address:
            self.actual_address = self.registration_address
        super().save(*args, **kwargs)


class TeacherProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='teacherprofile')
    education = models.TextField(blank=True, default='')
    specialization = models.CharField(max_length=100, blank=True, default='')
    experience = models.IntegerField(default=0)
    hire_date = models.DateField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Профиль воспитателя'
        verbose_name_plural = 'Профили воспитателей'
    
    def __str__(self):
        return f"Профиль воспитателя: {self.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.education:
            self.education = ''
        if not self.specialization:
            self.specialization = ''
        super().save(*args, **kwargs)


class DirectorProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='directorprofile')
    education = models.TextField(blank=True, default='')
    management_experience = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'Профиль заведующей'
        verbose_name_plural = 'Профили заведующих'
    
    def __str__(self):
        return f"Профиль заведующей: {self.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.education:
            self.education = ''
        super().save(*args, **kwargs)