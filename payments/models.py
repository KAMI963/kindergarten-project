# payments/models.py
from django.db import models
from django.utils import timezone
from children.models import Child, Group
from decimal import Decimal
import calendar
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from attendance.models import AttendanceRecord, AttendanceSheet, Meal as AttendanceMeal
from django.conf import settings


class Tariff(models.Model):
    """Тарифы на основные услуги (пребывание + питание)"""
    AGE_CATEGORY_CHOICES = [
        ('nursery', 'Ясельная (1.5-3 года)'),
        ('kindergarten', 'Сад (3-7 лет)'),
    ]
    
    age_category = models.CharField(
        max_length=20, 
        choices=AGE_CATEGORY_CHOICES,
        verbose_name='Возрастная категория'
    )
    year = models.IntegerField(verbose_name='Год')
    
    # Полная стоимость за месяц (абонентская плата + питание)
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name='Общая сумма за месяц'
    )
    
    # Разделение на составляющие
    content_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name='Абонентская плата (содержание)'
    )
    food_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name='Питание'
    )
    
    # Дневные ставки (рассчитываются автоматически)
    daily_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name='Дневной тариф (содержание)'
    )
    food_daily_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name='Дневной тариф (питание)'
    )
    
    class Meta:
        unique_together = ['age_category', 'year']
        ordering = ['-year', 'age_category']
        verbose_name = 'Тариф'
        verbose_name_plural = 'Тарифы'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_age_category_display()} - {self.year}: {self.total_amount} ₽"


class AdditionalService(models.Model):
    """Дополнительные услуги (кружки, секции)"""
    SERVICE_TYPE_CHOICES = [
        ('circle', 'Кружок'),
        ('section', 'Секция'),
        ('studio', 'Студия'),
        ('course', 'Курс'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Название услуги')
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, verbose_name='Тип услуги')
    description = models.TextField(blank=True, verbose_name='Описание')
    price_per_lesson = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=450,
        verbose_name='Стоимость одного занятия'
    )
    price_per_month = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        verbose_name='Стоимость в месяц (полная)'
    )
    age_min = models.IntegerField(default=3, verbose_name='Минимальный возраст')
    age_max = models.IntegerField(default=7, verbose_name='Максимальный возраст')
    teacher = models.CharField(max_length=100, blank=True, verbose_name='Преподаватель')
    teacher_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='taught_services',
        verbose_name='Преподаватель (пользователь)'
    )
    schedule = models.CharField(max_length=200, blank=True, verbose_name='Расписание')
    schedule_details = models.JSONField(default=dict, blank=True, verbose_name='Детали расписания')
    program = models.TextField(blank=True, verbose_name='Программа')
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    max_students = models.IntegerField(default=10, verbose_name='Максимум детей')
    start_date = models.DateField(null=True, blank=True, verbose_name='Дата начала')
    end_date = models.DateField(null=True, blank=True, verbose_name='Дата окончания')
    
    class Meta:
        verbose_name = 'Дополнительная услуга'
        verbose_name_plural = 'Дополнительные услуги'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.price_per_lesson} ₽/занятие"


class GroupServiceAssignment(models.Model):
    """Назначение кружка группе детей"""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')
    service = models.ForeignKey(AdditionalService, on_delete=models.CASCADE, verbose_name='Услуга')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['group', 'service']
        verbose_name = 'Назначение кружка группе'
        verbose_name_plural = 'Назначения кружков группам'
    
    def __str__(self):
        return f"{self.service.name} - {self.group.name}"


class ServiceAttendance(models.Model):
    """Посещаемость занятий кружка"""
    ABSENCE_REASONS = [
        ('present', 'Присутствовал'),
        ('absent', 'Отсутствовал'),
        ('sick', 'Болезнь'),
        ('vacation', 'Отпуск'),
        ('family_reasons', 'Семейные обстоятельства'),
    ]
    
    enrollment = models.ForeignKey('ServiceEnrollment', on_delete=models.CASCADE, related_name='attendances', verbose_name='Запись')
    date = models.DateField(verbose_name='Дата занятия')
    status = models.CharField(max_length=20, choices=ABSENCE_REASONS, default='present', verbose_name='Статус')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='Отметил')
    marked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['enrollment', 'date']
        verbose_name = 'Посещаемость занятия'
        verbose_name_plural = 'Посещаемость занятий'
        ordering = ['-date']
    
    def __str__(self):
        status_display = dict(self.ABSENCE_REASONS).get(self.status, self.status)
        return f"{self.enrollment.child.full_name} - {self.date} - {status_display}"


