from django.contrib import admin
from .models import Menu, WeeklyMenuPlan, ChildMeal

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ['dish_name', 'group', 'day_of_week', 'meal_type', 'is_approved', 'weight', 'calories']
    list_filter = ['group', 'day_of_week', 'meal_type', 'is_approved']
    search_fields = ['dish_name', 'description']
    list_editable = ['is_approved']

@admin.register(WeeklyMenuPlan)
class WeeklyMenuPlanAdmin(admin.ModelAdmin):
    list_display = ['group', 'week_start_date', 'is_approved', 'approved_by', 'approved_date']
    list_filter = ['group', 'is_approved']
    search_fields = ['group__name']

@admin.register(ChildMeal)
class ChildMealAdmin(admin.ModelAdmin):
    list_display = ['child', 'menu', 'date', 'eaten']
    list_filter = ['date', 'eaten']
    search_fields = ['child__full_name', 'menu__dish_name']
