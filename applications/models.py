from django.db import models
from accounts.models import CustomUser, ParentProfile
from django.utils import timezone
from datetime import date, timedelta
import uuid
import threading


class ApplicationStatus(models.TextChoices):
    """Статусы заявления"""
    DRAFT = 'draft', 'Черновик'
    PENDING = 'pending', 'На проверке'
    QUEUE = 'queue', 'В очереди'
    APPROVED = 'approved', 'Одобрено'
    INVITED = 'invited', 'Приглашен на оформление'
    PROCESSING = 'processing', 'На оформлении'
    ENROLLED = 'enrolled', 'Зачислен'
    REJECTED = 'rejected', 'Отказ'
    RETURNED = 'returned', 'Возвращено на доработку'
    EXPIRED = 'expired', 'Срок приглашения истек'
    WITHDRAWN = 'withdrawn', 'Отозвана'


class BenefitCategory(models.TextChoices):
    """Категории льгот с подробным описанием"""
    # Внеочередное право
    EXTRAORDINARY_SIBLING = 'extraordinary_sibling', 'Дети с внеочередным правом, братья/сёстры которых посещают тот же детский сад'
    EXTRAORDINARY = 'extraordinary', 'Дети с внеочередным правом на зачисление'
    EXTRAORDINARY_JUDGE = 'extraordinary_judge', 'Дети судей, сотрудников Следственного комитета или прокуратуры'
    EXTRAORDINARY_MILITARY_SVO = 'extraordinary_military_svo', 'Дети военнослужащих, добровольцев или сотрудников Росгвардии, погибших в ходе СВО'
    EXTRAORDINARY_CHERNOBYL = 'extraordinary_chernobyl', 'Дети ликвидаторов аварии на Чернобыльской АЭС'
    
    # Первоочередное право
    PRIORITY_SIBLING = 'priority_sibling', 'Дети с первоочередным правом, братья/сёстры которых посещают тот же детский сад'
    PRIORITY = 'priority', 'Дети с первоочередным правом на зачисление'
    PRIORITY_DISABILITY = 'priority_disability', 'Дети с инвалидностью'
    PRIORITY_LARGE_FAMILY = 'priority_large_family', 'Дети многодетных родителей'
    PRIORITY_PARENT_DISABILITY = 'priority_parent_disability', 'Дети родителей с инвалидностью'
    PRIORITY_MILITARY = 'priority_military', 'Дети военнослужащих, в том числе участников СВО'
    PRIORITY_POLICE = 'priority_police', 'Дети сотрудников полиции, ФСИН, ФССП, ФТС, ГПС'
    
    # Преимущественное право
    PREFERENTIAL_SIBLING = 'preferential_sibling', 'Дети с преимущественным правом (брат/сестра уже посещает детский сад)'
    PREFERENTIAL = 'preferential', 'Дети с преимущественным правом на зачисление'
    
    # Без льготы
    NONE = 'none', 'Дети без льгот'
    
    @classmethod
    def get_priority_score(cls, category):
        """Возвращает баллы приоритета для категории"""
        scores = {
            'extraordinary_sibling': 150,
            'extraordinary': 100,
            'extraordinary_judge': 100,
            'extraordinary_military_svo': 100,
            'extraordinary_chernobyl': 100,
            'priority_sibling': 80,
            'priority': 50,
            'priority_disability': 50,
            'priority_large_family': 50,
            'priority_parent_disability': 50,
            'priority_military': 50,
            'priority_police': 50,
            'preferential_sibling': 30,
            'preferential': 25,
            'none': 0,
        }
        return scores.get(category, 0)
    
    @classmethod
    def get_priority_text(cls, category):
        """Возвращает текст очерёдности для отображения"""
        texts = {
            'extraordinary_sibling': 'ВНЕОЧЕРЕДНОЕ право (150 баллов) - приоритет 1',
            'extraordinary': 'ВНЕОЧЕРЕДНОЕ право (100 баллов) - приоритет 1',
            'extraordinary_judge': 'ВНЕОЧЕРЕДНОЕ право (100 баллов) - приоритет 1',
            'extraordinary_military_svo': 'ВНЕОЧЕРЕДНОЕ право (100 баллов) - приоритет 1',
            'extraordinary_chernobyl': 'ВНЕОЧЕРЕДНОЕ право (100 баллов) - приоритет 1',
            'priority_sibling': 'ПЕРВООЧЕРЕДНОЕ право (80 баллов) - приоритет 2',
            'priority': 'ПЕРВООЧЕРЕДНОЕ право (50 баллов) - приоритет 2',
            'priority_disability': 'ПЕРВООЧЕРЕДНОЕ право (50 баллов) - приоритет 2',
            'priority_large_family': 'ПЕРВООЧЕРЕДНОЕ право (50 баллов) - приоритет 2',
            'priority_parent_disability': 'ПЕРВООЧЕРЕДНОЕ право (50 баллов) - приоритет 2',
            'priority_military': 'ПЕРВООЧЕРЕДНОЕ право (50 баллов) - приоритет 2',
            'priority_police': 'ПЕРВООЧЕРЕДНОЕ право (50 баллов) - приоритет 2',
            'preferential_sibling': 'ПРЕИМУЩЕСТВЕННОЕ право (30 баллов) - приоритет 3',
            'preferential': 'ПРЕИМУЩЕСТВЕННОЕ право (25 баллов) - приоритет 3',
            'none': 'БЕЗ ЛЬГОТЫ (0 баллов) - общая очередь',
        }
        return texts.get(category, 'Обычная очередь')


