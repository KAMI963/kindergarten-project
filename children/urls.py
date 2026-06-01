# children/urls.py - ИСПРАВЛЕННАЯ ВЕРСИЯ (без дублирования)

from django.urls import path
from . import views
from . import group_views

app_name = 'children'

urlpatterns = [
    # === ОСНОВНЫЕ МАРШРУТЫ ДЛЯ ДЕТЕЙ ===
    path('', views.children_list, name='children_list'),
    path('create/', views.child_create, name='child_create'),
    path('<int:child_id>/', views.child_detail, name='child_detail'),
    path('<int:child_id>/edit/', views.child_edit, name='child_edit'),
    path('<int:child_id>/delete/', views.child_delete, name='child_delete'),
    path('<int:child_id>/add-parent/', views.add_parent, name='add_parent'),
    
    # === МАРШРУТЫ ДЛЯ ГРУПП ===
    path('groups/', group_views.group_list, name='group_list'),
    path('groups/create/', group_views.group_create, name='group_create'),
    path('groups/<int:group_id>/', group_views.group_detail, name='group_detail'),
    path('groups/<int:group_id>/edit/', group_views.group_edit, name='group_edit'),
    
    # === МАРШРУТЫ ДЛЯ ДЕТЕЙ В ГРУППЕ ===
    path('groups/<int:group_id>/children/', views.group_children, name='group_children'),
    path('groups/<int:group_id>/export/excel/', views.export_group_children_excel, name='export_group_excel'),
    path('groups/<int:group_id>/export/word/', views.export_group_children_word, name='export_group_word'),
    
    # === ЛИЧНЫЕ ДЕЛА ===
    path('personal-files/', views.personal_files_list, name='personal_files_list'),
    path('<int:child_id>/personal-file/', views.personal_file_detail, name='personal_file_detail'),
    path('<int:child_id>/personal-file/edit/', views.personal_file_edit, name='personal_file_edit'),
    
    # === ЛИЧНОЕ ДЕЛО ИЗ ЗАЯВЛЕНИЯ ===
    path('application/<int:application_id>/personal-file/', views.personal_file_from_application, name='personal_file_from_application'),
    
    # === API ДЛЯ СТАТИСТИКИ ===
    path('api/document-stats/', views.document_stats_api, name='document_stats_api'),
    
    # === РАБОТА С ФАЙЛАМИ (ПРОСМОТР) ===
    path('view-file/<path:file_path>/', views.view_file_modal, name='view_file_modal'),
    path('view-pdf/<path:file_path>/', views.view_pdf, name='view_pdf'),
    path('view-media/<path:file_path>/', views.view_media_file, name='view_media_file'),
    
    # === РАБОТА С ФОТО (ЗАГРУЗКА/УДАЛЕНИЕ) ===
    path('<int:child_id>/upload-photo/', views.upload_child_photo, name='upload_child_photo'),
    path('<int:child_id>/delete-photo/', views.delete_child_photo, name='delete_child_photo'),
    
    # === РАБОТА С ДОКУМЕНТАМИ (ЗАГРУЗКА/УДАЛЕНИЕ) ===
    path('<int:child_id>/upload-document/', views.upload_child_document, name='upload_child_document'),
    path('<int:child_id>/delete-document/', views.delete_child_document, name='delete_child_document'),
    
    # === РАБОТА С СОГЛАСИЯМИ ===
    path('<int:child_id>/update-consent/', views.update_consent, name='update_consent'),
]