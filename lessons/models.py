# lessons/models.py
from django.db import models
from django.contrib.auth import get_user_model
from children.models import Group
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

class LessonPlan(models.Model):
    LESSON_TYPE_CHOICES = [
        ('cognitive', 'Познавательное'),
        ('creative', 'Творческое'),
        ('physical', 'Физкультурное'),
        ('music', 'Музыкальное'),
        ('language', 'Речевое развитие'),
        ('math', 'Математическое'),
        ('environment', 'Окружающий мир'),
        ('safety', 'Безопасность'),
        ('social', 'Социально-коммуникативное'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Легкое'),
        ('medium', 'Среднее'),
        ('hard', 'Сложное'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='Название занятия')
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPE_CHOICES, verbose_name='Тип занятия')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Воспитатель')
    description = models.TextField(verbose_name='Описание занятия')
    objectives = models.TextField(verbose_name='Цели и задачи')
    materials = models.TextField(verbose_name='Необходимые материалы', blank=True)
    duration = models.PositiveIntegerField(
        verbose_name='Продолжительность (мин)',
        validators=[MinValueValidator(5), MaxValueValidator(120)]
    )
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, verbose_name='Сложность')
    age_appropriate = models.BooleanField(default=True, verbose_name='Соответствует возрасту')
    
    # Планирование
    planned_date = models.DateField(verbose_name='Планируемая дата')
    planned_time = models.TimeField(verbose_name='Планируемое время')
    
    # Фактическое проведение
    actual_date = models.DateField(null=True, blank=True, verbose_name='Фактическая дата')
    actual_time = models.TimeField(null=True, blank=True, verbose_name='Фактическое время')
    completed = models.BooleanField(default=False, verbose_name='Проведено')
    
    # Результаты
    notes = models.TextField(blank=True, verbose_name='Заметки о проведении')
    success_rate = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Оценка успешности (1-5)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'План занятия'
        verbose_name_plural = 'Планы занятий'
        ordering = ['-planned_date', 'planned_time']
    
    def __str__(self):
        return f"{self.title} - {self.group.name} - {self.planned_date}"

class LessonSchedule(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Понедельник'),
        (1, 'Вторник'),
        (2, 'Среда'),
        (3, 'Четверг'),
        (4, 'Пятница'),
        (5, 'Суббота'),
        (6, 'Воскресенье'),
    ]
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK, verbose_name='День недели')
    start_time = models.TimeField(verbose_name='Время начала')
    end_time = models.TimeField(verbose_name='Время окончания')
    activity_type = models.CharField(max_length=50, verbose_name='Вид деятельности')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_regular = models.BooleanField(default=True, verbose_name='Регулярное занятие')
    
    class Meta:
        verbose_name = 'Расписание'
        verbose_name_plural = 'Расписания'
        ordering = ['day_of_week', 'start_time']
        unique_together = ['group', 'day_of_week', 'start_time']
    
    def __str__(self):
        return f"{self.group.name} - {self.get_day_of_week_display()} - {self.start_time}"

class LessonReminder(models.Model):
    REMINDER_TYPE_CHOICES = [
        ('preparation', 'Подготовка к занятию'),
        ('materials', 'Подготовка материалов'),
        ('parent_meeting', 'Родительское собрание'),
        ('event', 'Мероприятие'),
        ('other', 'Другое'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='Заголовок напоминания')
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE_CHOICES, verbose_name='Тип напоминания')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Воспитатель')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')
    description = models.TextField(verbose_name='Описание')
    due_date = models.DateField(verbose_name='Срок выполнения')
    due_time = models.TimeField(verbose_name='Время', null=True, blank=True)
    completed = models.BooleanField(default=False, verbose_name='Выполнено')
    priority = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        verbose_name='Приоритет (1-высокий, 3-низкий)'
    )
    
    # Связь с занятием (опционально)
    lesson_plan = models.ForeignKey(
        LessonPlan, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Связанное занятие'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Напоминание'
        verbose_name_plural = 'Напоминания'
        ordering = ['due_date', 'due_time', 'priority']
    
    def __str__(self):
        return f"{self.title} - {self.due_date}"

class ActivityTemplate(models.Model):
    AGE_GROUP_CHOICES = [
        ('nursery', 'Ясельная (1.5-3 года)'),
        ('junior', 'Младшая (3-4 года)'),
        ('middle', 'Средняя (4-5 лет)'),
        ('senior', 'Старшая (5-6 лет)'),
        ('preparatory', 'Подготовительная (6-7 лет)'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='Название шаблона')
    description = models.TextField(verbose_name='Описание')
    age_group = models.CharField(max_length=15, choices=AGE_GROUP_CHOICES, verbose_name='Возрастная группа')
    lesson_type = models.CharField(max_length=20, choices=LessonPlan.LESSON_TYPE_CHOICES, verbose_name='Тип занятия')
    objectives = models.TextField(verbose_name='Цели и задачи')
    materials = models.TextField(verbose_name='Материалы')
    duration = models.PositiveIntegerField(verbose_name='Продолжительность (мин)')
    steps = models.TextField(verbose_name='Этапы проведения')
    variations = models.TextField(blank=True, verbose_name='Вариации и дополнения')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Создатель')
    is_public = models.BooleanField(default=False, verbose_name='Общедоступный шаблон')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Шаблон занятия'
        verbose_name_plural = 'Шаблоны занятий'
    
    def __str__(self):
        return f"{self.title} - {self.age_group}"
