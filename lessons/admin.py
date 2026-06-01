# lessons/admin.py
from django.contrib import admin
from .models import LessonPlan, LessonSchedule, LessonReminder, ActivityTemplate

@admin.register(LessonPlan)
class LessonPlanAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'group', 'lesson_type', 'planned_date', 'planned_time', 'completed', 'duration']
    list_filter = ['lesson_type', 'completed', 'difficulty', 'age_appropriate', 'planned_date']
    search_fields = ['title', 'description', 'teacher__username', 'group__name']
    date_hierarchy = 'planned_date'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'teacher', 'group', 'lesson_type', 'description')
        }),
        ('Планирование', {
            'fields': ('objectives', 'materials', 'duration', 'difficulty', 'age_appropriate')
        }),
        ('Даты и время', {
            'fields': ('planned_date', 'planned_time', 'actual_date', 'actual_time')
        }),
        ('Результаты', {
            'fields': ('completed', 'notes', 'success_rate')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LessonSchedule)
class LessonScheduleAdmin(admin.ModelAdmin):
    list_display = ['group', 'day_of_week', 'start_time', 'end_time', 'activity_type', 'is_regular']
    list_filter = ['day_of_week', 'is_regular', 'group']
    ordering = ['day_of_week', 'start_time']

@admin.register(LessonReminder)
class LessonReminderAdmin(admin.ModelAdmin):
    list_display = ['title', 'teacher', 'reminder_type', 'due_date', 'due_time', 'priority', 'completed']
    list_filter = ['reminder_type', 'completed', 'priority', 'due_date']
    search_fields = ['title', 'description', 'teacher__username']
    date_hierarchy = 'due_date'

@admin.register(ActivityTemplate)
class ActivityTemplateAdmin(admin.ModelAdmin):
    list_display = ['title', 'age_group', 'lesson_type', 'duration', 'created_by', 'is_public']
    list_filter = ['age_group', 'lesson_type', 'is_public']
    search_fields = ['title', 'description', 'objectives']
    readonly_fields = ['created_at', 'updated_at']
