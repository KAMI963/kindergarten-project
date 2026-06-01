# staff/models.py
import calendar
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from attendance.models import ProductionCalendar
from decimal import Decimal

User = get_user_model()

# УБЕРИТЕ ЭТУ СТРОКУ - ОНА ВЫЗЫВАЕТ ОШИБКУ:
# from .models import (  # <-- ЭТО НУЖНО УДАЛИТЬ!

# staff/models.py (исправленная модель Employee)

class Employee(models.Model):
    """Сотрудник детского сада"""
    
    EMPLOYEE_TYPES = [
        ('teacher', 'Воспитатель'),
        ('assistant', 'Нянечка (помощник воспитателя)'),
        ('cook', 'Повар'),
        ('kitchen_worker', 'Кухонный работник'),
        ('administrative', 'Административный персонал'),
        ('caretaker', 'Завхоз'),
        ('guard', 'Сторож'),
        ('cleaner', 'Уборщица'),
        ('methodist', 'Методист'),
        ('music_director', 'Музыкальный руководитель'),
        ('physical_instructor', 'Инструктор по физкультуре'),
        ('psychologist', 'Психолог'),
        ('speech_therapist', 'Логопед'),
    ]
    
    # ИСПРАВЛЕНО: убрал дубликат, оставил одно правильное поле
    user = models.OneToOneField(
        'accounts.CustomUser', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Пользователь',
        related_name='employee_profile'
    )
    
    full_name = models.CharField(max_length=200, verbose_name='ФИО')
    employee_type = models.CharField(max_length=20, choices=EMPLOYEE_TYPES, verbose_name='Категория')
    position = models.CharField(max_length=100, verbose_name='Должность')
    
    # Контактные данные
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(verbose_name='Email')
    address = models.TextField(verbose_name='Адрес проживания')
    
    # Основные данные
    birth_date = models.DateField(verbose_name='Дата рождения')
    birth_place = models.CharField(max_length=200, verbose_name='Место рождения')
    
    # Статус
    is_active = models.BooleanField(default=True, verbose_name='Работает')
    hire_date = models.DateField(verbose_name='Дата приема на работу')
    dismissal_date = models.DateField(null=True, blank=True, verbose_name='Дата увольнения')
    dismissal_reason = models.TextField(blank=True, verbose_name='Причина увольнения')
    
    # Системные поля для инвайтов
    invite_token = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name='Токен приглашения'
    )
    invite_sent_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='Дата отправки приглашения'
    )
    invite_accepted_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name='Дата принятия приглашения'
    )
    
    # Системные поля
    photo = models.ImageField(upload_to='staff/photos/', blank=True, null=True, verbose_name='Фотография')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ['full_name']
    
    def __str__(self):
        return f"{self.full_name} - {self.get_position_display()}"
    
    @property
    def age(self):
        """Возраст сотрудника"""
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )
    
    @property
    def experience(self):
        """Стаж работы в годах"""
        end_date = self.dismissal_date if self.dismissal_date else date.today()
        years = end_date.year - self.hire_date.year
        if (end_date.month, end_date.day) < (self.hire_date.month, self.hire_date.day):
            years -= 1
        return years
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('staff:employee_detail', args=[str(self.id)])


class PersonalFile(models.Model):
    """Личное дело сотрудника"""
    
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    file_number = models.CharField(max_length=50, unique=True, verbose_name='Номер личного дела')
    
    # Документы (файлы)
    personal_card = models.FileField(upload_to='staff/personal_files/', blank=True, verbose_name='Личная карточка Т-2')
    employment_history = models.FileField(upload_to='staff/employment_history/', blank=True, verbose_name='Трудовая книжка/Сведения')
    application = models.FileField(upload_to='staff/applications/', blank=True, verbose_name='Заявление о приеме')
    order_file = models.FileField(upload_to='staff/orders/', blank=True, verbose_name='Приказ о приеме')  # ИСПРАВЛЕНО: order_file
    military_registration = models.FileField(upload_to='staff/military/', blank=True, verbose_name='Воинский учет')
    additional_docs = models.FileField(upload_to='staff/additional/', blank=True, verbose_name='Дополнительные документы')
    
    # Примечания
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Личное дело'
        verbose_name_plural = 'Личные дела'
    
    def __str__(self):
        return f"Личное дело №{self.file_number} - {self.employee.full_name}"


# staff/models.py - класс PassportData

class PassportData(models.Model):
    """Паспортные данные сотрудника"""
    
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    series = models.CharField(max_length=4, verbose_name='Серия', blank=True)  # Добавьте blank=True
    number = models.CharField(max_length=6, verbose_name='Номер', blank=True)  # Добавьте blank=True
    issued_by = models.TextField(verbose_name='Кем выдан', blank=True)  # Добавьте blank=True
    issue_date = models.DateField(verbose_name='Дата выдачи', null=True, blank=True)  # Измените на null=True, blank=True
    department_code = models.CharField(max_length=7, verbose_name='Код подразделения', blank=True)  # Добавьте blank=True
    
    # Файл скана паспорта
    scan = models.FileField(upload_to='staff/passports/', blank=True, null=True, verbose_name='Скан паспорта')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Паспортные данные'
        verbose_name_plural = 'Паспортные данные'
    
    def __str__(self):
        return f"Паспорт {self.series} {self.number}"


class INN(models.Model):
    """ИНН сотрудника"""
    
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    inn_number = models.CharField(max_length=12, unique=True, verbose_name='ИНН')
    scan = models.FileField(upload_to='staff/inn/', blank=True, verbose_name='Скан ИНН')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'ИНН'
        verbose_name_plural = 'ИНН'
    
    def __str__(self):
        return f"ИНН {self.inn_number}"


class SNILS(models.Model):
    """СНИЛС сотрудника"""
    
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    snils_number = models.CharField(max_length=14, unique=True, verbose_name='СНИЛС')  # Формат: XXX-XXX-XXX XX
    scan = models.FileField(upload_to='staff/snils/', blank=True, verbose_name='Скан СНИЛС')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'СНИЛС'
        verbose_name_plural = 'СНИЛС'
    
    def __str__(self):
        return f"СНИЛС {self.snils_number}"


