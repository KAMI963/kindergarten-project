# children/models.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

from django.db import models
from django.utils import timezone
from datetime import date, timedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import CustomUser, ParentProfile
import os


def child_photo_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f'profile_photo.{ext}'
    return os.path.join('photos', 'children', str(instance.id), filename)


# ==================== СНАЧАЛА ОПРЕДЕЛЯЕМ PersonalFile ====================

class PersonalFile(models.Model):
    """Личное дело воспитанника - расширенная модель"""
    
    # Временно используем ForeignKey вместо OneToOneField, чтобы избежать циклической зависимости
    child = models.ForeignKey(
        'Child', 
        on_delete=models.CASCADE, 
        related_name='personal_files',
        null=True,
        blank=True
    )
    
    # Статус дела
    STATUS_CHOICES = [
        ('active', 'Действует'),
        ('archived', 'В архиве'),
        ('graduated', 'Выпущен'),
        ('transferred', 'Переведен'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Контроль сроков действия документов
    registration_expiry_date = models.DateField(null=True, blank=True, verbose_name='Срок действия регистрации')
    medical_card_expiry_date = models.DateField(null=True, blank=True, verbose_name='Срок действия медкарты')
    policy_expiry_date = models.DateField(null=True, blank=True, verbose_name='Срок действия полиса')
    
    # Умные уведомления
    notification_sent_registration = models.BooleanField(default=False)
    notification_sent_medical = models.BooleanField(default=False)
    notification_sent_policy = models.BooleanField(default=False)
    
    # Дополнительные документы
    additional_documents = models.JSONField(default=list, verbose_name='Дополнительные документы')
    
    # История изменений
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Личное дело'
        verbose_name_plural = 'Личные дела'
    
    def __str__(self):
        child_name = self.child.full_name if self.child and hasattr(self.child, 'full_name') else "Нет ребенка"
        return f"Личное дело: {child_name}"
    
    def is_registration_expiring_soon(self, days=30):
        """Проверка, истекает ли срок регистрации"""
        if self.registration_expiry_date:
            days_left = (self.registration_expiry_date - date.today()).days
            return 0 < days_left <= days
        return False
    
    def is_registration_expired(self):
        """Проверка, истек ли срок регистрации"""
        if self.registration_expiry_date:
            return self.registration_expiry_date < date.today()
        return False
    
    def is_medical_expiring_soon(self, days=30):
        """Проверка, истекает ли срок медкарты"""
        if self.medical_card_expiry_date:
            days_left = (self.medical_card_expiry_date - date.today()).days
            return 0 < days_left <= days
        return False
    
    def is_medical_expired(self):
        """Проверка, истек ли срок медкарты"""
        if self.medical_card_expiry_date:
            return self.medical_card_expiry_date < date.today()
        return False
    
    def get_expiry_status(self):
        """Получить статус истечения документов"""
        statuses = []
        
        if self.is_registration_expired():
            statuses.append({'type': 'registration', 'status': 'expired', 'message': 'Срок регистрации ИСТЕК!'})
        elif self.is_registration_expiring_soon():
            statuses.append({'type': 'registration', 'status': 'warning', 'message': f'Регистрация истекает через {(self.registration_expiry_date - date.today()).days} дней'})
        
        if self.is_medical_expired():
            statuses.append({'type': 'medical', 'status': 'expired', 'message': 'Срок медкарты ИСТЕК!'})
        elif self.is_medical_expiring_soon():
            statuses.append({'type': 'medical', 'status': 'warning', 'message': f'Медкарта истекает через {(self.medical_card_expiry_date - date.today()).days} дней'})
        
        return statuses


class DocumentCheckHistory(models.Model):
    """История проверок документов"""
    
    personal_file = models.ForeignKey(PersonalFile, on_delete=models.CASCADE, related_name='check_history')
    checked_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    # Статусы документов на момент проверки
    registration_valid = models.BooleanField(default=False)
    medical_valid = models.BooleanField(default=False)
    policy_valid = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'История проверки'
        verbose_name_plural = 'Истории проверок'
        ordering = ['-checked_at']
    
    def __str__(self):
        return f"Проверка {self.personal_file} от {self.checked_at.strftime('%d.%m.%Y')}"


# ==================== ЗАТЕМ ОПРЕДЕЛЯЕМ Group ====================

class Group(models.Model):
    AGE_CATEGORY_CHOICES = [
        ('nursery', 'Ясельная (1.5-3 года)'),
        ('junior', 'Младшая (3-4 года)'),
        ('middle', 'Средняя (4-5 лет)'),
        ('senior', 'Старшая (5-6 лет)'),
        ('preparatory', 'Подготовительная (6-7 лет)'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Название группы')
    age_category = models.CharField(
        max_length=20, 
        choices=AGE_CATEGORY_CHOICES, 
        verbose_name='Возрастная категория'
    )
    teacher = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        limit_choices_to={'role': 'teacher'},
        verbose_name='Воспитатель'
    )
    capacity = models.PositiveIntegerField(default=20, verbose_name='Вместимость')
    room_number = models.CharField(max_length=10, verbose_name='Номер комнаты', blank=True)
    current_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Текущее количество детей'
    )
    
    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.current_count:
            self.current_count = 0
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('children:group_detail', args=[str(self.id)])
    
    @property
    def children_count(self):
        return self.child_set.count()
    
    @property
    def fill_percentage(self):
        if self.capacity > 0:
            return round((self.children_count / self.capacity) * 100, 1)
        return 0
    
    @property
    def free_spaces(self):
        return self.capacity - self.children_count


# ==================== ОПРЕДЕЛЯЕМ RELATION_CHOICES ГЛОБАЛЬНО ====================

RELATION_CHOICES = (
    ('mother', 'Мать'),
    ('father', 'Отец'),
    ('grandmother', 'Бабушка'),
    ('grandfather', 'Дедушка'),
    ('guardian', 'Опекун'),
)


# ==================== ТЕПЕРЬ ОПРЕДЕЛЯЕМ Child (перед ChildParent) ====================

class Child(models.Model):
    # Связь с заявлением
    application = models.OneToOneField(
        'applications.ChildApplication', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='child_record',
        verbose_name='Заявление о приеме'
    )
    
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Группа')
    full_name = models.CharField(max_length=200, verbose_name='ФИО ребенка')
    birth_date = models.DateField(verbose_name='Дата рождения')
    gender = models.CharField(max_length=1, choices=(('M', 'Мальчик'), ('F', 'Девочка')), verbose_name='Пол')
    
    # Документы
    birth_certificate = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Свидетельство о рождении',
        help_text='Серия и номер свидетельства о рождении'
    )
    birth_certificate_issued_by = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Кем выдано свидетельство'
    )
    birth_certificate_issue_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата выдачи свидетельства'
    )
    
    # ===== ДОКУМЕНТЫ (ДОБАВИТЬ ЭТИ ПОЛЯ) =====
    birth_certificate_file = models.FileField(
        upload_to='children/birth_certificates/',
        blank=True,
        null=True,
        verbose_name='Скан свидетельства о рождении'
    )
    snils_file = models.FileField(
        upload_to='children/snils/',
        blank=True,
        null=True,
        verbose_name='Скан СНИЛС'
    )
    insurance_policy_file = models.FileField(
        upload_to='children/insurance/',
        blank=True,
        null=True,
        verbose_name='Скан полиса ОМС'
    )
    vaccination_certificate_file = models.FileField(
        upload_to='children/vaccinations/',
        blank=True,
        null=True,
        verbose_name='Скан прививочного сертификата'
    )
    medical_card_file = models.FileField(
        upload_to='children/medical_cards/',
        blank=True,
        null=True,
        verbose_name='Скан медицинской карты'
    )
    registration_certificate = models.FileField(
        upload_to='children/registration/',
        blank=True,
        null=True,
        verbose_name='Справка о регистрации'
    )
    has_vaccinations = models.BooleanField(default=False, verbose_name='Наличие прививок')
    pmpk_conclusion = models.FileField(
        upload_to='children/pmpk/',
        blank=True,
        null=True,
        verbose_name='Заключение ПМПК'
    )
    
    # Медицинская информация
    medical_card_number = models.CharField(max_length=50, blank=True, verbose_name='Номер медицинской карты')
    policy_oms_number = models.CharField(max_length=50, blank=True, verbose_name='Полис ОМС')
    snils = models.CharField(max_length=50, blank=True, verbose_name='СНИЛС')
    
    blood_type = models.CharField(max_length=3, blank=True, verbose_name='Группа крови')
    allergies = models.TextField(blank=True, verbose_name='Аллергии')
    chronic_diseases = models.TextField(blank=True, verbose_name='Хронические заболевания')
    special_needs = models.TextField(blank=True, verbose_name='Особые потребности')
    disability_certificate = models.CharField(max_length=100, blank=True, verbose_name='Справка об инвалидности')
    
    # Адреса
    registration_address = models.TextField(verbose_name='Адрес регистрации')
    actual_address = models.TextField(verbose_name='Фактический адрес проживания')
    
    # Фото
    photo = models.ImageField(
        upload_to=child_photo_path,
        null=True,
        blank=True,
        verbose_name='Фотография',
        help_text='Рекомендуемый размер: 300x300 пикселей'
    )
    
    # Статусы
    is_active = models.BooleanField(default=True, verbose_name='Активен в системе')
    enrollment_date = models.DateField(null=True, blank=True, verbose_name='Дата зачисления')
    graduation_date = models.DateField(null=True, blank=True, verbose_name='Дата выпуска')
    
    # Связь с личным делом (OneToOne)
    personal_file = models.OneToOneField(
        PersonalFile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='child_record'
    )
    
    # Документы с контролем сроков
    registration_certificate = models.FileField(
        upload_to='documents/registration/',
        blank=True,
        null=True,
        verbose_name='Свидетельство о регистрации'
    )
    registration_issued_date = models.DateField(null=True, blank=True, verbose_name='Дата выдачи регистрации')
    
    medical_card_file = models.FileField(
        upload_to='documents/medical/',
        blank=True,
        null=True,
        verbose_name='Медицинская карта (файл)'
    )
    
    # Согласия
    consent_data_processing = models.BooleanField(default=False, verbose_name='Согласие на обработку ПД')
    consent_photo_video = models.BooleanField(default=False, verbose_name='Согласие на фото/видео')
    consent_medical_intervention = models.BooleanField(default=False, verbose_name='Согласие на медвмешательство')
    
    # Даты подписания согласий
    consent_data_processing_date = models.DateField(null=True, blank=True)
    consent_photo_video_date = models.DateField(null=True, blank=True)
    consent_medical_intervention_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Ребенок'
        verbose_name_plural = 'Дети'
        ordering = ['full_name']
    
    def save(self, *args, **kwargs):
        # Автоматическое создание личного дела, если его нет
        if not self.personal_file:
            personal_file = PersonalFile.objects.create()
            self.personal_file = personal_file
            personal_file.child = self
            personal_file.save()
        elif self.personal_file and self.personal_file.child != self:
            self.personal_file.child = self
            self.personal_file.save()
        
        super().save(*args, **kwargs)
    
    def get_age(self):
        today = date.today()
        age = today.year - self.birth_date.year
        if today.month < self.birth_date.month or (today.month == self.birth_date.month and today.day < self.birth_date.day):
            age -= 1
        return age
    
    def get_age_detailed(self):
        today = date.today()
        years = today.year - self.birth_date.year
        months = today.month - self.birth_date.month
        
        if today.day < self.birth_date.day:
            months -= 1
        
        if months < 0:
            years -= 1
            months += 12
            
        return years, months
    
    def __str__(self):
        return self.full_name
    
    @property
    def age_display(self):
        years, months = self.get_age_detailed()
        if years == 0:
            return f"{months} мес."
        elif months == 0:
            return f"{years} лет"
        else:
            return f"{years} лет {months} мес."
    
    def get_documents_completion_percentage(self):
        """Процент заполнения документов"""
        required_fields = [
            'full_name', 'birth_date', 'gender', 'registration_address',
            'birth_certificate', 'medical_card_number', 'policy_oms_number'
        ]
        filled = 0
        for field in required_fields:
            value = getattr(self, field, None)
            if value:
                filled += 1
        
        total_fields = len(required_fields)
        if total_fields == 0:
            return 0
        
        return int((filled / total_fields) * 100)
    
    def get_parents(self):
        """Получить всех родителей ребенка через ChildParent"""
        from .models import ChildParent
        return ChildParent.objects.filter(child=self).select_related('parent__user')
    
    def get_primary_parent(self):
        """Получить основного родителя"""
        primary = self.get_parents().filter(is_primary=True).first()
        if primary:
            return primary.parent
        first = self.get_parents().first()
        return first.parent if first else None


# ==================== В КОНЦЕ ОПРЕДЕЛЯЕМ ChildParent (после Child) ====================

class ChildParent(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='parent_relations')
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name='child_relations')
    relation = models.CharField(max_length=15, choices=RELATION_CHOICES, verbose_name='Родство')
    is_primary = models.BooleanField(default=False, verbose_name='Основной контакт')
    
    class Meta:
        verbose_name = 'Связь ребенок-родитель'
        verbose_name_plural = 'Связи ребенок-родитель'
        unique_together = ('child', 'parent')
    
    def __str__(self):
        return f"{self.child.full_name} - {self.get_relation_display()}"