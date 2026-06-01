# attendance/models.py
from django.db import models
from django.contrib.auth import get_user_model
from children.models import Child, Group
from calendar import monthrange, weekday
from datetime import date
import re

User = get_user_model()


class ProductionCalendar(models.Model):
    """Производственный календарь - выходные и праздничные дни"""
    year = models.IntegerField(verbose_name='Год')
    date = models.DateField(verbose_name='Дата')
    is_holiday = models.BooleanField(default=False, verbose_name='Выходной/Праздник')
    holiday_name = models.CharField(max_length=100, blank=True, verbose_name='Название праздника')
    is_working_saturday = models.BooleanField(default=False, verbose_name='Рабочая суббота')
    
    class Meta:
        unique_together = ['year', 'date']
        verbose_name = 'Производственный календарь'
        verbose_name_plural = 'Производственный календарь'
        ordering = ['date']
    
    def __str__(self):
        return f"{self.date} - {'Выходной' if self.is_holiday else 'Рабочий'}"


class AttendanceSheet(models.Model):
    """Табель посещаемости детей (ф. 0504608) - ежемесячный документ"""
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')
    month = models.IntegerField(verbose_name='Месяц')
    year = models.IntegerField(verbose_name='Год')
    
    is_approved = models.BooleanField(default=False, verbose_name='Утвержден')
    is_draft = models.BooleanField(default=True, verbose_name='Черновик')
    
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_sheets',
        verbose_name='Создал (воспитатель)'
    )
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_sheets',
        verbose_name='Утвердил (заведующая)'
    )
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата утверждения')
    
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    production_calendar = models.ForeignKey(
        ProductionCalendar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Производственный календарь'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['group', 'month', 'year']
        verbose_name = 'Табель посещаемости'
        verbose_name_plural = 'Табели посещаемости'
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"Табель {self.group.name} - {self.month}.{self.year}"
    
    def get_month_name(self):
        month_names = [
            'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
            'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
        ]
        return month_names[self.month - 1]
    
    def get_total_days(self):
        return monthrange(self.year, self.month)[1]
    
    def get_working_days(self):
        """Количество рабочих дней в месяце (без выходных)"""
        working_days = 0
        for day in range(1, self.get_total_days() + 1):
            current_date = date(self.year, self.month, day)
            if not self.is_holiday_date(current_date):
                working_days += 1
        return working_days
    
    def is_holiday_date(self, date_obj):
        """Проверка, является ли дата выходным/праздничным днем"""
        try:
            entry = ProductionCalendar.objects.get(date=date_obj)
            return entry.is_holiday
        except ProductionCalendar.DoesNotExist:
            return date_obj.weekday() >= 5


class AbsenceDocument(models.Model):
    """Документ, подтверждающий уважительную причину отсутствия"""
    
    DOCUMENT_TYPES = [
        ('sick_leave', 'Больничный лист'),
        ('medical_certificate', 'Медицинская справка'),
        ('parent_statement', 'Заявление родителя'),
        ('sanatorium_voucher', 'Путевка в санаторий'),
        ('other', 'Другое'),
    ]
    
    record = models.ForeignKey('AttendanceRecord', on_delete=models.CASCADE, related_name='documents', verbose_name='Запись посещаемости')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, verbose_name='Тип документа')
    document_file = models.FileField(upload_to='absence_documents/%Y/%m/', verbose_name='Файл документа')
    document_number = models.CharField(max_length=100, blank=True, verbose_name='Номер документа')
    issue_date = models.DateField(null=True, blank=True, verbose_name='Дата выдачи')
    start_date = models.DateField(verbose_name='Дата начала')
    end_date = models.DateField(verbose_name='Дата окончания')
    description = models.TextField(blank=True, verbose_name='Описание')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Загрузил')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Документ отсутствия'
        verbose_name_plural = 'Документы отсутствия'
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.record.child.full_name} ({self.start_date} - {self.end_date})"


