# communication/views.py - ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ ВЕРСИЯ

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Max
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.utils import timezone
import os
import mimetypes
import json

from .models import Conversation, Message
from .forms import MessageForm, NewConversationForm
from children.models import Child
from accounts.models import ParentProfile

User = get_user_model()


# communication/views.py - в функции communication_dashboard

# communication/views.py - исправленная функция communication_dashboard

@login_required
def communication_dashboard(request):
    """Главная страница общения"""
    
    # Получаем все чаты пользователя
    if request.user.role == 'parent':
        # Для родителя - чаты с воспитателями его детей
        conversations = Conversation.objects.filter(
            parent__user=request.user
        ).distinct().annotate(
            last_message_time=Max('messages__timestamp')
        ).order_by('-last_message_time', '-updated_at')
    elif request.user.role == 'teacher':
        # Для воспитателя - чаты с родителями и заведующей
        conversations = Conversation.objects.filter(
            Q(teacher=request.user)
        ).distinct().annotate(
            last_message_time=Max('messages__timestamp')
        ).order_by('-last_message_time', '-updated_at')
    elif request.user.role == 'director':
        # Для заведующей - чаты с воспитателями и родителями
        conversations = Conversation.objects.filter(
            Q(director=request.user)
        ).distinct().annotate(
            last_message_time=Max('messages__timestamp')
        ).order_by('-last_message_time', '-updated_at')
    else:
        conversations = Conversation.objects.none()
    
    print(f"DEBUG: Found {conversations.count()} conversations for {request.user.role}")  # Отладка
    
    for conversation in conversations:
        conversation.last_message = conversation.messages.filter(is_deleted=False).last()
        conversation.unread_count = conversation.messages.filter(
            is_read=False, is_deleted=False
        ).exclude(sender=request.user).count()
        conversation.display_name = get_conversation_display_name(conversation, request.user)
        conversation.avatar_url = get_conversation_avatar(conversation, request.user)
    
    new_conversation_form = NewConversationForm(user=request.user)
    message_form = MessageForm()
    
    selected_conversation_id = request.GET.get('conversation')
    selected_conversation = None
    messages_list = []
    conversation_partner = None
    
    if selected_conversation_id:
        selected_conversation = get_object_or_404(Conversation, id=selected_conversation_id)
        
        if not has_access_to_conversation(request.user, selected_conversation):
            messages.error(request, 'У вас нет доступа к этому чату.')
            return redirect('communication:dashboard')
        
        selected_conversation.messages.filter(is_read=False, is_deleted=False).exclude(sender=request.user).update(is_read=True)
        messages_list = selected_conversation.messages.filter(is_deleted=False).order_by('timestamp')
        selected_conversation.display_name = get_conversation_display_name(selected_conversation, request.user)
        conversation_partner = get_conversation_partner(selected_conversation, request.user)
    
    context = {
        'conversations': conversations,
        'selected_conversation': selected_conversation,
        'messages': messages_list,
        'new_conversation_form': new_conversation_form,
        'message_form': message_form,
        'conversation_partner': conversation_partner,
    }
    
    return render(request, 'communication/dashboard.html', context)

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def send_message(request, conversation_id):
    """Отправка сообщения с файлом"""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    if not has_access_to_conversation(request.user, conversation):
        return JsonResponse({'success': False, 'error': 'Нет доступа'})
    
    content = request.POST.get('content', '').strip()
    file = request.FILES.get('file')
    
    print(f"DEBUG: send_message called - content: {content}, file: {file}")  # Отладка
    
    if not content and not file:
        return JsonResponse({'success': False, 'error': 'Сообщение не может быть пустым'})
    
    try:
        message = Message(
            conversation=conversation,
            sender=request.user,
            content=content or ''
        )
        
        if file:
            # Проверяем тип файла
            file_type = 'other'
            if file.content_type and file.content_type.startswith('image/'):
                file_type = 'image'
            elif file.content_type in ['application/pdf', 'application/msword', 
                                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                        'application/vnd.ms-excel',
                                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                file_type = 'document'
            
            message.file = file
            message.file_type = file_type
            message.file_name = file.name
            message.file_size = file.size
        
        message.save()
        conversation.save()
        
        # Обновляем время последнего сообщения
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'content': message.content,
                'has_file': bool(message.file),
                'file_url': message.file.url if message.file else None,
                'file_name': message.file_name,
                'file_type': message.file_type,
                'file_icon': message.get_file_icon(),
                'file_size_display': message.get_file_size_display(),
                'sender': message.sender.get_full_name(),
                'is_own': True,
                'timestamp': message.timestamp.strftime('%H:%M'),
                'full_timestamp': message.timestamp.strftime('%d.%m.%Y %H:%M'),
            }
        })
    except Exception as e:
        print(f"ERROR in send_message: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


# communication/views.py - полностью исправленная функция start_conversation

@login_required
def start_conversation(request):
    """Начало нового разговора"""
    if request.method == 'POST':
        form = NewConversationForm(request.POST, user=request.user)
        if form.is_valid():
            recipient_data = form.cleaned_data['recipient']
            parts = recipient_data.split('_')
            
            conversation = None
            
            try:
                # Для ЗАВЕДУЮЩЕЙ
                if request.user.role == 'director':
                    if recipient_data.startswith('teacher_'):
                        # Чат с воспитателем
                        teacher_id = parts[1]
                        teacher = get_object_or_404(User, id=teacher_id, role='teacher')
                        conversation, created = Conversation.objects.get_or_create(
                            conversation_type='teacher_director',
                            teacher=teacher,
                            director=request.user
                        )
                    
                    elif recipient_data.startswith('parent_'):
                        # Чат с родителем
                        parent_id = parts[1]
                        parent = get_object_or_404(ParentProfile, id=parent_id)
                        conversation, created = Conversation.objects.get_or_create(
                            conversation_type='director_parent',
                            director=request.user,
                            parent=parent
                        )
                
                # Для ВОСПИТАТЕЛЯ
                elif request.user.role == 'teacher':
                    if recipient_data.startswith('parent_') and len(parts) == 3:
                        parent_id, child_id = parts[1], parts[2]
                        parent = get_object_or_404(ParentProfile, id=parent_id)
                        child = get_object_or_404(Child, id=child_id)
                        
                        if child.group.teacher != request.user:
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({'success': False, 'error': 'Нет доступа к ребенку'})
                            messages.error(request, 'У вас нет доступа к этому ребенку.')
                            return redirect('communication:dashboard')
                        
                        conversation, created = Conversation.objects.get_or_create(
                            conversation_type='teacher_parent',
                            teacher=request.user,
                            parent=parent,
                            child=child
                        )
                    
                    elif recipient_data.startswith('director_'):
                        director_id = parts[1]
                        director = get_object_or_404(User, id=director_id, role='director')
                        conversation, created = Conversation.objects.get_or_create(
                            conversation_type='teacher_director',
                            teacher=request.user,
                            director=director
                        )
                
                # Для РОДИТЕЛЯ
                elif request.user.role == 'parent':
                    if recipient_data.startswith('teacher_') and len(parts) == 3:
                        teacher_id, child_id = parts[1], parts[2]
                        teacher = get_object_or_404(User, id=teacher_id, role='teacher')
                        child = get_object_or_404(Child, id=child_id)
                        
                        # Проверяем, что ребенок принадлежит родителю
                        if not child.parent_relations.filter(parent__user=request.user).exists():
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({'success': False, 'error': 'Нет доступа к ребенку'})
                            messages.error(request, 'У вас нет доступа к этому ребенку.')
                            return redirect('communication:dashboard')
                        
                        conversation, created = Conversation.objects.get_or_create(
                            conversation_type='teacher_parent',
                            teacher=teacher,
                            parent=request.user.parentprofile,
                            child=child
                        )
                    
                    elif recipient_data.startswith('director_'):
                        director_id = parts[1]
                        director = get_object_or_404(User, id=director_id, role='director')
                        conversation, created = Conversation.objects.get_or_create(
                            conversation_type='director_parent',
                            director=director,
                            parent=request.user.parentprofile
                        )
                
                if conversation:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True, 
                            'conversation_id': conversation.id,
                            'redirect_url': f'/communication/?conversation={conversation.id}'
                        })
                    return redirect(f'/communication/?conversation={conversation.id}')
                else:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': 'Не удалось создать чат'})
                    messages.error(request, 'Не удалось создать чат.')
            
            except Exception as e:
                print(f"ERROR creating conversation: {e}")
                import traceback
                traceback.print_exc()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)})
                messages.error(request, f'Ошибка при создании чата: {str(e)}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Форма не валидна'})
    
    return redirect('communication:dashboard')

