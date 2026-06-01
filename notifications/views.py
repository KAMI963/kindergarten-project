from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
import json
from .models import Notification


@login_required
def notifications_list(request):
    """Страница со всеми уведомлениями"""
    notifications = Notification.objects.filter(user=request.user)
    unread_count = notifications.filter(is_read=False).count()
    
    return render(request, 'notifications/list.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def notifications_api(request):
    """API для получения уведомлений"""
    notifications = Notification.objects.filter(user=request.user)[:20]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    
    data = {
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'is_read': n.is_read,
                'created_at': n.created_at.strftime('%d.%m.%Y %H:%M'),
                'link': n.link,
                'notification_type': n.notification_type,
            } for n in notifications
        ],
        'unread_count': unread_count
    }
    return JsonResponse(data)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def mark_notification_read(request):
    """Отметить уведомление как прочитанное"""
    try:
        data = json.loads(request.body)
        notification_id = data.get('notification_id')
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Уведомление не найдено'})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def mark_all_read(request):
    """Отметить все уведомления как прочитанные"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
def unread_count_api(request):
    """API для получения количества непрочитанных уведомлений"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})