class EducationDocument(models.Model):
    """Документы об образовании"""
    
    EDUCATION_LEVELS = [
        ('secondary', 'Среднее общее'),
        ('secondary_special', 'Среднее профессиональное'),
        ('higher', 'Высшее'),
        ('postgraduate', 'Послевузовское'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    education_level = models.CharField(max_length=20, choices=EDUCATION_LEVELS, verbose_name='Уровень образования')
    
    # Данные диплома
    document_type = models.CharField(max_length=100, verbose_name='Тип документа')  # Диплом, аттестат и т.д.
    series = models.CharField(max_length=20, blank=True, verbose_name='Серия')
    number = models.CharField(max_length=20, verbose_name='Номер')
    issue_date = models.DateField(verbose_name='Дата выдачи')
    institution = models.CharField(max_length=200, verbose_name='Учебное заведение')
    qualification = models.CharField(max_length=200, verbose_name='Квалификация')
    specialization = models.CharField(max_length=200, verbose_name='Специальность')
    
    # Файл
    scan = models.FileField(upload_to='staff/education/', verbose_name='Скан документа')
    
    # Срок действия (для некоторых документов)
    valid_until = models.DateField(null=True, blank=True, verbose_name='Срок действия до')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Документ об образовании'
        verbose_name_plural = 'Документы об образовании'
        ordering = ['-issue_date']
    
    def __str__(self):
        return f"{self.get_education_level_display()} - {self.specialization}"
    
    @property
    def is_valid(self):
        """Проверка срока действия документа"""
        if self.valid_until:
            return date.today() <= self.valid_until
        return True


class QualificationCourse(models.Model):
    """Курсы повышения квалификации"""
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    course_name = models.CharField(max_length=200, verbose_name='Название курса')
    provider = models.CharField(max_length=200, verbose_name='Организатор')
    
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(verbose_name='Дата окончания')
    hours = models.PositiveIntegerField(verbose_name='Количество часов')
    
    document_number = models.CharField(max_length=50, verbose_name='Номер документа')
    document_date = models.DateField(verbose_name='Дата документа')
    
    scan = models.FileField(upload_to='staff/courses/', blank=True, verbose_name='Скан удостоверения')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Курс повышения квалификации'
        verbose_name_plural = 'Курсы повышения квалификации'
        ordering = ['-end_date']
    
    def __str__(self):
        return f"{self.course_name} - {self.end_date.year}"
    
class EducationContract(models.Model):
    # ... другие поля ...
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True,      # <-- ДОБАВЬТЕ ЭТО
        blank=True,     # <-- ДОБАВЬТЕ ЭТО
        verbose_name='Родительский договор'
    )

class Attestation(models.Model):
    """Аттестация педагогических работников"""
    
    ATTESTATION_RESULTS = [
        ('pending', 'Ожидает'),
        ('passed', 'Аттестована'),
        ('failed', 'Не аттестована'),
        ('not_required', 'Не требуется'),
    ]
    
    CATEGORY_CHOICES = [
        ('first', 'Первая категория'),
        ('highest', 'Высшая категория'),
        ('young_specialist', 'Молодой специалист'),
        ('compliance', 'Соответствие занимаемой должности'),
        ('none', 'Без категории'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    attestation_date = models.DateField(verbose_name='Дата аттестации')
    result = models.CharField(max_length=20, choices=ATTESTATION_RESULTS, verbose_name='Результат')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, verbose_name='Категория')
    
    protocol_number = models.CharField(max_length=50, verbose_name='Номер протокола')
    protocol_date = models.DateField(verbose_name='Дата протокола')
    
    valid_until = models.DateField(verbose_name='Срок действия до')
    
    # Файл
    scan = models.FileField(upload_to='staff/attestation/', blank=True, verbose_name='Скан протокола')
    
    notes = models.TextField(blank=True, verbose_name='Примечания')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Аттестация'
        verbose_name_plural = 'Аттестации'
        ordering = ['-attestation_date']
    
    def __str__(self):
        return f"Аттестация {self.employee.full_name} - {self.attestation_date}"
    
    @property
    def is_valid(self):
        """Проверка срока действия аттестации"""
        return date.today() <= self.valid_until


class MedicalExamination(models.Model):
    """Медицинский осмотр"""
    
    EXAM_TYPES = [
        ('preliminary', 'Предварительный (при приеме)'),
        ('periodic', 'Периодический'),
        ('pre_shift', 'Предсменный'),
        ('extraordinary', 'Внеочередной'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    examination_type = models.CharField(max_length=20, choices=EXAM_TYPES, verbose_name='Тип осмотра')
    examination_date = models.DateField(verbose_name='Дата осмотра')
    valid_until = models.DateField(verbose_name='Действителен до')
    
    # Медицинская книжка
    medical_book_number = models.CharField(max_length=50, verbose_name='Номер медкнижки')
    medical_book_scan = models.FileField(upload_to='staff/medical/', blank=True, verbose_name='Скан медкнижки')
    
    # Результаты
    is_allowed = models.BooleanField(default=True, verbose_name='Допущен к работе')
    notes = models.TextField(blank=True, verbose_name='Примечания врачей')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Медицинский осмотр'
        verbose_name_plural = 'Медицинские осмотры'
        ordering = ['-examination_date']
    
    def __str__(self):
        return f"Медосмотр {self.employee.full_name} - {self.examination_date}"
    
    @property
    def is_valid(self):
        """Проверка срока действия медосмотра"""
        return date.today() <= self.valid_until
    
    @property
    def days_until_expiry(self):
        """Дней до истечения срока"""
        delta = self.valid_until - date.today()
        return delta.days


class CriminalRecordCheck(models.Model):
    """Справка об отсутствии судимости"""
    
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    check_date = models.DateField(verbose_name='Дата проверки')
    document_number = models.CharField(max_length=50, verbose_name='Номер справки')
    issued_by = models.CharField(max_length=200, verbose_name='Кем выдана')
    valid_until = models.DateField(verbose_name='Действительна до')
    
    scan = models.FileField(upload_to='staff/criminal_records/', verbose_name='Скан справки')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Справка об отсутствии судимости'
        verbose_name_plural = 'Справки об отсутствии судимости'
    
    def __str__(self):
        return f"Справка для {self.employee.full_name} от {self.check_date}"
    
    @property
    def is_valid(self):
        """Проверка срока действия справки"""
        return date.today() <= self.valid_until
    
    @property
    def days_until_expiry(self):
        """Дней до истечения срока"""
        delta = self.valid_until - date.today()
        return delta.days


class StaffPosition(models.Model):
    """Должность в штатном расписании"""
    
    POSITION_CATEGORIES = [
        ('pedagogical', 'Педагогический персонал'),
        ('support', 'Учебно-вспомогательный персонал'),
        ('administrative', 'Административный персонал'),
        ('service', 'Обслуживающий персонал'),
    ]
    
    code = models.CharField(max_length=20, unique=True, verbose_name='Код должности')
    title = models.CharField(max_length=100, verbose_name='Наименование должности')
    category = models.CharField(max_length=20, choices=POSITION_CATEGORIES, verbose_name='Категория')
    
    # Тарифные характеристики
    tariff_category = models.CharField(max_length=10, blank=True, verbose_name='Тарифный разряд')
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Базовый оклад')
    
    # Надбавки (в процентах)
    hazardous_bonus = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Надбавка за вредность (%)')
    irregular_bonus = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Надбавка за ненормированный день (%)')
    
    # Требования к образованию
    education_requirements = models.TextField(blank=True, verbose_name='Требования к образованию')
    
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Действует')
    
    class Meta:
        verbose_name = 'Должность (штатное расписание)'
        verbose_name_plural = 'Должности (штатное расписание)'
        ordering = ['category', 'title']
    
    def __str__(self):
        return f"{self.title} ({self.code})"


class StaffUnit(models.Model):
    """Штатная единица"""
    
    position = models.ForeignKey(StaffPosition, on_delete=models.CASCADE, verbose_name='Должность')
    
    # Количество ставок
    quantity = models.DecimalField(max_digits=5, decimal_places=2, default=1, verbose_name='Количество ставок')
    
    # Настройки для конкретной единицы
    salary_coefficient = models.DecimalField(max_digits=5, decimal_places=2, default=1, verbose_name='Коэффициент к окладу')
    has_hazardous = models.BooleanField(default=False, verbose_name='Вредные условия')
    has_irregular = models.BooleanField(default=False, verbose_name='Ненормированный день')
    
    # Дополнительные надбавки (фиксированные)
    additional_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Доплата (фикс)')
    
    # Занятость
    is_vacant = models.BooleanField(default=True, verbose_name='Вакансия')
    employee = models.OneToOneField(Employee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Сотрудник')
    
    # Примечания
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    class Meta:
        verbose_name = 'Штатная единица'
        verbose_name_plural = 'Штатное расписание'
    
    def __str__(self):
        status = "вакансия" if self.is_vacant else f"занято: {self.employee.full_name if self.employee else ''}"
        return f"{self.position.title} - {self.quantity} ставки ({status})"
    
    @property
    def calculated_salary(self):
        """Расчетный оклад с учетом коэффициентов"""
        base = self.position.base_salary * self.salary_coefficient
        
        if self.has_hazardous and self.position.hazardous_bonus:
            base += base * (self.position.hazardous_bonus / 100)
        
        if self.has_irregular and self.position.irregular_bonus:
            base += base * (self.position.irregular_bonus / 100)
        
        return base + self.additional_payment


class Vacancy(models.Model):
    """Вакансии"""
    
    staff_unit = models.OneToOneField(StaffUnit, on_delete=models.CASCADE, verbose_name='Штатная единица')
    
    # Информация для публикации
    requirements = models.TextField(verbose_name='Требования к кандидату')
    responsibilities = models.TextField(verbose_name='Обязанности')
    conditions = models.TextField(verbose_name='Условия работы')
    
    # Статус
    is_published = models.BooleanField(default=False, verbose_name='Опубликована')
    publish_date = models.DateField(null=True, blank=True, verbose_name='Дата публикации')
    closing_date = models.DateField(null=True, blank=True, verbose_name='Плановая дата закрытия')
    
    # Кандидаты - ИСПРАВЛЕНО: убираем through, если оно не нужно
    # candidates = models.ManyToManyField(Employee, through='VacancyCandidate', related_name='vacancies')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Вакансия'
        verbose_name_plural = 'Вакансии'
    
    def __str__(self):
        return f"Вакансия: {self.staff_unit.position.title}"


class VacancyCandidate(models.Model):
    """Кандидаты на вакансию"""
    
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('reviewed', 'Рассмотрен'),
        ('interview', 'Назначено собеседование'),
        ('rejected', 'Отказ'),
        ('accepted', 'Принят на работу'),
    ]
    
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, verbose_name='Вакансия', related_name='candidates')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник', null=True, blank=True)
    
    # Если кандидат ещё не сотрудник, храним его данные отдельно
    full_name = models.CharField(max_length=200, verbose_name='ФИО кандидата')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(verbose_name='Email')
    
    resume = models.FileField(upload_to='staff/resumes/', blank=True, verbose_name='Резюме')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус')
    interview_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата собеседования')
    notes = models.TextField(blank=True, verbose_name='Заметки')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Кандидат'
        verbose_name_plural = 'Кандидаты'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.full_name} - {self.vacancy.staff_unit.position.title}"


class LaborContract(models.Model):
    """Трудовой договор"""
    
    CONTRACT_TYPES = [
        ('indefinite', 'Бессрочный'),
        ('fixed_term', 'Срочный'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    contract_number = models.CharField(max_length=50, unique=True, verbose_name='Номер договора')
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES, verbose_name='Тип договора')
    
    # Даты
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(null=True, blank=True, verbose_name='Дата окончания (для срочного)')
    
    # Испытательный срок
    probation_period = models.PositiveIntegerField(default=0, verbose_name='Испытательный срок (дней)')
    probation_end_date = models.DateField(null=True, blank=True, verbose_name='Окончание испытательного срока')
    probation_passed = models.BooleanField(default=False, verbose_name='Испытательный срок пройден')
    
    # Файл договора
    contract_file = models.FileField(upload_to='staff/contracts/', verbose_name='Файл договора')
    
    # Дополнительная информация
    is_active = models.BooleanField(default=True, verbose_name='Действует')
    termination_date = models.DateField(null=True, blank=True, verbose_name='Дата расторжения')
    termination_reason = models.TextField(blank=True, verbose_name='Причина расторжения')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Трудовой договор'
        verbose_name_plural = 'Трудовые договоры'
        ordering = ['-start_date']
    
    def __str__(self):
        return f"Договор №{self.contract_number} от {self.start_date} - {self.employee.full_name}"
    
    @property
    def is_probation_active(self):
        """Идет ли испытательный срок"""
        if not self.probation_period or self.probation_passed:
            return False
        if not self.probation_end_date:
            return True
        return date.today() <= self.probation_end_date
    
    @property
    def days_until_expiry(self):
        """Дней до окончания срочного договора"""
        if self.contract_type != 'fixed_term' or not self.end_date:
            return None
        delta = self.end_date - date.today()
        return delta.days
    
    def save(self, *args, **kwargs):
        if self.probation_period and not self.probation_end_date:
            self.probation_end_date = self.start_date + timedelta(days=self.probation_period)
        super().save(*args, **kwargs)


class AdditionalAgreement(models.Model):
    """Дополнительное соглашение к трудовому договору"""
    
    contract = models.ForeignKey(LaborContract, on_delete=models.CASCADE, verbose_name='Трудовой договор')
    
    agreement_number = models.CharField(max_length=50, verbose_name='Номер соглашения')
    agreement_date = models.DateField(verbose_name='Дата соглашения')
    
    # Содержание изменений
    changes_description = models.TextField(verbose_name='Описание изменений')
    
    # Файл
    file = models.FileField(upload_to='staff/additional_agreements/', verbose_name='Файл соглашения')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Дополнительное соглашение'
        verbose_name_plural = 'Дополнительные соглашения'
        ordering = ['-agreement_date']
    
    def __str__(self):
        return f"Доп.соглашение №{self.agreement_number} от {self.agreement_date} к договору {self.contract.contract_number}"


class WorkSchedule(models.Model):
    """График работы"""
    
    SCHEDULE_TYPES = [
        ('5x2', 'Пятидневка (5/2)'),
        ('6x1', 'Шестидневка (6/1)'),
        ('2x2', 'Два через два'),
        ('1x3', 'Сутки через трое'),
        ('shift', 'Сменный график'),
        ('individual', 'Индивидуальный'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Название графика')
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES, verbose_name='Тип графика')
    
    # Для каких категорий сотрудников
    employee_types = models.CharField(max_length=200, verbose_name='Категории сотрудников')
    
    # Норма часов
    weekly_hours = models.PositiveIntegerField(default=40, verbose_name='Норма часов в неделю')
    daily_hours = models.PositiveIntegerField(default=8, verbose_name='Норма часов в день')
    
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Действует')
    
    class Meta:
        verbose_name = 'График работы'
        verbose_name_plural = 'Графики работы'
    
    def __str__(self):
        return f"{self.name} - {self.get_schedule_type_display()}"


class Timesheet(models.Model):
    """Табель учета рабочего времени"""
    
    month = models.IntegerField(choices=[(i, i) for i in range(1, 13)], verbose_name='Месяц')
    year = models.IntegerField(verbose_name='Год')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Кто составил')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_closed = models.BooleanField(default=False, verbose_name='Закрыт')
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Табель учета рабочего времени'
        verbose_name_plural = 'Табели учета рабочего времени'
        unique_together = ['month', 'year']
    
    def __str__(self):
        return f"Табель за {self.month}.{self.year}"
    
    @property
    def month_name(self):
        months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        return months[self.month - 1]
    
    def get_days_in_month(self):
        """Возвращает количество дней в месяце"""
        import calendar  # <-- Убедитесь, что импорт внутри метода
        return calendar.monthrange(self.year, self.month)[1]
    
    def get_default_attendance(self, employee, day):
        """
        Определяет значение по умолчанию для конкретного дня
        """
        date_obj = date(self.year, self.month, day)
        
        # Проверяем отпуск
        leave = LeaveSchedule.objects.filter(
            employee=employee,
            start_date__lte=date_obj,
            end_date__gte=date_obj,
            status__in=['planned', 'approved', 'in_progress']
        ).first()
        if leave:
            return 'OT'  # Отпуск
        
        # Проверяем выходные
        schedule = EmployeeWorkSchedule.objects.filter(
            employee=employee,
            start_date__lte=date_obj,
            end_date__isnull=True
        ).first()
        
        if schedule and schedule.schedule_template:
            # Проверяем по графику
            template = schedule.schedule_template
            if template.schedule_type in ['5x2', '6x1']:
                # Простая проверка выходных
                if template.schedule_type == '5x2':
                    if date_obj.weekday() >= 5:  # Суббота или воскресенье
                        return 'V'  # Выходной
                elif template.schedule_type == '6x1':
                    if date_obj.weekday() == 6:  # Воскресенье
                        return 'V'
        
        # По умолчанию - явка
        return 'I'
    
    def initialize_entries(self):
        """
        Инициализация записей табеля для всех активных сотрудников
        """
        employees = Employee.objects.filter(is_active=True)
        days_in_month = self.get_days_in_month()
        
        for employee in employees:
            entry, created = TimesheetEntry.objects.get_or_create(
                timesheet=self,
                employee=employee
            )
            
            # Устанавливаем значения по умолчанию для каждого дня
            for day in range(1, days_in_month + 1):
                default_code = self.get_default_attendance(employee, day)
                setattr(entry, f'day_{day}', default_code)
            
            entry.calculate_totals()
            entry.save()
    


class TimesheetEntry(models.Model):
    """Запись в табеле (по дням)"""
    
    ATTENDANCE_CODES = [
        ('I', 'Явка (полный день)'),
        ('N', 'Ночная работа'),
        ('RV', 'Работа в выходной/праздник'),
        ('C', 'Сверхурочная работа'),
        ('B', 'Больничный'),
        ('OT', 'Отпуск'),
        ('OZ', 'Отпуск за свой счет'),
        ('UO', 'Учебный отпуск'),
        ('DO', 'Отпуск по уходу за ребенком'),
        ('K', 'Командировка'),
        ('G', 'Прогул'),
        ('NN', 'Неявка по невыясненной причине'),
        ('PR', 'Отстранение от работы'),
        ('V', 'Выходной'),
    ]
    
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, verbose_name='Табель', related_name='entries')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    day_1 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='1')
    day_2 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='2')
    day_3 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='3')
    day_4 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='4')
    day_5 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='5')
    day_6 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='6')
    day_7 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='7')
    day_8 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='8')
    day_9 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='9')
    day_10 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='10')
    day_11 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='11')
    day_12 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='12')
    day_13 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='13')
    day_14 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='14')
    day_15 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='15')
    day_16 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='16')
    day_17 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='17')
    day_18 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='18')
    day_19 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='19')
    day_20 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='20')
    day_21 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='21')
    day_22 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='22')
    day_23 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='23')
    day_24 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='24')
    day_25 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='25')
    day_26 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='26')
    day_27 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='27')
    day_28 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='28')
    day_29 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='29')
    day_30 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='30')
    day_31 = models.CharField(max_length=5, choices=ATTENDANCE_CODES, default='V', verbose_name='31')
    
    # Итоги
    total_days = models.PositiveIntegerField(default=0, verbose_name='Всего дней')
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Всего часов')
    
    # Сверхурочные
    overtime_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Сверхурочные часы')
    night_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Ночные часы')
    holiday_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Часы в праздники')
    
    # Отстранения
    suspension_start = models.DateField(null=True, blank=True, verbose_name='Начало отстранения')
    suspension_end = models.DateField(null=True, blank=True, verbose_name='Окончание отстранения')
    suspension_reason = models.CharField(max_length=200, blank=True, verbose_name='Причина отстранения')
    suspension_order = models.CharField(max_length=50, blank=True, verbose_name='Приказ об отстранении')
    
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    # Хранение прикрепленных документов (JSON)
    absence_documents = models.JSONField(default=dict, blank=True, verbose_name='Документы отсутствия')
    
    # Причины отсутствия по дням (JSON)
    absence_reasons = models.JSONField(default=dict, blank=True, verbose_name='Причины отсутствия')
    
    class Meta:
        verbose_name = 'Запись в табеле'
        verbose_name_plural = 'Записи в табеле'
        unique_together = ['timesheet', 'employee']
    
    def __str__(self):
        return f"Табель {self.employee.full_name} - {self.timesheet.month}.{self.timesheet.year}"
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ПРИЧИНАМИ ОТСУТСТВИЯ ====================
    
    def set_absence_reason(self, day, reason, description=''):
        """
        Установка причины отсутствия для конкретного дня
        """
        if not self.absence_reasons:
            self.absence_reasons = {}
        
        self.absence_reasons[str(day)] = {
            'reason': reason,
            'description': description,
            'set_at': timezone.now().isoformat()
        }
        self.save()
        return True
    
    def get_absence_reason(self, day):
        """
        Получить причину отсутствия для дня
        """
        return self.absence_reasons.get(str(day), None)
    
    def clear_absence_reason(self, day):
        """
        Очистить причину отсутствия для дня
        """
        if str(day) in self.absence_reasons:
            del self.absence_reasons[str(day)]
            self.save()
            return True
        return False
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ДОКУМЕНТАМИ ====================
    
    def add_absence_document(self, doc_id, doc_info):
        """
        Добавление информации о документе (без сохранения файла)
        """
        if not self.absence_documents:
            self.absence_documents = {}
        self.absence_documents[doc_id] = doc_info
        self.save()
        return doc_id
    
    def remove_absence_document(self, doc_id):
        """
        Удаление информации о документе (файл удаляется отдельно в views)
        """
        if doc_id in self.absence_documents:
            del self.absence_documents[doc_id]
            self.save()
            return True
        return False
    
    def get_documents_for_day(self, day):
        """
        Получить все документы для конкретного дня
        """
        docs = []
        for doc_id, doc_info in self.absence_documents.items():
            if doc_info.get('day') == day:
                docs.append({'id': doc_id, **doc_info})
        return docs
    
    def has_document_for_day(self, day):
        """
        Проверить, есть ли документы для дня
        """
        for doc_info in self.absence_documents.values():
            if doc_info.get('day') == day:
                return True
        return False
    
    def get_all_documents(self):
        """
        Получить все документы
        """
        return [{'id': doc_id, **doc_info} for doc_id, doc_info in self.absence_documents.items()]
    
    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ПОСЕЩАЕМОСТЬЮ ====================
    
    def get_attendance_display(self, day):
        """Возвращает отображаемое название кода"""
        codes = dict(self.ATTENDANCE_CODES)
        code = getattr(self, f'day_{day}', 'V')
        return codes.get(code, code)
    
    def set_attendance(self, day, code, reason=None, description=''):
        """
        Установить код явки с возможностью сохранения причины
        """
        setattr(self, f'day_{day}', code)
        
        # Сохраняем причину, если указана
        if reason:
            self.set_absence_reason(day, reason, description)
        else:
            # Если нет причины, очищаем
            self.clear_absence_reason(day)
        
        self.calculate_totals()
        self.save()
    
    # ==================== РАСЧЕТ ИТОГОВ ====================
    
    def calculate_totals(self):
        """
        Расчет итогов по табелю
        """
        days_in_month = self.timesheet.get_days_in_month()
        
        # Коды, считающиеся рабочими днями
        work_codes = ['I', 'N', 'RV', 'C']
        
        # Словарь для подсчета по типам
        totals = {
            'days': 0,
            'hours': 0,
            'overtime': 0,
            'night': 0,
            'holiday': 0,
        }
        
        for day in range(1, days_in_month + 1):
            code = getattr(self, f'day_{day}', 'V')
            
            # Получаем норму часов в день
            daily_hours = 8  # стандартная продолжительность
            date_obj = date(self.timesheet.year, self.timesheet.month, day)
            schedule = EmployeeWorkSchedule.objects.filter(
                employee=self.employee,
                start_date__lte=date_obj,
                end_date__isnull=True
            ).first()
            if schedule and schedule.schedule_template:
                daily_hours = schedule.schedule_template.daily_hours
            
            if code in work_codes:
                totals['days'] += 1
                totals['hours'] += daily_hours
            
            if code == 'C':  # Сверхурочные
                totals['overtime'] += 2  # Условно 2 часа сверхурочных
            elif code == 'N':  # Ночные
                totals['night'] += daily_hours
            elif code == 'RV':  # Работа в выходной
                totals['holiday'] += daily_hours
        
        self.total_days = totals['days']
        self.total_hours = totals['hours']
        self.overtime_hours = totals['overtime']
        self.night_hours = totals['night']
        self.holiday_hours = totals['holiday']
        
        return self
    
    