class AgeCategory(models.TextChoices):
    """Возрастные категории для очереди"""
    NURSERY_1_2 = 'nursery_1_2', 'Первая младшая (1-2 года)'
    NURSERY_2_3 = 'nursery_2_3', 'Первая младшая (2-3 года)'
    JUNIOR_3_4 = 'junior_3_4', 'Вторая младшая (3-4 года)'
    MIDDLE_4_5 = 'middle_4_5', 'Средняя (4-5 лет)'
    SENIOR_5_6 = 'senior_5_6', 'Старшая (5-6 лет)'
    PREPARATORY_6_7 = 'preparatory_6_7', 'Подготовительная (6-7 лет)'


class ChildApplication(models.Model):
    """Модель заявления о приеме ребенка в детский сад"""
    
    PRIORITY_CHOICES = (
        ('standard', 'Стандартный'),
        ('district', 'Районный'),
        ('benefit', 'Льготный'),
        ('staff', 'Сотрудник ДОУ'),
    )
    
    # ===== ОСНОВНАЯ ИНФОРМАЦИЯ =====
    application_number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name='applications')
    
    # ===== ДАННЫЕ РЕБЕНКА =====
    child_full_name = models.CharField(max_length=200, verbose_name='ФИО ребенка')
    child_birth_date = models.DateField(verbose_name='Дата рождения ребенка')
    child_gender = models.CharField(max_length=1, choices=(('M', 'Мальчик'), ('F', 'Девочка')), verbose_name='Пол ребенка')
    child_snils = models.CharField(max_length=20, blank=True, verbose_name='СНИЛС ребенка (номер)')
    child_photo = models.ImageField(
        upload_to='applications/child_photos/',
        blank=True,
        null=True,
        verbose_name='Фотография ребенка'
    )
    
    # ===== ДОКУМЕНТЫ РЕБЕНКА (НОВЫЕ) =====
    child_snils_file = models.FileField(
        upload_to='applications/child_snils/',
        blank=True,
        null=True,
        verbose_name='СНИЛС ребенка (скан)'
    )
    vaccination_certificate_file = models.FileField(
        upload_to='applications/vaccinations/',
        blank=True,
        null=True,
        verbose_name='Сертификат о прививках (форма № 063/у)'
    )
    insurance_policy_file = models.FileField(
        upload_to='applications/insurance/',
        blank=True,
        null=True,
        verbose_name='Полис медицинского страхования'
    )
    medical_card_a4_file = models.FileField(
        upload_to='applications/medical_cards_a4/',
        blank=True,
        null=True,
        verbose_name='Медицинская карта ребенка (форма № 026/у) А4'
    )
    
    # ===== ДАННЫЕ СВИДЕТЕЛЬСТВА О РОЖДЕНИИ =====
    birth_certificate_series = models.CharField(max_length=10, blank=True, verbose_name='Серия свидетельства')
    birth_certificate_number = models.CharField(max_length=20, blank=True, verbose_name='Номер свидетельства')
    birth_certificate_issue_date = models.DateField(null=True, blank=True, verbose_name='Дата выдачи свидетельства')
    birth_certificate_issued_by = models.CharField(max_length=200, blank=True, verbose_name='Кем выдано свидетельство')
    birth_certificate_file = models.FileField(
        upload_to='applications/birth_certificates/',
        verbose_name='Свидетельство о рождении'
    )
    birth_certificate_translation = models.FileField(
        upload_to='applications/birth_translations/',
        null=True, blank=True,
        verbose_name='Перевод свидетельства о рождении (нотариально заверенный)'
    )
    
    # ===== АДРЕСНЫЕ ДАННЫЕ =====
    registration_address = models.TextField(verbose_name='Адрес регистрации')
    actual_address = models.TextField(verbose_name='Фактический адрес проживания')
    residence_certificate = models.FileField(
        upload_to='applications/residence_certificates/',
        null=True, blank=True,
        verbose_name='Свидетельство о регистрации/справка с места жительства'
    )
    
    # ===== КОНТАКТНЫЕ ДАННЫЕ =====
    phone_number = models.CharField(max_length=20, blank=True, verbose_name='Контактный телефон')
    email = models.EmailField(blank=True, verbose_name='Электронная почта')
    
    # ===== ДАННЫЕ ЗАЯВИТЕЛЕЙ (НОВЫЕ) =====
    # Заявитель 1 (основной)
    applicant1_full_name = models.CharField(
        max_length=200,
        verbose_name='ФИО заявителя (лицо, подписывающее документы)'
    )
    applicant1_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Телефон заявителя'
    )
    applicant1_is_primary = models.BooleanField(
        default=True,
        verbose_name='Основной заявитель'
    )
    applicant1_passport_file = models.FileField(
        upload_to='applications/applicant1_passports/',
        blank=True,
        null=True,
        verbose_name='Паспорт заявителя'
    )
    
    # Заявитель 2 (второй родитель/представитель)
    applicant2_full_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='ФИО второго заявителя'
    )
    applicant2_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Телефон второго заявителя'
    )
    applicant2_passport_file = models.FileField(
        upload_to='applications/applicant2_passports/',
        blank=True,
        null=True,
        verbose_name='Паспорт второго заявителя'
    )
    
    # ===== МЕДИЦИНСКИЕ ДАННЫЕ =====
    has_vaccinations = models.BooleanField(default=False, verbose_name='Наличие прививок')
    chronic_diseases = models.TextField(blank=True, verbose_name='Хронические заболевания')
    medical_notes = models.TextField(blank=True, verbose_name='Медицинские примечания')
    blood_type = models.CharField(max_length=5, blank=True, verbose_name='Группа крови')
    allergies = models.TextField(blank=True, verbose_name='Аллергии')
    special_needs = models.TextField(blank=True, verbose_name='Особые потребности')
    medical_card = models.FileField(
        upload_to='documents/medical_cards/',
        verbose_name='Медицинская карта'
    )
    health_certificate_oz = models.FileField(
        upload_to='applications/health_certificates/',
        null=True, blank=True,
        verbose_name='Медицинская справка (оздоровительная группа)'
    )
    pmpk_conclusion = models.FileField(
        upload_to='applications/pmpk/',
        null=True, blank=True,
        verbose_name='Заключение ПМПК'
    )
    
    # ===== ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ =====
    preferred_group = models.CharField(max_length=100, blank=True, null=True, verbose_name='Предпочтительная группа')
    enrollment_date = models.DateField(null=True, blank=True, verbose_name='Желаемая дата зачисления')
    additional_info = models.TextField(blank=True, verbose_name='Дополнительная информация')
    
    # ===== ДОПОЛНИТЕЛЬНЫЕ ДОКУМЕНТЫ =====
    additional_documents = models.FileField(
        upload_to='documents/additional/',
        blank=True, null=True,
        verbose_name='Дополнительные документы'
    )
    residence_proof_file = models.FileField(
        upload_to='applications/residence_proof/',
        blank=True, null=True,
        verbose_name='Подтверждение места жительства'
    )
    health_certificate = models.FileField(
        upload_to='applications/health_certificates/',
        blank=True, null=True,
        verbose_name='Медицинская справка'
    )
    pmpk_file = models.FileField(
        upload_to='applications/pmpk/',
        blank=True, null=True,
        verbose_name='Заключение ПМПК'
    )
    foreign_documents = models.FileField(
        upload_to='applications/foreign_docs/',
        blank=True, null=True,
        verbose_name='Документы для иностранцев'
    )
    foreign_residence_doc = models.FileField(
        upload_to='applications/foreign_residence/',
        blank=True, null=True,
        verbose_name='Документ о праве находиться в России'
    )
    guardianship_act = models.FileField(
        upload_to='applications/guardianship/',
        blank=True, null=True,
        verbose_name='Акт о назначении опекуна'
    )
    guardianship_act_doc = models.FileField(
        upload_to='applications/guardianship/',
        blank=True, null=True,
        verbose_name='Акт о назначении опекуна'
    )
    
    # ===== ЛЬГОТЫ =====
    benefit_category = models.CharField(
        max_length=30,
        choices=BenefitCategory.choices,
        default=BenefitCategory.NONE,
        verbose_name='Категория льготы'
    )
    benefit_document = models.FileField(
        upload_to='applications/benefits/',
        blank=True, null=True,
        verbose_name='Подтверждающий документ льготы'
    )
    benefit_document_right = models.FileField(
        upload_to='applications/benefit_rights/',
        blank=True, null=True,
        verbose_name='Документ о праве на льготу'
    )
    benefit_verified = models.BooleanField(default=False, verbose_name='Льгота подтверждена')
    
    # ===== ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ ДЛЯ ОЧЕРЕДИ =====
    age_category = models.CharField(
        max_length=20,
        choices=AgeCategory.choices,
        blank=True,
        null=True,
        verbose_name='Возрастная категория'
    )
    
    sibling_in_kindergarten = models.BooleanField(
        default=False,
        verbose_name='Брат/сестра уже посещает этот детский сад'
    )
    
    sibling_child = models.ForeignKey(
        'children.Child',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sibling_applications',
        verbose_name='Брат/сестра в детском саду'
    )
    
    sibling_application = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Заявление брата/сестры'
    )
    
    invitation_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Срок действия приглашения'
    )
    
    appointment_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата и время визита для оформления'
    )
    
    enrollment_order_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Номер приказа о зачислении'
    )
    
    enrollment_order_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата приказа о зачислении'
    )
    
    enrolled_group = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Зачислен в группу'
    )
    
    returned_reason = models.TextField(
        blank=True,
        verbose_name='Причина возврата на доработку'
    )
    
    # ===== ЭЛЕКТРОННАЯ ОЧЕРЕДЬ =====
    queue_position = models.IntegerField(
        null=True, blank=True,
        verbose_name='Позиция в очереди'
    )
    queue_priority = models.IntegerField(
        default=0,
        verbose_name='Приоритет очереди'
    )
    last_queue_update = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Последнее обновление очереди'
    )
    
    # ===== СТАТУС И ПРИОРИТЕТ =====
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.DRAFT,
        verbose_name='Статус заявления'
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='standard',
        verbose_name='Приоритет'
    )
    
    # ===== КОММЕНТАРИИ И ПРОВЕРКА =====
    director_notes = models.TextField(blank=True, verbose_name='Заметки заведующей')
    rejection_reason = models.TextField(blank=True, verbose_name='Причина отклонения')
    verification_comment = models.TextField(blank=True, verbose_name='Примечание проверяющего')
    documents_verified = models.BooleanField(default=False, verbose_name='Документы проверены')
    
    # ===== ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ =====
    require_health_group = models.BooleanField(default=False, verbose_name='Требуется оздоровительная группа')
    require_compensating_group = models.BooleanField(default=False, verbose_name='Требуется компенсирующая группа')
    is_foreign_citizen = models.BooleanField(default=False, verbose_name='Иностранный гражданин')
    is_guardianship = models.BooleanField(default=False, verbose_name='Опекунство')
    
    # ===== ДАТЫ =====
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submission_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата подачи')
    
    # ===== СОГЛАСИЯ =====
    data_processing_consent = models.BooleanField(default=False, verbose_name='Согласие на обработку персональных данных')
    rules_acquainted = models.BooleanField(default=False, verbose_name='Ознакомление с правилами')
    medical_examination_consent = models.BooleanField(default=False, verbose_name='Согласие на медицинский осмотр')
    photo_video_consent = models.BooleanField(default=False, verbose_name='Согласие на фото/видеосъемку')
    
    # ===== СГЕНЕРИРОВАННОЕ ЗАЯВЛЕНИЕ =====
    generated_application = models.FileField(
        upload_to='applications/generated/',
        blank=True, null=True,
        verbose_name='Сгенерированное заявление'
    )
    
    class Meta:
        verbose_name = "Заявление"
        verbose_name_plural = "Заявления"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Заявление #{self.application_number} - {self.child_full_name}"
    
    def save(self, *args, **kwargs):
        # Автоматический расчёт возрастной категории
        if self.child_birth_date and not self.age_category:
            self.age_category = self.calculate_age_category()
        
        update_fields = kwargs.get('update_fields')
        if not update_fields and self.status == ApplicationStatus.QUEUE:
            self.queue_priority = self.calculate_priority_score()
        
        super().save(*args, **kwargs)
    
    def calculate_age_category(self):
        """Расчёт возрастной категории на основе даты рождения"""
        if not self.child_birth_date:
            return None
        
        age = self.get_age()
        
        if age < 1:
            return None
        elif 1 <= age < 2:
            return 'nursery_1_2'
        elif 2 <= age < 3:
            return 'nursery_2_3'
        elif 3 <= age < 4:
            return 'junior_3_4'
        elif 4 <= age < 5:
            return 'middle_4_5'
        elif 5 <= age < 6:
            return 'senior_5_6'
        elif 6 <= age <= 7:
            return 'preparatory_6_7'
        return None
    
    def get_age(self):
        """Возраст ребёнка в годах"""
        if not self.child_birth_date:
            return 0
        today = date.today()
        age = today.year - self.child_birth_date.year
        if today.month < self.child_birth_date.month or (
            today.month == self.child_birth_date.month and today.day < self.child_birth_date.day
        ):
            age -= 1
        return age
    
    def get_age_detailed(self):
        """Возраст в годах и месяцах"""
        if not self.child_birth_date:
            return 0, 0
        today = date.today()
        years = today.year - self.child_birth_date.year
        months = today.month - self.child_birth_date.month
        
        if today.day < self.child_birth_date.day:
            months -= 1
        
        if months < 0:
            years -= 1
            months += 12
        
        return years, months
    
    def calculate_priority_score(self):
        """Расчёт приоритетного балла для сортировки в очереди"""
        base_score = BenefitCategory.get_priority_score(self.benefit_category)
        
        if self.sibling_in_kindergarten:
            base_score += 25
        
        days_since_submission = (date.today() - self.created_at.date()).days
        days_score = min(days_since_submission, 365)
        
        return base_score + days_score
    
    def get_priority_text(self):
        """Возвращает текст очерёдности для отображения"""
        return BenefitCategory.get_priority_text(self.benefit_category)
    
    def get_queue_position(self):
        """Получить позицию в очереди с учётом возрастной категории"""
        if not self.age_category:
            return None
        
        if self.status not in [ApplicationStatus.QUEUE, ApplicationStatus.INVITED, ApplicationStatus.PROCESSING]:
            return None
        
        queue_apps = ChildApplication.objects.filter(
            status__in=[ApplicationStatus.QUEUE, ApplicationStatus.INVITED, ApplicationStatus.PROCESSING],
            age_category=self.age_category
        ).order_by('-queue_priority', 'created_at')
        
        positions = list(queue_apps.values_list('id', flat=True))
        try:
            position = positions.index(self.id) + 1
            if self.queue_position != position:
                ChildApplication.objects.filter(id=self.id).update(queue_position=position)
                self.queue_position = position
            return position
        except ValueError:
            return self.queue_position or None
    
    def update_queue_position(self):
        """Обновить позицию в очереди"""
        if self.age_category:
            from .models import recalc_category_queue_positions
            recalc_category_queue_positions(self.age_category)
    
    def get_age_category_display(self):
        """Отображение возрастной категории"""
        categories = {
            'nursery_1_2': 'Первая младшая группа (1-2 года)',
            'nursery_2_3': 'Вторая младшая группа (2-3 года)',
            'junior_3_4': 'Младшая группа (3-4 года)',
            'middle_4_5': 'Средняя (4-5 лет)',
            'senior_5_6': 'Старшая (5-6 лет)',
            'preparatory_6_7': 'Подготовительная (6-7 лет)',
        }
        return categories.get(self.age_category, 'Не определена')
    
    def get_status_display(self):
        """Возвращает отображаемое название статуса"""
        status_map = {
            'draft': 'Черновик',
            'pending': 'На проверке',
            'queue': 'В очереди',
            'approved': 'Одобрено',
            'invited': 'Приглашен',
            'processing': 'На оформлении',
            'enrolled': 'Зачислен',
            'rejected': 'Отказано',
            'returned': 'На доработке',
            'expired': 'Срок истек',
            'withdrawn': 'Отозвано',
        }
        return status_map.get(self.status, self.status)
    
    def has_all_required_documents(self):
        """Проверка наличия всех обязательных документов"""
        required_docs = [
            self.birth_certificate_file,
            self.medical_card,
            self.applicant1_passport_file,
            self.residence_certificate,
        ]
        # Проверяем, что все документы есть и это не пустые строки
        for doc in required_docs:
            if not doc or doc == '':
                return False
        return True

    def get_missing_documents(self):
        """Получение списка недостающих документов"""
        missing = []
        if not self.birth_certificate_file or self.birth_certificate_file == '':
            missing.append('Свидетельство о рождении')
        if not self.medical_card or self.medical_card == '':
            missing.append('Медицинская карта')
        if not self.applicant1_passport_file or self.applicant1_passport_file == '':
            missing.append('Паспорт заявителя')
        if not self.residence_certificate or self.residence_certificate == '':
            missing.append('Подтверждение места жительства')
        return missing
    
    
      # ===== СВОЙСТВА ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ =====
    @property
    def mother_full_name(self):
        """ФИО матери (для обратной совместимости)"""
        return self.applicant1_full_name if self.applicant1_full_name else ''
    
    @property
    def father_full_name(self):
        """ФИО отца (для обратной совместимости)"""
        return self.applicant2_full_name if self.applicant2_full_name else ''
    
    @property
    def mother_phone(self):
        """Телефон матери (для обратной совместимости)"""
        return self.applicant1_phone if self.applicant1_phone else ''
    
    @property
    def father_phone(self):
        """Телефон отца (для обратной совместимости)"""
        return self.applicant2_phone if self.applicant2_phone else ''
    
    @property
    def passport_file(self):
        """Паспорт (для обратной совместимости)"""
        return self.applicant1_passport_file
    
    @property
    def parent_passport_file(self):
        """Паспорт родителя (для обратной совместимости)"""
        return self.applicant1_passport_file
    
    @property
    def residence_proof_file(self):
        """Подтверждение места жительства (для обратной совместимости)"""
        return self.residence_certificate
    
    @property
    def snils_file(self):
        """СНИЛС (для обратной совместимости)"""
        return self.child_snils_file
    
    @property
    def polis_file(self):
        """Полис (для обратной совместимости)"""
        return self.insurance_policy_file
    
    def get_child_gender_display(self):
        """Отображение пола ребенка"""
        return 'Мальчик' if self.child_gender == 'M' else 'Девочка'
    
    def get_benefit_category_display(self):
        """Отображение категории льготы"""
        return dict(BenefitCategory.choices).get(self.benefit_category, self.benefit_category)
    
    def invite_to_enrollment(self):
        """Пригласить на оформление"""
        self.status = ApplicationStatus.INVITED
        self.invitation_expires_at = timezone.now() + timedelta(days=14)
        self.save()
    
    def can_be_invited(self):
        """Проверка, можно ли пригласить заявление на оформление"""
        return self.status == ApplicationStatus.QUEUE
    
    def create_notification(self, title, message):
        """Создание уведомления для родителя"""
        try:
            from notifications.models import Notification
            Notification.objects.create(
                user=self.parent.user,
                title=title,
                message=message,
                notification_type='info',
                related_object_id=self.id,
                related_object_type='application'
            )
        except ImportError:
            print(f"Уведомление: {title} - {message}")
    
    def invite(self):
        """Пригласить на оформление"""
        if self.can_be_invited():
            self.status = ApplicationStatus.INVITED
            self.invitation_expires_at = timezone.now() + timedelta(days=14)
            self.save()
            return True
        return False
    
    def confirm_originals(self):
        """Подтверждение оригиналов документов"""
        self.status = ApplicationStatus.PROCESSING
        self.save()
    
    def create_enrollment_order(self, order_number, order_date, group_name):
        """Создание приказа о зачислении"""
        self.status = ApplicationStatus.ENROLLED
        self.enrollment_order_number = order_number
        self.enrollment_order_date = order_date
        self.enrolled_group = group_name
        self.save()
    
    def return_for_revision(self, reason):
        """Вернуть на доработку"""
        self.status = ApplicationStatus.RETURNED
        self.returned_reason = reason
        self.save()
    
    def reject(self, reason):
        """Отклонить заявление"""
        self.status = ApplicationStatus.REJECTED
        self.rejection_reason = reason
        self.save()
    
    def withdraw(self):
        """Отозвать заявление"""
        self.status = ApplicationStatus.WITHDRAWN
        self.save()
    
    @property
    def child_age(self):
        """Возраст ребенка в годах"""
        return self.get_age()
    
    def get_benefit_display(self):
        """Отображение льготы для списка"""
        return self.get_benefit_category_display()
    
    def get_status_display_verbose(self):
        """Расширенное отображение статуса"""
        status_display = {
            'draft': 'Черновик',
            'pending': 'На проверке',
            'queue': 'В очереди',
            'invited': 'Приглашен на оформление',
            'processing': 'На оформлении',
            'enrolled': 'Зачислен',
            'rejected': 'Отказано',
            'returned': 'Возвращено на доработку',
            'expired': 'Срок приглашения истек',
            'withdrawn': 'Отозвано'
        }
        return status_display.get(self.status, self.status)
    
    def is_invitation_expired(self):
        """Проверка, истек ли срок приглашения"""
        if self.status == ApplicationStatus.INVITED and self.invitation_expires_at:
            return timezone.now() > self.invitation_expires_at
        return False


