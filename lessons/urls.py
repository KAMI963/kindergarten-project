# lessons/urls.py
from django.urls import path
from . import views

app_name = 'lessons'

urlpatterns = [
    # Главная страница
    path('', views.lessons_dashboard, name='lessons_dashboard'),
    
    # Планы занятий
    path('plans/', views.lesson_plan_list, name='lesson_plan_list'),
    path('plans/create/', views.lesson_plan_create, name='lesson_plan_create'),
    path('plans/<int:plan_id>/', views.lesson_plan_detail, name='lesson_plan_detail'),
    path('plans/<int:plan_id>/edit/', views.lesson_plan_edit, name='lesson_plan_edit'),
    path('plans/<int:plan_id>/complete/', views.lesson_plan_complete, name='lesson_plan_complete'),
    path('plans/<int:plan_id>/delete/', views.lesson_plan_delete, name='lesson_plan_delete'),
    
    # Расписание
    path('schedule/', views.schedule_view, name='schedule_view'),
    path('schedule/edit/', views.schedule_edit, name='schedule_edit'),
    path('schedule/<int:schedule_id>/delete/', views.schedule_delete, name='schedule_delete'),
    
    # Напоминания
    path('reminders/', views.reminders_list, name='reminders_list'),
    path('reminders/create/', views.reminder_create, name='reminder_create'),
    path('reminders/<int:reminder_id>/toggle/', views.reminder_toggle, name='reminder_toggle'),
    path('reminders/<int:reminder_id>/delete/', views.reminder_delete, name='reminder_delete'),
    
    # Календарь
    path('calendar/', views.calendar_view, name='calendar_view'),
    path('api/calendar-events/', views.get_calendar_events, name='get_calendar_events'),
    
    # Шаблоны
    path('templates/', views.templates_list, name='templates_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:template_id>/use/', views.template_use, name='template_use'),
]
