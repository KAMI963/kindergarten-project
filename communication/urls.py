# communication/urls.py
from django.urls import path
from . import views

app_name = 'communication'

urlpatterns = [
    path('', views.communication_dashboard, name='dashboard'),
    path('start/', views.start_conversation, name='start_conversation'),
    path('<int:conversation_id>/send/', views.send_message, name='send_message'),
    path('<int:conversation_id>/messages/', views.get_messages, name='get_messages'),
    path('get-unread-count/', views.get_unread_count, name='get_unread_count'),
    path('download/<int:message_id>/', views.download_file, name='download_file'),
]