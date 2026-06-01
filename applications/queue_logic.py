# applications/queue_logic.py
from django.db.models import Q, F
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, timedelta
import logging

from .models import ChildApplication, ApplicationStatus, QueueSettings, AgeCategory
from children.models import Child

logger = logging.getLogger(__name__)

# Баллы за категории льгот
BENEFIT_POINTS = {
    'extraordinary': 1000,
    'priority': 500,
    'preferential': 250,
    'none': 0,
}

# Приоритеты для сортировки
PRIORITY_LEVELS = {
    'extraordinary': 1,
    'priority': 2,
    'preferential': 3,
    'none': 4,
}

SIBLING_BONUS = 100
DAYS_WAITING_POINTS = 1


def calculate_queue_points(application):
    """Рассчитывает баллы для заявления"""
    points = 0
    points += BENEFIT_POINTS.get(application.benefit_category, 0)
    
    if has_sibling_in_same_kindergarten(application):
        points += SIBLING_BONUS
    
    days_waiting = (date.today() - application.created_at.date()).days
    points += days_waiting * DAYS_WAITING_POINTS
    
    return points


def has_sibling_in_same_kindergarten(application):
    """Проверяет наличие брата/сестры в саду"""
    try:
        parent = application.parent
        siblings = Child.objects.filter(
            childparent__parent=parent,
            is_active=True
        ).exclude(full_name=application.child_full_name)
        
        for sibling in siblings:
            if sibling.group is not None:
                return True
        return False
    except:
        return False


def get_priority_level(benefit_category, has_sibling):
    """Определяет уровень приоритета"""
    if has_sibling:
        if benefit_category == 'extraordinary':
            return 0.5
        elif benefit_category == 'priority':
            return 1.5
        elif benefit_category == 'preferential':
            return 2.5
        else:
            return 3.5
    else:
        return PRIORITY_LEVELS.get(benefit_category, 4)


def update_all_queue_positions():
    """Обновляет позиции в очереди"""
    active_applications = ChildApplication.objects.filter(
        status__in=['pending', 'queue', 'returned']
    )
    
    for app in active_applications:
        app.queue_priority = calculate_queue_points(app)
        app.save()
    
    sorted_apps = active_applications.order_by('-queue_priority', 'created_at')
    
    for position, app in enumerate(sorted_apps, 1):
        app.queue_position = position
        app.save()
    
    return sorted_apps.count()


def auto_invite_from_queue(age_category=None):
    """
    АВТОМАТИЧЕСКОЕ ПРИГЛАШЕНИЕ - ОСНОВНАЯ ФУНКЦИЯ
    """
    print("=" * 60)
    print("🔔 АВТОМАТИЧЕСКОЕ ПРИГЛАШЕНИЕ ВЫЗВАНО")
    print(f"📅 Время: {timezone.now()}")
    print("=" * 60)
    
    invited_count = 0
    
    try:
        from notifications.models import Notification
        
        # Определяем категории для проверки
        if age_category:
            categories = [age_category]
        else:
            categories = [cat[0] for cat in AgeCategory.choices]
        
        print(f"📋 Категории для проверки: {categories}")
        
        for cat in categories:
            print(f"\n---🔍 Проверка категории: {cat} ---")
            
            # Получаем настройки очереди
            settings_queue = QueueSettings.objects.filter(age_category=cat).first()
            if not settings_queue:
                print(f"❌ Нет настроек для категории {cat}")
                continue
            
            free_places = settings_queue.get_free_places()
            print(f"📊 Статистика группы:")
            print(f"   - Вместимость: {settings_queue.capacity}")
            print(f"   - Зачислено: {settings_queue.current_enrolled}")
            print(f"   - Свободных мест: {free_places}")
            
            if free_places <= 0:
                print("⚠️ Нет свободных мест, пропускаем категорию")
                continue
            
            # Находим следующих в очереди
            next_apps = ChildApplication.objects.filter(
                status=ApplicationStatus.QUEUE,
                age_category=cat
            ).order_by('-queue_priority', 'created_at')[:free_places]
            
            print(f"📋 Найдено заявлений в очереди: {next_apps.count()}")
            
            for app in next_apps:
                print(f"\n👶 Приглашаем: {app.child_full_name} (ID: {app.id})")
                print(f"   - Родитель: {app.parent.user.get_full_name()}")
                print(f"   - Email: {app.parent.user.email}")
                print(f"   - Текущий статус: {app.status}")
                
                # Меняем статус
                app.status = ApplicationStatus.INVITED
                app.invitation_expires_at = timezone.now() + timedelta(days=14)
                app.save(update_fields=['status', 'invitation_expires_at'])
                invited_count += 1
                print(f"   ✅ Статус изменен на INVITED")
                print(f"   📅 Приглашение действует до: {app.invitation_expires_at.strftime('%d.%m.%Y')}")
                
                # СОЗДАЕМ УВЕДОМЛЕНИЕ
                try:
                    notification = Notification.objects.create(
                        user=app.parent.user,
                        title="🎉 Приглашение на оформление!",
                        message=f"Уважаемый(ая)! Ваш ребенок {app.child_full_name} приглашен для оформления в детский сад. Пожалуйста, запишитесь на прием в личном кабинете. Срок действия приглашения до {app.invitation_expires_at.strftime('%d.%m.%Y')}.",
                        notification_type='invite',
                        link=f"/applications/{app.id}/"
                    )
                    print(f"   ✅ Уведомление создано (ID: {notification.id})")
                except Exception as e:
                    print(f"   ❌ Ошибка создания уведомления: {e}")
                
                # ОТПРАВЛЯЕМ EMAIL
                try:
                    parent_email = app.parent.user.email
                    if parent_email:
                        subject = f'🎉 Приглашение на оформление в детский сад - {app.child_full_name}'
                        message = f"""
Здравствуйте, {app.parent.user.get_full_name() or app.parent.user.username}!

🎉 Ваш ребенок {app.child_full_name} приглашен для оформления в детский сад.

📅 Срок действия приглашения: до {app.invitation_expires_at.strftime('%d.%m.%Y')}

📝 Для подтверждения необходимо:
1. Войдите в личный кабинет
2. Выберите удобное время для визита
3. Приходите с оригиналами документов

🔗 Перейти к заявлению: http://127.0.0.1:8000/applications/{app.id}/

С уважением,
Администрация детского сада
"""
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [parent_email],
                            fail_silently=False
                        )
                        print(f"   ✅ Email отправлен на {parent_email}")
                    else:
                        print(f"   ⚠️ Email родителя не указан")
                except Exception as e:
                    print(f"   ❌ Ошибка отправки email: {e}")
        
        print(f"\n" + "=" * 60)
        print(f"📊 ИТОГО ПРИГЛАШЕНО: {invited_count} заявителей")
        print("=" * 60)
        return invited_count
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 0


def get_queue_position_for_parent(application):
    """Возвращает позицию в очереди для родителя"""
    if application.queue_position:
        total = ChildApplication.objects.filter(
            status__in=[
                ApplicationStatus.PENDING,
                ApplicationStatus.QUEUE,
                ApplicationStatus.RETURNED
            ]
        ).count()
        return {
            'position': application.queue_position,
            'total': total,
            'percentile': round((application.queue_position / total) * 100, 1) if total > 0 else 0
        }
    return None