@login_required
def get_messages(request, conversation_id):
    """Получение сообщений чата (AJAX)"""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    if not has_access_to_conversation(request.user, conversation):
        return JsonResponse({'success': False, 'error': 'Нет доступа'})
    
    conversation.messages.filter(is_read=False, is_deleted=False).exclude(sender=request.user).update(is_read=True)
    
    messages_list = conversation.messages.filter(is_deleted=False).order_by('timestamp')
    messages_data = []
    
    for msg in messages_list:
        messages_data.append({
            'id': msg.id,
            'content': msg.content,
            'has_file': bool(msg.file),
            'file_url': msg.file.url if msg.file else None,
            'file_name': msg.file_name,
            'file_type': msg.file_type,
            'file_icon': msg.get_file_icon(),
            'file_size_display': msg.get_file_size_display(),
            'sender': msg.sender.get_full_name(),
            'is_own': msg.sender == request.user,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'full_timestamp': msg.timestamp.strftime('%d.%m.%Y %H:%M'),
        })
    
    return JsonResponse({
        'success': True,
        'messages': messages_data,
    })


@login_required
def download_file(request, message_id):
    """Скачивание файла из сообщения"""
    message = get_object_or_404(Message, id=message_id)
    
    if not has_access_to_conversation(request.user, message.conversation):
        return HttpResponse('Нет доступа', status=403)
    
    if not message.file:
        return HttpResponse('Файл не найден', status=404)
    
    file_path = message.file.path
    file_name = message.file_name or os.path.basename(file_path)
    
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response


