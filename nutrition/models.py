from django.db import models
from django.contrib.auth import get_user_model
from children.models import Child, Group
from datetime import date, timedelta

User = get_user_model()

class Menu(models.Model):
    MEAL_TYPES = [
        ('breakfast', 'Завтрак'),
        ('lunch', 'Обед'),
        ('snack', 'Полдник'),
        ('dinner', 'Ужин'),
    ]
    
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
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES, verbose_name='Тип питания')
    dish_name = models.CharField(max_length=200, verbose_name='Название блюда')
    description = models.TextField(blank=True, verbose_name='Описание')
    calories = models.IntegerField(verbose_name='Калории')
    proteins = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Белки (г)')
    fats = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Жиры (г)')
    carbohydrates = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Углеводы (г)')
    weight = models.IntegerField(verbose_name='Вес (г)')
    
    # Поля для утверждения
    is_approved = models.BooleanField(default=False, verbose_name='Утверждено')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   verbose_name='Утвердил(а)')
    approved_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата утверждения')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Меню'
        verbose_name_plural = 'Меню'
        unique_together = ['group', 'day_of_week', 'meal_type']
        ordering = ['group', 'day_of_week', 'meal_type']
    
    def __str__(self):
        return f"{self.group.name} - {self.get_day_of_week_display()} - {self.get_meal_type_display()}"

class WeeklyMenuPlan(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, verbose_name='Группа')
    week_start_date = models.DateField(verbose_name='Начало недели')
    is_approved = models.BooleanField(default=False, verbose_name='Утверждено')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='Утвердил(а)')
    approved_date = models.DateTimeField(null=True, blank=True, verbose_name='Дата утверждения')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'План меню на неделю'
        verbose_name_plural = 'Планы меню на неделю'
        unique_together = ['group', 'week_start_date']
    
    def __str__(self):
        return f"Меню {self.group.name} на неделю с {self.week_start_date}"

class ChildMeal(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, verbose_name='Ребенок')
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, verbose_name='Меню')
    date = models.DateField(verbose_name='Дата')
    eaten = models.BooleanField(default=False, verbose_name='Съедено')
    notes = models.TextField(blank=True, verbose_name='Примечания')
    
    class Meta:
        verbose_name = 'Питание ребенка'
        verbose_name_plural = 'Питание детей'
        unique_together = ['child', 'menu', 'date']
    
    def __str__(self):
        return f"{self.child.full_name} - {self.menu.dish_name} - {self.date}"