# staff/models.py - добавить в конец файла

class OvertimeTracking(models.Model):
    """Отслеживание сверхурочных часов за год"""
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    year = models.IntegerField(verbose_name='Год')
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='Всего часов')
    
    class Meta:
        verbose_name = 'Отслеживание сверхурочных'
        verbose_name_plural = 'Отслеживание сверхурочных'
        unique_together = ['employee', 'year']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.year}: {self.total_hours} ч."
    
    def can_add_hours(self, hours):
        """Проверка возможности добавить часы (лимит 120 часов в год)"""
        return self.total_hours + hours <= 120
    
    def add_hours(self, hours):
        """Добавить сверхурочные часы"""
        if self.can_add_hours(hours):
            self.total_hours += hours
            self.save()
            return True
        return False

class LeaveSchedule(models.Model):
    """График отпусков"""
    
    LEAVE_TYPES = [
        ('annual', 'Ежегодный основной'),
        ('additional', 'Дополнительный'),
        ('study', 'Учебный'),
        ('maternity', 'По беременности и родам'),
        ('childcare', 'По уходу за ребенком'),
        ('unpaid', 'Без сохранения зарплаты'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    year = models.IntegerField(verbose_name='Год')
    
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, default='annual', verbose_name='Тип отпуска')
    
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(verbose_name='Дата окончания')
    
    # Продолжительность (автоматически вычисляется)
    duration = models.PositiveIntegerField(verbose_name='Количество дней')
    
    # Для учета категорий (28, 42, 56 дней)
    category_duration = models.PositiveIntegerField(default=28, verbose_name='Продолжительность по категории')
    
    # Статус
    STATUS_CHOICES = [
        ('planned', 'Запланирован'),
        ('approved', 'Утвержден'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned', verbose_name='Статус')
    
    # Заявление
    application_date = models.DateField(verbose_name='Дата заявления')
    application_file = models.FileField(upload_to='staff/leave_applications/', blank=True, verbose_name='Заявление')
    
    # Приказ
    order_number = models.CharField(max_length=50, blank=True, verbose_name='Номер приказа')
    order_date = models.DateField(null=True, blank=True, verbose_name='Дата приказа')
    order_file = models.FileField(upload_to='staff/leave_orders/', blank=True, verbose_name='Файл приказа')
    
    # Контроль наложения отпусков
    replacement_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, 
                                            related_name='replacing_leaves', verbose_name='Замещающий сотрудник')
    
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'График отпусков'
        verbose_name_plural = 'Графики отпусков'
        ordering = ['year', 'start_date']
        unique_together = ['employee', 'year', 'start_date']
    
    def __str__(self):
        return f"Отпуск {self.employee.full_name} - {self.start_date} - {self.end_date}"
    
    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            self.duration = (self.end_date - self.start_date).days + 1
        super().save(*args, **kwargs)
    
    @property
    def is_overlapping(self):
        """Проверка наложения отпусков с другими сотрудниками (для замещения)"""
        if not self.replacement_employee:
            return False
        
        overlapping = LeaveSchedule.objects.filter(
            employee=self.replacement_employee,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
            status__in=['planned', 'approved', 'in_progress']
        ).exclude(pk=self.pk)
        
        return overlapping.exists()


# staff/models.py - проверьте наличие этой модели

class LeaveRequest(models.Model):
    """Заявление на отпуск"""
    
    LEAVE_TYPES = [
        ('annual', 'Ежегодный основной'),
        ('additional', 'Дополнительный'),
        ('study', 'Учебный'),
        ('maternity', 'По беременности и родам'),
        ('childcare', 'По уходу за ребенком'),
        ('unpaid', 'Без сохранения зарплаты'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Утвержден'),
        ('rejected', 'Отклонен'),
        ('rescheduled', 'Перенесен'),
    ]
    
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, verbose_name='Сотрудник')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES, verbose_name='Тип отпуска')
    start_date = models.DateField(verbose_name='Желаемая дата начала')
    end_date = models.DateField(verbose_name='Желаемая дата окончания')
    duration = models.PositiveIntegerField(verbose_name='Количество дней')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    request_date = models.DateField(auto_now_add=True, verbose_name='Дата подачи')
    processed_date = models.DateField(null=True, blank=True, verbose_name='Дата рассмотрения')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Рассмотрел')
    comments = models.TextField(blank=True, verbose_name='Комментарии')
    leave_schedule = models.ForeignKey('LeaveSchedule', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Запись в графике')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Заявление на отпуск'
        verbose_name_plural = 'Заявления на отпуск'
        ordering = ['-request_date']
    
    def __str__(self):
        return f"Заявление от {self.employee.full_name} - {self.start_date}"


class DisciplinaryAction(models.Model):
    """Дисциплинарное взыскание"""
    
    ACTION_TYPES = [
        ('remark', 'Замечание'),
        ('reprimand', 'Выговор'),
        ('severe_reprimand', 'Строгий выговор'),
        ('warning', 'Предупреждение о неполном соответствии'),
        ('dismissal', 'Увольнение'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name='Вид взыскания')
    violation_description = models.TextField(verbose_name='Описание нарушения')
    
    # Приказ
    order_number = models.CharField(max_length=50, verbose_name='Номер приказа')
    order_date = models.DateField(verbose_name='Дата приказа')
    order_file = models.FileField(upload_to='staff/disciplinary_orders/', blank=True, verbose_name='Файл приказа')
    
    # Срок действия
    issue_date = models.DateField(verbose_name='Дата наложения')
    valid_until = models.DateField(verbose_name='Действует до')
    
    # Автоматическое снятие
    is_active = models.BooleanField(default=True, verbose_name='Действует')
    lifted_date = models.DateField(null=True, blank=True, verbose_name='Дата снятия')
    lifted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='lifted_actions', verbose_name='Снял')
    lifting_order = models.CharField(max_length=50, blank=True, verbose_name='Приказ о снятии')
    
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Дисциплинарное взыскание'
        verbose_name_plural = 'Дисциплинарные взыскания'
        ordering = ['-order_date']
    
    def __str__(self):
        return f"{self.get_action_type_display()} - {self.employee.full_name} от {self.order_date}"
    
    @property
    def days_until_expiry(self):
        """Дней до истечения срока"""
        if not self.is_active:
            return 0
        delta = self.valid_until - date.today()
        return delta.days


class Encouragement(models.Model):
    """Поощрения сотрудников"""
    
    ENCOURAGEMENT_TYPES = [
        ('gratitude', 'Благодарность'),
        ('bonus', 'Премия'),
        ('honorary_certificate', 'Почетная грамота'),
        ('valuable_gift', 'Ценный подарок'),
        ('thanks_letter', 'Благодарственное письмо'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    encouragement_type = models.CharField(max_length=20, choices=ENCOURAGEMENT_TYPES, verbose_name='Вид поощрения')
    description = models.TextField(verbose_name='Описание')
    
    # Приказ
    order_number = models.CharField(max_length=50, verbose_name='Номер приказа')
    order_date = models.DateField(verbose_name='Дата приказа')
    order_file = models.FileField(upload_to='staff/encouragement_orders/', blank=True, verbose_name='Файл приказа')
    
    # Для премии
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Сумма премии')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Поощрение'
        verbose_name_plural = 'Поощрения'
        ordering = ['-order_date']
    
    def __str__(self):
        return f"{self.get_encouragement_type_display()} - {self.employee.full_name} от {self.order_date}"


class DispensaryRecord(models.Model):
    """Учет диспансеризации"""
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    # Год диспансеризации
    year = models.IntegerField(verbose_name='Год')
    
    # Освобождение от работы
    exemption_start = models.DateField(verbose_name='Начало освобождения')
    exemption_end = models.DateField(verbose_name='Окончание освобождения')
    exemption_days = models.PositiveIntegerField(verbose_name='Количество дней')
    
    # Подтверждающие справки
    medical_certificate = models.FileField(upload_to='staff/dispensary/', verbose_name='Медицинская справка')
    
    # Результаты
    STATUS_CHOICES = [
        ('planned', 'Запланирована'),
        ('in_progress', 'Проходит'),
        ('completed', 'Пройдена'),
        ('skipped', 'Пропущена'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned', verbose_name='Статус')
    
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Диспансеризация'
        verbose_name_plural = 'Диспансеризация'
        unique_together = ['employee', 'year']
    
    def __str__(self):
        return f"Диспансеризация {self.employee.full_name} - {self.year}"


class SalaryCalculation(models.Model):
    """Расчет заработной платы"""
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    month = models.IntegerField(choices=[(i, i) for i in range(1, 13)], verbose_name='Месяц')
    year = models.IntegerField(verbose_name='Год')
    
    # Связь с табелем
    timesheet = models.ForeignKey(Timesheet, on_delete=models.SET_NULL, null=True, verbose_name='Табель')
    
    # Базовая часть
    base_salary = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Оклад/ставка')
    worked_hours = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='Отработано часов')
    standard_hours = models.DecimalField(max_digits=6, decimal_places=2, verbose_name='Норма часов')
    
    # Надбавки
    hazardous_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='За вредность')
    part_time_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='За совместительство')
    irregular_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='За ненормированный день')
    overtime_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Сверхурочные')
    night_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Ночные')
    holiday_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Праздничные')
    
    # Стимулирующие
    stimulating_payments = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Стимулирующие выплаты')
    
    # Больничные и отпускные
    sick_leave = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Больничные')
    vacation_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Отпускные')
    
    # Итог
    total_accrued = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Всего начислено')
    
    # Налоги (упрощенно)
    income_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='НДФЛ')
    
    # К выплате
    total_payable = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='К выплате')
    
    # Статус
    STATUS_CHOICES = [
        ('calculated', 'Рассчитано'),
        ('approved', 'Утверждено'),
        ('paid', 'Выплачено'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='calculated', verbose_name='Статус')
    
    payment_date = models.DateField(null=True, blank=True, verbose_name='Дата выплаты')
    
    # Расчетный листок
    payslip = models.FileField(upload_to='staff/payslips/', blank=True, verbose_name='Расчетный листок')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Расчет заработной платы'
        verbose_name_plural = 'Расчеты заработной платы'
        unique_together = ['employee', 'month', 'year']
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"Зарплата {self.employee.full_name} за {self.month}.{self.year}"
    
    @property
    def month_name(self):
        months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
        return months[self.month - 1]


class SalaryComponent(models.Model):
    """Детализация расчета зарплаты (составляющие)"""
    
    COMPONENT_TYPES = [
        ('base', 'Оклад'),
        ('bonus', 'Надбавка'),
        ('stimulating', 'Стимулирующая'),
        ('sick', 'Больничный'),
        ('vacation', 'Отпускные'),
        ('deduction', 'Удержание'),
    ]
    
    salary_calculation = models.ForeignKey(SalaryCalculation, on_delete=models.CASCADE, verbose_name='Расчет')
    
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPES, verbose_name='Тип')
    name = models.CharField(max_length=100, verbose_name='Название')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    class Meta:
        verbose_name = 'Компонент зарплаты'
        verbose_name_plural = 'Компоненты зарплаты'
    
    def __str__(self):
        return f"{self.name}: {self.amount}"
    