class QueueHistory(models.Model):
    """История перемещений заявления в очереди"""
    application = models.ForeignKey(
        ChildApplication,
        on_delete=models.CASCADE,
        related_name='queue_history'
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    old_position = models.IntegerField(null=True, blank=True)
    new_position = models.IntegerField()
    new_priority = models.IntegerField(default=0)
    age_category = models.CharField(max_length=20, blank=True)
    reason = models.CharField(max_length=255, blank=True, verbose_name='Причина изменения')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    
    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'История очереди'
        verbose_name_plural = 'История очереди'
    
    def __str__(self):
        return f"{self.application.child_full_name}: {self.old_position} → {self.new_position} ({self.changed_at.strftime('%d.%m.%Y %H:%M')})"


class QueueSettings(models.Model):
    """Настройки очереди для каждой возрастной категории"""
    age_category = models.CharField(
        max_length=20,
        choices=AgeCategory.choices,
        unique=True,
        verbose_name='Возрастная категория'
    )
    capacity = models.PositiveIntegerField(
        default=20,
        verbose_name='Вместимость группы'
    )
    current_enrolled = models.PositiveIntegerField(
        default=0,
        verbose_name='Текущее количество зачисленных'
    )
    waiting_list = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество в очереди'
    )
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Настройка очереди'
        verbose_name_plural = 'Настройки очереди'
    
    def __str__(self):
        return f"{self.get_age_category_display()} - {self.current_enrolled}/{self.capacity}"
    
    def get_free_places(self):
        """Получить количество свободных мест"""
        return max(0, self.capacity - self.current_enrolled)
    
    def check_and_invite_next(self):
        """Проверить и пригласить следующего в очереди при освобождении места"""
        free_places = self.get_free_places()
        if free_places > 0:
            next_applications = ChildApplication.objects.filter(
                status=ApplicationStatus.QUEUE,
                age_category=self.age_category
            ).order_by('-queue_priority', 'created_at')[:free_places]
            
            for app in next_applications:
                app.invite_to_enrollment()
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            from .queue_logic import auto_invite_from_queue
            auto_invite_from_queue(self.age_category)
        except ImportError:
            pass


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

