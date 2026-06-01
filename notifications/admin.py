from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'user__username', 'user__email']
    readonly_fields = ['created_at']
    list_editable = ['is_read']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'title', 'message', 'notification_type')
        }),
        ('Статус и ссылки', {
            'fields': ('is_read', 'link', 'related_object_id', 'related_object_type')
        }),
        ('Даты', {
            'fields': ('created_at',)
        }),
    )