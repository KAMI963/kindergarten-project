# applications/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import (
    auto_reassign_age_categories, 
    process_expired_invitations, 
    QueueSettings,
    AgeCategory,
    ChildApplication,
    ApplicationStatus
)


@shared_task
def daily_queue_maintenance():
    """Ежедневное обслуживание очереди"""
    # Обновление возрастных категорий
    auto_reassign_age_categories()
    
    # Обработка просроченных приглашений
    process_expired_invitations()
    
    # Проверка свободных мест и приглашение следующих
    for age_cat in AgeCategory.choices:
        age_cat_code = age_cat[0]
        settings, _ = QueueSettings.objects.get_or_create(age_category=age_cat_code)
        free_places = settings.get_free_places()
        
        if free_places > 0:
            next_apps = ChildApplication.objects.filter(
                status=ApplicationStatus.QUEUE,
                age_category=age_cat_code
            ).order_by('-queue_priority', 'created_at')[:free_places]
            
            for app in next_apps:
                app.invite_to_enrollment()


@shared_task
def check_free_places():
    """Проверка свободных мест и приглашение кандидатов"""
    for age_cat in AgeCategory.choices:
        age_cat_code = age_cat[0]
        settings, _ = QueueSettings.objects.get_or_create(age_category=age_cat_code)
        
        # Обновляем статистику
        settings.waiting_list = ChildApplication.objects.filter(
            status=ApplicationStatus.QUEUE,
            age_category=age_cat_code
        ).count()
        settings.save()
        
        free_places = settings.get_free_places()
        
        if free_places > 0:
            next_apps = ChildApplication.objects.filter(
                status=ApplicationStatus.QUEUE,
                age_category=age_cat_code
            ).order_by('-queue_priority', 'created_at')[:free_places]
            
            for app in next_apps:
                app.invite_to_enrollment()