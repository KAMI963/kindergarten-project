# contracts/models.py
from django.db import models
from django.utils import timezone
from django.urls import reverse
from children.models import Child
from accounts.models import ParentProfile, CustomUser
from applications.models import ChildApplication


class EducationContract(models.Model):
    """
    Модель договора об образовании между ДОУ и родителями
    """
    CONTRACT_STATUS_CHOICES = (
        ('draft', 'Сформирован'),
        ('signed', 'Подписан сторонами'),
        ('active', 'Действует'),
        ('terminated', 'Расторгнут'),
        ('expired', 'Истек'),
    )
    
    # Регистрационные данные
    contract_number = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name='Номер договора'
    )
    registration_date = models.DateField(
        default=timezone.now,
        verbose_name='Дата регистрации'
    )
    
    # Связь с заявлением
    application = models.ForeignKey(
        ChildApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Заявление',
        related_name='contracts'
    )
    
    # Ребенок (может быть NULL, если создан из заявления)
    child = models.ForeignKey(
        Child, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Воспитанник',
        related_name='contracts'
    )
    
    # Родитель
    parent = models.ForeignKey(
        ParentProfile,
        on_delete=models.CASCADE,
        verbose_name='Родитель (законный представитель)',
        related_name='contracts'
    )
    
    # Данные ребенка (дублируются из заявления для истории)
    child_full_name = models.CharField(
        max_length=200,
        verbose_name='ФИО ребенка',
        blank=True,
        null=True
    )
    child_birth_date = models.DateField(
        verbose_name='Дата рождения ребенка',
        blank=True,
        null=True
    )
    
    # Данные из договора
    enrollment_date = models.DateField(
        verbose_name='Планируемая дата зачисления',
        blank=True,
        null=True
    )
    group_name = models.CharField(
        max_length=100,
        verbose_name='Планируемая группа',
        help_text='Наименование группы при зачислении',
        blank=True,
        null=True
    )
    
    # Сроки договора
    contract_start_date = models.DateField(
        default=timezone.now,
        verbose_name='Дата заключения договора'
    )
    contract_end_date = models.DateField(
        null=True, 
        blank=True,
        verbose_name='Дата окончания договора'
    )
    
    # Данные из пунктов договора
    educational_program = models.TextField(
        verbose_name='Образовательная программа',
        blank=True,
        null=True,
        default='Основная общеобразовательная программа дошкольного образования муниципального бюджетного дошкольного образовательного учреждения Карабашский детский сад общеразвивающего вида №1 «Рябинушка» Бугульминского муниципального района Республики Татарстан'
    )
    study_period = models.IntegerField(
        verbose_name='Срок освоения программы (лет)',
        default=5
    )
    stay_regimen = models.CharField(
        max_length=200,
        verbose_name='Режим пребывания',
        blank=True,
        null=True,
        default='пятидневная неделя (понедельник – пятница), 12 часов (с 6.00 до 18.00)'
    )
    
    child_gender = models.CharField(
    max_length=1, 
    choices=(('M', 'Мальчик'), ('F', 'Девочка')), 
    blank=True, 
    null=True,
    verbose_name='Пол ребенка'
)
    
    # Финансовые данные
    parent_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Родительская плата (всего)',
        default=0
    )
    subscription_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Абонентская плата',
        default=0
    )
    food_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Питание',
        default=0
    )
    
    # Дополнительная информация
    basis_documents = models.TextField(
        verbose_name='Основание',
        help_text='Документы, на основании которых заключен договор',
        blank=True,
        null=True
    )
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Примечания'
    )
    
    # Статус и контроль
    status = models.CharField(
        max_length=20,
        choices=CONTRACT_STATUS_CHOICES,
        default='draft',
        verbose_name='Статус договора'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    
    # Даты подписания
    director_signed_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Подписано заведующей'
    )
    parent_signed_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Подписано родителем'
    )
    
    # Сгенерированный документ
    generated_contract = models.FileField(
        upload_to='contracts/generated/',
        blank=True,
        null=True,
        verbose_name='Сгенерированный договор'
    )
    
    # Системные поля
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_contracts',
        verbose_name='Кем создан'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Договор об образовании'
        verbose_name_plural = 'Договоры об образовании'
        ordering = ['-registration_date', '-contract_number']
        indexes = [
            models.Index(fields=['contract_number']),
            models.Index(fields=['status']),
            models.Index(fields=['registration_date']),
        ]
    
    def __str__(self):
        child_name = self.child_full_name if self.child_full_name else "Не указано"
        return f"Договор №{self.contract_number} от {self.registration_date} - {child_name}"
    
    def get_absolute_url(self):
        return reverse('contracts:contract_detail', kwargs={'pk': self.pk})
    
    def save(self, *args, **kwargs):
        if not self.contract_number:
            self.contract_number = self.generate_contract_number()
        super().save(*args, **kwargs)
    
    def generate_contract_number(self):
        """Генерация номера договора в формате Д-{год}-{номер}"""
        year = self.registration_date.year
        last_contract = EducationContract.objects.filter(
            registration_date__year=year
        ).order_by('-id').first()
        
        if last_contract and last_contract.contract_number:
            try:
                last_num = int(last_contract.contract_number.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"Д-{year}-{new_num:04d}"
    
    @property
    def parent_full_name(self):
        """ФИО родителя для отображения"""
        return self.parent.user.get_full_name() if self.parent else ""
    
    @property
    def is_fully_signed(self):
        """Проверка, подписан ли договор обеими сторонами"""
        return self.director_signed_at is not None and self.parent_signed_at is not None


class ContractRegistry(models.Model):
    """
    Реестр договоров для учета и контроля
    """
    contract = models.OneToOneField(
        EducationContract,
        on_delete=models.CASCADE,
        related_name='registry_entry',
        verbose_name='Договор'
    )
    
    # Номер в реестре
    registry_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Номер в реестре'
    )
    
    # Дополнительные соглашения
    has_additional_agreements = models.BooleanField(
        default=False,
        verbose_name='Есть дополнительные соглашения'
    )
    additional_agreements_info = models.TextField(
        blank=True,
        null=True,
        verbose_name='Информация о доп. соглашениях'
    )
    
    # Контрольные поля
    last_check_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата последней проверки'
    )
    checked_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checked_contracts',
        verbose_name='Проверил'
    )
    check_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Замечания при проверке'
    )
    
    # Хранение
    storage_location = models.CharField(
        max_length=100,
        default='Личное дело воспитанника',
        verbose_name='Место хранения'
    )
    
    # Системные поля
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Запись реестра договоров'
        verbose_name_plural = 'Реестр договоров'
        ordering = ['-registry_number']
    
    def __str__(self):
        return f"Реестр №{self.registry_number} - {self.contract}"
    
    def save(self, *args, **kwargs):
        if not self.registry_number:
            self.registry_number = self.generate_registry_number()
        super().save(*args, **kwargs)
    
    def generate_registry_number(self):
        """Генерация номера в реестре"""
        year = timezone.now().year
        last_entry = ContractRegistry.objects.filter(
            created_at__year=year
        ).order_by('-id').first()
        
        if last_entry and last_entry.registry_number:
            try:
                last_num = int(last_entry.registry_number.split('-')[-1])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1
        
        return f"Р-{year}-{new_num:04d}"