class ServiceEnrollment(models.Model):
    """Запись ребенка на дополнительную услугу"""
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Зачислен'),
        ('rejected', 'Отказано'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменен'),
    ]
    
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='service_enrollments', verbose_name='Ребенок')
    service = models.ForeignKey(AdditionalService, on_delete=models.CASCADE, verbose_name='Услуга')
    enrollment_date = models.DateField(auto_now_add=True, verbose_name='Дата подачи')
    start_date = models.DateField(verbose_name='Дата начала занятий')
    end_date = models.DateField(null=True, blank=True, verbose_name='Дата окончания')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    contract_signed = models.BooleanField(default=False, verbose_name='Договор подписан')
    contract_signed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата подписания договора')
    
    class Meta:
        unique_together = ['child', 'service', 'start_date']
        verbose_name = 'Запись на услугу'
        verbose_name_plural = 'Записи на услуги'
        ordering = ['-enrollment_date']
    
    def __str__(self):
        return f"{self.child.full_name} - {self.service.name}"
    
    def is_active(self):
        return self.status == 'approved' and (not self.end_date or self.end_date >= date.today())
    
    def get_attendance_count(self, month=None, year=None):
        """Получить количество посещенных занятий за месяц"""
        queryset = self.attendances.filter(status='present')
        if month and year:
            queryset = queryset.filter(date__month=month, date__year=year)
        return queryset.count()
    
    def calculate_monthly_cost(self, month=None, year=None):
        """
        Расчет стоимости за месяц на основе количества посещенных занятий.
        Плата взимается ТОЛЬКО за фактически посещенные занятия.
        """
        if not month or not year:
            now = timezone.now()
            month = now.month
            year = now.year
        
        attendance_count = self.get_attendance_count(month, year)
        return self.service.price_per_lesson * attendance_count