class HireOrder(models.Model):
    """Приказ о приеме на работу (форма Т-1)"""
    
    # Номер и дата
    order_number = models.CharField(max_length=50, unique=True, verbose_name='Номер приказа')
    order_date = models.DateField(default=date.today, verbose_name='Дата приказа')
    
    # Связь с сотрудником
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник')
    
    # Данные для приказа
    hire_date = models.DateField(verbose_name='Дата приема')
    position = models.CharField(max_length=200, verbose_name='Должность')
    department = models.CharField(max_length=200, verbose_name='Подразделение', blank=True, 
                                  default='Детский сад')
    
    # Условия приема
    EMPLOYMENT_CONDITIONS = [
        ('main', 'Постоянно'),
        ('fixed_term', 'Срочный договор'),
        ('part_time', 'Совместительство'),
        ('temporary', 'Временно'),
    ]
    
    employment_condition = models.CharField(max_length=20, choices=EMPLOYMENT_CONDITIONS, 
                                           default='main', verbose_name='Условия приема')
    
    # Тарифная ставка
    tariff_rate = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Тарифная ставка (оклад)')
    
    # Надбавки
    has_bonus = models.BooleanField(default=False, verbose_name='Есть надбавки')
    bonus_description = models.CharField(max_length=200, blank=True, verbose_name='Описание надбавок')
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                      verbose_name='Сумма надбавок')
    
    # Испытательный срок
    probation_period = models.IntegerField(default=0, verbose_name='Испытательный срок (мес.)')
    
    # Основание
    basis_documents = models.TextField(verbose_name='Основание', 
                                       default='Заявление сотрудника, Трудовой договор')
    
    # Руководитель
    director_name = models.CharField(max_length=200, verbose_name='ФИО заведующей', 
                                    default='Михайлова Надежда Васильевна')
    director_position = models.CharField(max_length=200, verbose_name='Должность руководителя',
                                        default='Заведующая МБДОУ "Рябинушка"')
    
    # Сотрудник ознакомлен
    employee_acquainted = models.BooleanField(default=False, verbose_name='Сотрудник ознакомлен')
    acquainted_date = models.DateField(null=True, blank=True, verbose_name='Дата ознакомления')
    
    # Файл приказа (сгенерированный PDF)
    order_file = models.FileField(upload_to='staff/hire_orders/', blank=True, null=True, 
                                 verbose_name='Файл приказа')
    
    # Статус
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('issued', 'Издан'),
        ('cancelled', 'Отменен'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='Статус')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Кто создал')
    
    class Meta:
        verbose_name = 'Приказ о приеме'
        verbose_name_plural = 'Приказы о приеме'
        ordering = ['-order_date', '-order_number']
    
    def __str__(self):
        return f"Приказ №{self.order_number} от {self.order_date} - {self.employee.full_name}"
    
    def generate_order_number(self):
        """Генерация номера приказа"""
        year = self.order_date.year
        last_order = HireOrder.objects.filter(order_date__year=year).order_by('-id').first()
        
        if last_order and last_order.order_number:
            try:
                last_num = int(last_order.order_number.split('-')[-1])
                new_num = last_num + 1
            except:
                new_num = 1
        else:
            new_num = 1
        
        return f"{year}-{new_num:04d}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
        
        
        