_recalculation_lock = threading.Lock()


def recalc_category_queue_positions(age_category):
    """Пересчитать позиции для всех заявлений в категории"""
    with _recalculation_lock:
        try:
            apps = ChildApplication.objects.filter(
                status__in=[ApplicationStatus.QUEUE, ApplicationStatus.INVITED, ApplicationStatus.PROCESSING],
                age_category=age_category
            ).order_by('-queue_priority', 'created_at')
            
            for idx, app in enumerate(apps, 1):
                old_pos = app.queue_position
                if old_pos != idx:
                    app.queue_position = idx
                    app.last_queue_update = timezone.now()
                    app.save(update_fields=['queue_position', 'last_queue_update'])
                    
                    QueueHistory.objects.create(
                        application=app,
                        old_position=old_pos,
                        new_position=idx,
                        new_priority=app.queue_priority,
                        age_category=age_category,
                        reason='Автоматический пересчёт очереди'
                    )
        except Exception as e:
            print(f"Ошибка пересчёта позиций для {age_category}: {e}")


def auto_reassign_age_categories():
    """Автоматическое перераспределение возрастных категорий"""
    with _recalculation_lock:
        try:
            applications = ChildApplication.objects.filter(
                status__in=[ApplicationStatus.QUEUE, ApplicationStatus.INVITED, ApplicationStatus.PROCESSING]
            )
            
            for app in applications:
                new_category = app.calculate_age_category()
                if new_category and app.age_category != new_category:
                    old_category = app.age_category
                    app.age_category = new_category
                    app.save(update_fields=['age_category'])
                    
                    if old_category:
                        recalc_category_queue_positions(old_category)
                    recalc_category_queue_positions(new_category)
                    
                    QueueHistory.objects.create(
                        application=app,
                        old_position=app.queue_position,
                        new_position=None,
                        new_priority=app.queue_priority,
                        age_category=new_category,
                        reason=f'Переход из категории {old_category} в {new_category} (достижение возраста)'
                    )
        except Exception as e:
            print(f"Ошибка перераспределения категорий: {e}")


def process_expired_invitations():
    """Обработка просроченных приглашений"""
    try:
        expired = ChildApplication.objects.filter(
            status=ApplicationStatus.INVITED,
            invitation_expires_at__lt=timezone.now()
        )
        
        for app in expired:
            app.status = ApplicationStatus.EXPIRED
            app.save()
            if app.age_category:
                recalc_category_queue_positions(app.age_category)
    except Exception as e:
        print(f"Ошибка обработки просроченных приглашений: {e}")