class ChildAccount(models.Model):
    """Лицевой счет ребенка"""
    child = models.OneToOneField(Child, on_delete=models.CASCADE, related_name='account', verbose_name='Ребенок')
    account_number = models.CharField(max_length=50, unique=True, verbose_name='Номер лицевого счета')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Баланс')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Лицевой счет'
        verbose_name_plural = 'Лицевые счета'
    
    def __str__(self):
        return f"Лицевой счет {self.child.full_name}: {self.account_number}"
    
    def save(self, *args, **kwargs):
        if not self.account_number:
            year = timezone.now().year
            last_account = ChildAccount.objects.filter(account_number__startswith=f'ЛСГ{year}').order_by('-account_number').first()
            if last_account:
                last_num = int(last_account.account_number[7:])
                new_num = last_num + 1
            else:
                new_num = 1
            self.account_number = f'ЛСГ{year}{new_num:06d}'
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Платежи с полным расчетом"""
    STATUS_CHOICES = (
        ('pending', 'Ожидает оплаты'),
        ('completed', 'Оплачено'),
        ('failed', 'Ошибка оплаты'),
        ('refunded', 'Возвращено'),
        ('overdue', 'Просрочено'),
    )
    
    child = models.ForeignKey(Child, on_delete=models.CASCADE, verbose_name='Ребенок')
    month = models.IntegerField(verbose_name='Месяц')
    year = models.IntegerField(verbose_name='Год')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Базовая сумма (сад + питание)')
    attendance_days = models.IntegerField(default=0, verbose_name='Фактические дни посещения сада')
    total_days = models.IntegerField(default=0, verbose_name='Всего рабочих дней в месяце')
    food_days = models.IntegerField(default=0, verbose_name='Дни питания')
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Дневной тариф (содержание)')
    food_daily_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Дневной тариф (питание)')
    
    additional_services_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Дополнительные услуги')
    additional_services_details = models.JSONField(default=dict, blank=True, verbose_name='Детали доп. услуг')
    
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Ставка компенсации (0-1)')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Сумма компенсации')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Итого к оплате')
    
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        unique_together = ['child', 'month', 'year']
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"Платеж {self.child.full_name} - {self.month}.{self.year} - {self.amount} ₽"
    
    def _get_working_days_in_month(self, year, month):
        """Получить количество рабочих дней в месяце (без учета выходных)"""
        working_days = 0
        _, last_day = calendar.monthrange(year, month)
        for day in range(1, last_day + 1):
            current_date = date(year, month, day)
            if current_date.weekday() < 5:
                working_days += 1
        return working_days
    
    def calculate_amount(self):
        """
        Расчёт платежа с гарантированным применением тарифа заведующей.
        """
        year = self.year
        month = self.month

        # ========== 1. РАБОЧИЕ ДНИ И ПОСЕЩЕНИЯ ==========
        total_working_days = 0
        present_days = 0
        
        try:
            sheet = AttendanceSheet.objects.get(
                group=self.child.group, month=month, year=year
            )
            record = AttendanceRecord.objects.get(sheet=sheet, child=self.child)

            _, last_day = calendar.monthrange(year, month)
            for day in range(1, last_day + 1):
                current_date = date(year, month, day)
                if sheet.is_holiday_date(current_date):
                    continue
                total_working_days += 1
                status = getattr(record, f'day_{day}', '')
                if status == 'present':
                    present_days += 1
        except (AttendanceSheet.DoesNotExist, AttendanceRecord.DoesNotExist):
            total_working_days = self._get_working_days_in_month(year, month)
            present_days = 0

        self.total_days = total_working_days
        self.attendance_days = present_days

        # ========== 2. ДНИ ПИТАНИЯ ==========
        meal_days = AttendanceMeal.objects.filter(
            child=self.child,
            date__month=month,
            date__year=year,
            eaten=True
        ).values('date').distinct().count()
        self.food_days = meal_days

        # ========== 3. ТАРИФ ЗАВЕДУЮЩЕЙ ==========
        child_age = self.child.get_age()
        age_category = 'nursery' if child_age < 3 else 'kindergarten'

        tariff = Tariff.objects.filter(
            age_category=age_category,
            year=year
        ).first()

        if tariff:
            content_monthly = tariff.content_amount
            food_monthly = tariff.food_amount
        else:
            # Если тариф не найден — пробуем любой тариф за этот год
            tariff = Tariff.objects.filter(year=year).first()
            if tariff:
                content_monthly = tariff.content_amount
                food_monthly = tariff.food_amount
            else:
                content_monthly = Decimal('1684.00')
                food_monthly = Decimal('2503.00')

        # ========== 4. ДНЕВНЫЕ СТАВКИ ==========
        if total_working_days > 0:
            content_daily_rate = content_monthly / total_working_days
            food_daily_rate = food_monthly / total_working_days
        else:
            content_daily_rate = Decimal('0')
            food_daily_rate = Decimal('0')

        self.daily_rate = content_daily_rate
        self.food_daily_rate = food_daily_rate

        # ========== 5. СУММА ЗА САД ==========
        content_amount = content_daily_rate * present_days
        food_amount = food_daily_rate * self.food_days
        kindergarten_amount = content_amount + food_amount
        self.base_amount = kindergarten_amount

        # ========== 6. КРУЖКИ ==========
        total_circles_amount = Decimal('0')
        circles_details = {}

        active_enrollments = ServiceEnrollment.objects.filter(
            child=self.child, status='approved'
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=date(year, month, 1))
        )

        for enrollment in active_enrollments:
            attended_lessons = ServiceAttendance.objects.filter(
                enrollment=enrollment,
                date__month=month,
                date__year=year,
                status='present'
            ).count()
            if attended_lessons > 0:
                circle_amount = enrollment.service.price_per_lesson * attended_lessons
                total_circles_amount += circle_amount
                circles_details[enrollment.service.name] = {
                    'price_per_lesson': float(enrollment.service.price_per_lesson),
                    'attended_lessons': attended_lessons,
                    'total': float(circle_amount)
                }

        self.additional_services_amount = total_circles_amount
        self.additional_services_details = circles_details

        # ========== 7. КОМПЕНСАЦИЯ ==========
        compensation_rate = self._calculate_compensation_rate()
        self.discount_rate = compensation_rate
        self.discount_amount = kindergarten_amount * compensation_rate

        # ========== 8. ИТОГ ==========
        self.amount = kindergarten_amount + total_circles_amount

        return self.amount
    
    
    def _calculate_compensation_rate(self):
        """
        Расчет федеральной компенсации:
        - На первого ребенка: 20%
        - На второго ребенка: 50%
        - На третьего и последующих: 70%
        """
        from accounts.models import ParentProfile
        
        parents = self.child.parent_relations.all()
        if not parents.exists():
            return Decimal('0.2')
        
        parent = parents.first().parent
        children_count = Child.objects.filter(
            parent_relations__parent=parent,
            is_active=True
        ).count()
        
        if children_count == 1:
            return Decimal('0.2')
        elif children_count == 2:
            return Decimal('0.5')
        else:
            return Decimal('0.7')
    
    def get_month_name(self):
        month_names = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]
        return month_names[self.month - 1] if 1 <= self.month <= 12 else ''
    
    @property
    def is_overdue(self):
        """Проверка просрочки платежа (после 15 числа месяца)"""
        if self.status == 'completed':
            return False
        today = date.today()
        if today.year == self.year and today.month == self.month:
            return today.day > 15
        return today > date(self.year, self.month, 15)

  
class BankCard(models.Model):
    CARD_TYPES = [
        ('visa', 'Visa'),
        ('mastercard', 'MasterCard'),
        ('mir', 'МИР'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bank_cards')
    card_type = models.CharField(max_length=20, choices=CARD_TYPES, default='visa')
    card_number = models.CharField(max_length=16)
    card_number_masked = models.CharField(max_length=25)
    card_holder = models.CharField(max_length=100)
    expiry_month = models.IntegerField()
    expiry_year = models.IntegerField()
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Банковская карта'
        verbose_name_plural = 'Банковские карты'
    
    def __str__(self):
        return f"{self.get_card_type_display()} •••• {self.card_number[-4:]}"


class PaymentCalculation(models.Model):
    """История расчетов платежей"""
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, verbose_name='Платеж')
    calculation_date = models.DateTimeField(auto_now_add=True, verbose_name='Дата расчета')
    details = models.JSONField(verbose_name='Детали расчета')
    
    class Meta:
        verbose_name = 'Расчет платежа'
        verbose_name_plural = 'Расчеты платежей'
        ordering = ['-calculation_date']
    
    def __str__(self):
        return f"Расчет для {self.payment}"