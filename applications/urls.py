# applications/urls.py
from django.urls import path
from . import views

app_name = 'applications'

urlpatterns = [
    # Основные маршруты
    path('', views.applications_list, name='applications_list'),
    path('create/', views.application_create, name='application_create'),
    path('<int:application_id>/', views.application_detail, name='application_detail'),
    path('<int:application_id>/edit/', views.application_edit, name='application_edit'),
    path('<int:application_id>/generate-document/', views.generate_application_document, name='generate_application_document'),
    
    # Действия
    path('<int:application_id>/approve/', views.application_approve, name='application_approve'),
    path('<int:application_id>/reject/', views.application_reject, name='application_reject'),
    path('<int:application_id>/need-correction/', views.application_need_correction, name='application_need_correction'),
    path('<int:application_id>/return/', views.return_for_revision, name='return_revision'),
    path('<int:application_id>/invite/', views.invite_to_enrollment, name='invite_enrollment'),
    path('api/available-slots/<int:application_id>/', views.available_slots_api, name='available_slots_api'),
    path('api/book-appointment/', views.book_appointment_api, name='book_appointment_api'),
    
    # Генерация и скачивание
    path('<int:application_id>/download/', views.download_application, name='download_application'),
    path('sync-from-profile/', views.sync_from_profile, name='sync_from_profile'),
    
    # ==================== API ENDPOINTS ====================
    path('api/application/<int:application_id>/', views.application_api_detail, name='application_api_detail'),
    path('api/application/<int:application_id>/history/', views.application_history_api, name='application_history_api'),
    path('api/application/<int:application_id>/verify-form/', views.verify_form_api, name='verify_form_api'),
    path('api/application/<int:application_id>/verify/', views.verify_api, name='verify_api'),
    path('api/application/<int:application_id>/invite/', views.invite_api, name='invite_api'),
    path('api/application/<int:application_id>/position-form/', views.position_form_api, name='position_form_api'),
    path('api/application/<int:application_id>/position/', views.position_change_api, name='position_change_api'),
    path('api/application/<int:application_id>/order-form/', views.order_form_api, name='order_form_api'),
    path('api/application/<int:application_id>/order/', views.order_create_api, name='order_create_api'),
    path('api/queue-stats/', views.queue_statistics_api, name='queue_statistics_api'),
    
    # Очередь
    path('queue/recalculate/', views.recalculate_queue, name='recalculate_queue'),
    path('queue/parent/', views.parent_queue_status, name='parent_queue'),
    path('queue/director/', views.director_queue_admin, name='director_queue'),
    
    # Управление очередью
    path('<int:application_id>/change-position/', views.change_queue_position, name='change_position'),
    path('<int:application_id>/create-order/', views.create_enrollment_order, name='create_order'),
    path('<int:application_id>/withdraw/', views.application_withdraw, name='application_withdraw'),
    path('queue/calendar/', views.queue_calendar, name='queue_calendar'),
    path('<int:application_id>/book/', views.book_appointment, name='book_appointment'),
]