class AttendanceRecord(models.Model):
    """Запись посещаемости для конкретного ребенка в табеле"""
    
    STATUS_CHOICES = [
        ('', '-'),                          # Не заполнено
        ('present', 'Я'),                   # Присутствовал (оплачивается)
        ('absent_unexcused', 'НЯ'),         # Неявка без уважительной причины (оплачивается)
        ('absent_sick', 'НБ'),              # Неявка по болезни (не оплачивается)
        ('absent_vacation', 'НУ'),          # Неявка по уважительной причине (не оплачивается)
        ('weekend', 'В'),                   # Выходной (не оплачивается)
    ]
    
    # Словарь для автоматического заполнения примечаний
    STATUS_NOTES_MAP = {
        'absent_sick': 'НБ — неявка по болезни',
        'absent_vacation': 'НУ — неявка по уважительной причине',
        'absent_unexcused': 'НЯ — неявка без уважительной причины',
    }
    
    sheet = models.ForeignKey(AttendanceSheet, on_delete=models.CASCADE, related_name='records', verbose_name='Табель')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, verbose_name='Ребенок')
    
    start_date = models.DateField(null=True, blank=True, verbose_name='Дата начала посещения')
    end_date = models.DateField(null=True, blank=True, verbose_name='Дата окончания посещения')
    
    # Отметки по дням месяца
    day_1 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_2 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_3 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_4 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_5 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_6 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_7 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_8 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_9 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_10 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_11 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_12 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_13 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_14 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_15 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_16 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_17 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_18 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_19 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_20 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_21 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_22 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_23 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_24 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_25 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_26 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_27 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_28 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_29 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_30 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    day_31 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='', blank=True)
    
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    class Meta:
        unique_together = ['sheet', 'child']
        verbose_name = 'Запись посещаемости'
        verbose_name_plural = 'Записи посещаемости'
    
    def __str__(self):
        return f"{self.child.full_name} - {self.sheet}"
    
    
    def get_day_status(self, day):
        """Получить статус для конкретного дня"""
        if day < 1 or day > 31:
            return ''
        status = getattr(self, f'day_{day}', '')
        return status if status else ''
    
    def set_day_status(self, day, status):
        """Установить статус для конкретного дня и автоматически добавить/обновить примечание"""
        if 1 <= day <= 31:
            # Сохраняем старый статус
            old_status = getattr(self, f'day_{day}', '')
            
            # Устанавливаем новый статус
            setattr(self, f'day_{day}', status)
            
            # Обновляем примечания для этого дня
            self._update_notes_for_day(day, old_status, status)
    
    def _update_notes_for_day(self, day, old_status, new_status):
        """Обновить примечания для конкретного дня"""
        # Получаем текущие примечания
        current_notes = self.notes or ""
        notes_lines = [line.strip() for line in current_notes.split('\n') if line.strip()]
        
        # Ключ для поиска примечания этого дня
        day_key = f"(день {day})"
        
        # Удаляем старое примечание для этого дня
        new_notes_lines = []
        for line in notes_lines:
            if day_key not in line:
                new_notes_lines.append(line)
        
        # Добавляем новое примечание (если нужно)
        if new_status in self.STATUS_NOTES_MAP:
            note = f"{self.STATUS_NOTES_MAP[new_status]} (день {day})"
            new_notes_lines.append(note)
        
        # Сортируем примечания по дням
        def get_day_from_note(note):
            match = re.search(r'\(день (\d+)\)', note)
            return int(match.group(1)) if match else 999
        
        new_notes_lines.sort(key=get_day_from_note)
        
        # Сохраняем
        self.notes = '\n'.join(new_notes_lines)
    
    def clear_notes_for_day(self, day):
        """Очистить примечания для конкретного дня"""
        if not self.notes:
            return
        
        notes_lines = self.notes.split('\n')
        day_key = f"(день {day})"
        
        new_notes_lines = [line for line in notes_lines if day_key not in line]
        self.notes = '\n'.join(new_notes_lines)
    
    def get_note_for_day(self, day):
        """Получить примечание для конкретного дня"""
        if not self.notes:
            return None
        day_key = f"(день {day})"
        for line in self.notes.split('\n'):
            if day_key in line:
                return line
        return None
    
    def get_present_days(self):
        """Количество дней присутствия (Я)"""
        count = 0
        for day in range(1, self.sheet.get_total_days() + 1):
            current_date = date(self.sheet.year, self.sheet.month, day)
            if self.sheet.is_holiday_date(current_date):
                continue
            status = getattr(self, f'day_{day}', '')
            if status == 'present':
                count += 1
        return count
    
    def get_unexcused_absent_days(self):
        """Количество дней неявки без уважительной причины (НЯ) - ОПЛАЧИВАЕТСЯ"""
        count = 0
        for day in range(1, self.sheet.get_total_days() + 1):
            current_date = date(self.sheet.year, self.sheet.month, day)
            if self.sheet.is_holiday_date(current_date):
                continue
            status = getattr(self, f'day_{day}', '')
            if status == 'absent_unexcused':
                count += 1
        return count
    
    def get_sick_days(self):
        """Количество дней болезни (НБ) - НЕ ОПЛАЧИВАЕТСЯ (перерасчет)"""
        count = 0
        for day in range(1, self.sheet.get_total_days() + 1):
            current_date = date(self.sheet.year, self.sheet.month, day)
            if self.sheet.is_holiday_date(current_date):
                continue
            status = getattr(self, f'day_{day}', '')
            if status == 'absent_sick':
                count += 1
        return count
    
    def get_vacation_days(self):
        """Количество дней отпуска/уважительной причины (НУ) - НЕ ОПЛАЧИВАЕТСЯ (перерасчет)"""
        count = 0
        for day in range(1, self.sheet.get_total_days() + 1):
            current_date = date(self.sheet.year, self.sheet.month, day)
            if self.sheet.is_holiday_date(current_date):
                continue
            status = getattr(self, f'day_{day}', '')
            if status == 'absent_vacation':
                count += 1
        return count
    
    def get_total_working_days(self):
        """Общее количество рабочих дней в месяце"""
        working_days = 0
        for day in range(1, self.sheet.get_total_days() + 1):
            current_date = date(self.sheet.year, self.sheet.month, day)
            if not self.sheet.is_holiday_date(current_date):
                working_days += 1
        return working_days
    
    def get_paid_days(self):
        """
        Расчет дней, подлежащих оплате.
        Формула: Рабочие дни - Пропуски по уважительной причине (НБ + НУ)
        """
        working_days = self.get_total_working_days()
        valid_absent_days = self.get_sick_days() + self.get_vacation_days()
        return working_days - valid_absent_days
    
    def get_total_absent_days(self):
        """Общее количество пропущенных дней (все виды отсутствий)"""
        return (self.get_unexcused_absent_days() + 
                self.get_sick_days() + 
                self.get_vacation_days())
    
    def get_valid_absent_days(self):
        """Уважительные причины отсутствия (НБ, НУ) - вычитаются из оплаты"""
        return self.get_sick_days() + self.get_vacation_days()
    
    def get_invalid_absent_days(self):
        """Неуважительные причины отсутствия (НЯ) - оплачиваются"""
        return self.get_unexcused_absent_days()
    
    def get_absence_reason_text(self):
        """Получить текстовое описание причин отсутствия"""
        reasons = []
        sick_days = self.get_sick_days()
        vacation_days = self.get_vacation_days()
        unexcused_days = self.get_unexcused_absent_days()
        
        if sick_days > 0:
            reasons.append(f"Болезнь: {sick_days} дн.")
        if vacation_days > 0:
            reasons.append(f"Уважительная причина: {vacation_days} дн.")
        if unexcused_days > 0:
            reasons.append(f"Без уважительной причины: {unexcused_days} дн.")
        
        return ', '.join(reasons) if reasons else ''
    
    def has_absence_documents(self):
        """Проверка наличия документов, подтверждающих отсутствие"""
        return self.documents.exists()


class Meal(models.Model):
    """Питание ребенка"""
    MEAL_TYPES = [
        ('breakfast', 'Завтрак'),
        ('lunch', 'Обед'),
        ('snack', 'Полдник'),
        ('dinner', 'Ужин'),
    ]
    
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='meals')
    date = models.DateField()
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES)
    eaten = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['child', 'date', 'meal_type']
        db_table = 'attendance_meal'
        verbose_name = 'Питание'
        verbose_name_plural = 'Питание'
    
    def __str__(self):
        return f"{self.child} - {self.date} - {self.get_meal_type_display()}"
