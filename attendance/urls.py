# attendance/urls.py
from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # ==================== ОСНОВНЫЕ МАРШРУТЫ ====================
    path('', views.attendance_dashboard, name='attendance_dashboard'),
    path('dashboard/', views.attendance_dashboard, name='dashboard'),
    
    # ==================== AJAX ОБНОВЛЕНИЯ ====================
    path('api/update-attendance/', views.update_attendance_ajax, name='update_attendance_ajax'),
    path('api/update-meal/', views.update_meal_ajax, name='update_meal_ajax'),
    
    # ==================== ТАБЕЛИ ПОСЕЩАЕМОСТИ ====================
    path('sheets/', views.attendance_sheet_list, name='attendance_sheet_list'),
    path('sheets/create/', views.attendance_sheet_create, name='attendance_sheet_create'),
    path('sheets/<int:sheet_id>/', views.attendance_sheet_view, name='attendance_sheet_view'),
    path('sheets/<int:sheet_id>/edit/', views.attendance_sheet_edit, name='attendance_sheet_edit'),
    path('sheets/<int:sheet_id>/reset/', views.attendance_sheet_reset, name='attendance_sheet_reset'),
    path('sheets/<int:sheet_id>/restore/', views.restore_attendance_records, name='restore_attendance_records'),
    
    # ==================== МАССОВЫЕ ОТМЕТКИ ====================
    path('sheets/<int:sheet_id>/mark-all-present/', views.mark_all_present, name='mark_all_present'),
    path('sheets/<int:sheet_id>/mark-all-workdays-present/', views.mark_all_workdays_present, name='mark_all_workdays_present'),
    
    # ==================== УТВЕРЖДЕНИЕ ТАБЕЛЕЙ ====================
    path('sheets/<int:sheet_id>/approve/', views.attendance_sheet_approve, name='attendance_sheet_approve'),
    path('sheets/<int:sheet_id>/return/', views.attendance_sheet_return, name='attendance_sheet_return'),
    
    # ==================== ПЕЧАТЬ ТАБЕЛЕЙ ====================
    path('sheets/<int:sheet_id>/print/', views.attendance_sheet_print_word, name='attendance_sheet_print_word'),
    path('sheets/<int:sheet_id>/print-ajax/', views.attendance_sheet_print_ajax, name='attendance_sheet_print_ajax'),
    
    # ==================== ТЕСТОВЫЕ МАРШРУТЫ ====================
    path('sheets/<int:sheet_id>/test-save/', views.test_save_attendance, name='test_save_attendance'),
    
    # ==================== СТАТИСТИКА И АНАЛИТИКА ====================
    # ИСПРАВЛЕНО: используем правильные имена функций
    path('statistics/', views.attendance_statistics, name='statistics'),  # Эта функция должна существовать
    path('analytics/', views.attendance_analytics, name='analytics'),
    path('report/', views.generate_attendance_report, name='generate_attendance_report'),
    
    # ==================== ПРОИЗВОДСТВЕННЫЙ КАЛЕНДАРЬ ====================
    path('calendar/', views.production_calendar_list, name='production_calendar_list'),
    path('calendar/update/', views.production_calendar_update, name='production_calendar_update'),
    path('calendar/generate/', views.production_calendar_generate, name='production_calendar_generate'),
    path('api/calendar-data/', views.api_calendar_data, name='api_calendar_data'),
    path('api/generate-year/', views.api_generate_year, name='api_generate_year'),
    
    # ==================== РОДИТЕЛЬСКАЯ ПАНЕЛЬ ====================
    path('parent/', views.parent_attendance, name='parent_dashboard'),
    path('parent/child/<int:child_id>/', views.parent_attendance_detail, name='parent_detail'),
    
    # ==================== ДОКУМЕНТЫ ОТСУТСТВИЯ ====================
    path('document/add/<int:record_id>/', views.add_absence_document, name='add_absence_document'),
    path('document/delete/<int:doc_id>/', views.delete_absence_document, name='delete_absence_document'),
    path('document/download/<int:doc_id>/', views.download_absence_document, name='download_absence_document'),
    
    # ==================== ОТЛАДОЧНЫЕ МАРШРУТЫ ====================
    path('debug/template/', views.debug_template, name='debug_template'),
    path('api/get-child-status/', views.get_child_today_status, name='get_child_status'),
]