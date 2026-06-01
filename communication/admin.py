from django.contrib import admin
from .models import Conversation, Message

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['conversation_type', 'teacher', 'parent', 'director', 'child', 'created_at']
    list_filter = ['conversation_type', 'created_at']
    search_fields = ['teacher__username', 'parent__user__username', 'director__username']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'sender', 'timestamp', 'is_read']
    list_filter = ['timestamp', 'is_read']
    search_fields = ['content', 'sender__username']