@login_required
def get_unread_count(request):
    """Возвращает количество непрочитанных сообщений"""
    conversations = Conversation.objects.filter(
        Q(teacher=request.user) | 
        Q(parent__user=request.user) | 
        Q(director=request.user)
    ).distinct()
    
    total_unread = 0
    for conversation in conversations:
        total_unread += conversation.messages.filter(
            is_read=False, is_deleted=False
        ).exclude(sender=request.user).count()
    
    return JsonResponse({'count': total_unread})


def update_unread_count(conversation, exclude_user):
    """Обновляет счетчик непрочитанных для получателя"""
    # Здесь можно добавить логику для real-time уведомлений
    pass


def has_access_to_conversation(user, conversation):
    """Проверка доступа пользователя к чату"""
    if user.role == 'teacher':
        return conversation.teacher == user
    elif user.role == 'parent':
        return conversation.parent and conversation.parent.user == user
    elif user.role == 'director':
        return conversation.director == user
    return False


def get_conversation_display_name(conversation, current_user):
    """Получить отображаемое имя для чата"""
    if current_user.role == 'teacher':
        if conversation.parent:
            if conversation.child:
                return f"{conversation.parent.user.get_full_name()} ({conversation.child.full_name})"
            return conversation.parent.user.get_full_name()
        elif conversation.director:
            return f"{conversation.director.get_full_name()}"
    
    elif current_user.role == 'parent':
        if conversation.teacher:
            if conversation.child:
                return f"{conversation.teacher.get_full_name()}"
            return conversation.teacher.get_full_name()
        elif conversation.director:
            return f"{conversation.director.get_full_name()}"
    
    elif current_user.role == 'director':
        if conversation.teacher:
            return f"{conversation.teacher.get_full_name()} (Воспитатель)"
        elif conversation.parent:
            if conversation.child:
                return f"{conversation.parent.user.get_full_name()} ({conversation.child.full_name})"
            return conversation.parent.user.get_full_name()
    
    return "Чат"


# communication/views.py - исправленная функция

def get_conversation_partner(conversation, current_user):
    """Получить данные собеседника для отображения в шапке чата"""
    partner = None
    role = ''
    
    if current_user.role == 'teacher':
        if conversation.parent:
            partner = conversation.parent.user
            role = 'Родитель'
        elif conversation.director:
            partner = conversation.director
            role = 'Заведующая'
    
    elif current_user.role == 'parent':
        if conversation.teacher:
            partner = conversation.teacher
            role = 'Воспитатель'
        elif conversation.director:
            partner = conversation.director
            role = 'Заведующая'
    
    elif current_user.role == 'director':
        if conversation.teacher:
            partner = conversation.teacher
            role = 'Воспитатель'
        elif conversation.parent:
            partner = conversation.parent.user
            role = 'Родитель'
    
    if partner:
        return {
            'full_name': partner.get_full_name(),
            'photo_url': partner.photo.url if partner.photo else None,
            'role': role,
        }
    
    # Если не удалось определить партнера, возвращаем данные из conversation
    if conversation.parent:
        return {
            'full_name': conversation.parent.user.get_full_name(),
            'photo_url': conversation.parent.user.photo.url if conversation.parent.user.photo else None,
            'role': 'Родитель',
        }
    elif conversation.teacher:
        return {
            'full_name': conversation.teacher.get_full_name(),
            'photo_url': conversation.teacher.photo.url if conversation.teacher.photo else None,
            'role': 'Воспитатель',
        }
    elif conversation.director:
        return {
            'full_name': conversation.director.get_full_name(),
            'photo_url': conversation.director.photo.url if conversation.director.photo else None,
            'role': 'Заведующая',
        }
    
    return None


def get_conversation_avatar(conversation, current_user):
    """Получить URL аватара собеседника"""
    if current_user.role == 'teacher':
        if conversation.parent and conversation.parent.user.photo:
            return conversation.parent.user.photo.url
        elif conversation.director and conversation.director.photo:
            return conversation.director.photo.url
    elif current_user.role == 'parent':
        if conversation.teacher and conversation.teacher.photo:
            return conversation.teacher.photo.url
        elif conversation.director and conversation.director.photo:
            return conversation.director.photo.url
    elif current_user.role == 'director':
        if conversation.teacher and conversation.teacher.photo:
            return conversation.teacher.photo.url
        elif conversation.parent and conversation.parent.user.photo:
            return conversation.parent.user.photo.url
    return None