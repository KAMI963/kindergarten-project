from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notifications_list, name='list'),
    path('api/list/', views.notifications_api, name='api_list'),
    path('api/mark-read/', views.mark_notification_read, name='mark_read'),
    path('api/mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('api/unread-count/', views.unread_count_api, name='unread_count'),
]