# staff/models.py (добавьте в конец файла)

class PayrollType(models.Model):
    """Базовый класс для видов начислений и удержаний"""
    
    CALCULATION_TYPES = [
        ('fixed', 'Фиксированная сумма'),
        ('percent', 'Процент от оклада'),
        ('formula', 'По формуле (сложный расчет)'),
    ]
    
    code = models.CharField(max_length=50, unique=True, verbose_name='Код')
    name = models.CharField(max_length=200, verbose_name='Наименование')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    # Тип расчета
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPES, verbose_name='Тип расчета')
    
    # Для фиксированной суммы или процента
    base_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Базовое значение')
    
    # Признак, что это начисление или удержание
    is_accrual = models.BooleanField(default=True, verbose_name='Начисление')  # False - удержание
    
    # Влияет на расчет налогов (для сложных случаев)
    is_taxable = models.BooleanField(default=True, verbose_name='Облагается налогом')
    include_in_average = models.BooleanField(default=True, verbose_name='Учитывается в среднем заработке')
    
    # Для надбавок за стаж (процент от оклада в зависимости от стажа)
    # Храним как JSON: [{"years_from": 0, "years_to": 3, "percent": 5}, ...]
    seniority_scale = models.JSONField(null=True, blank=True, verbose_name='Шкала за стаж')
    
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Вид начисления/удержания'
        verbose_name_plural = 'Виды начислений и удержаний'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class EmployeePayrollAssignment(models.Model):
    """Назначение начислений сотруднику (плановые начисления)"""
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name='Сотрудник', related_name='payroll_assignments')
    payroll_type = models.ForeignKey(PayrollType, on_delete=models.CASCADE, verbose_name='Вид начисления')
    
    # Дата начала и окончания действия
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(null=True, blank=True, verbose_name='Дата окончания')
    
    # Конкретное значение для этого сотрудника (если нужно переопределить)
    custom_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Индивидуальное значение')
    
    # Для процентов - от какой базы считать
    # options: 'base_salary', 'total_accrued'
    calculation_base = models.CharField(max_length=50, default='base_salary', verbose_name='База для расчета')
    
    # Приказ-основание
    order_number = models.CharField(max_length=100, blank=True, verbose_name='Номер приказа')
    order_date = models.DateField(null=True, blank=True, verbose_name='Дата приказа')
    
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Назначение начисления'
        verbose_name_plural = 'Назначения начислений'
        ordering = ['employee', 'start_date']
    
    def __str__(self):
        return f"{self.employee} - {self.payroll_type.name}"


# staff/models.py - проверьте модель EmployeeWorkSchedule

class EmployeeWorkSchedule(models.Model):
    """Назначение графика работы сотруднику"""
    
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, verbose_name='Сотрудник', related_name='work_schedules')
    schedule_template = models.ForeignKey('WorkSchedule', on_delete=models.CASCADE, verbose_name='Шаблон графика', null=True, default=None)
    
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(null=True, blank=True, verbose_name='Дата окончания')
    
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'График работы сотрудника'
        verbose_name_plural = 'Графики работы сотрудников'
        ordering = ['-start_date', 'employee']
    
    def __str__(self):
        status = "активен" if self.is_active else "неактивен"
        return f"{self.employee} - {self.schedule_template} с {self.start_date} ({status})"
