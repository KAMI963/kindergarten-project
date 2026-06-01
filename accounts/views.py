from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm 
from django.core.cache import cache
from django.db.models import Q, Sum, Count
from datetime import timedelta
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
import json
import traceback

# Правильный импорт
from applications.models import ChildApplication
from payments.models import Payment

from .forms import CustomUserCreationForm, EmailVerificationForm, ResendVerificationForm, ParentProfileFullForm
from .models import CustomUser, ParentProfile, EmailVerificationCode
from .tasks import send_verification_code_email, send_welcome_email

from .models import (
    CustomUser, ParentProfile, TeacherProfile, DirectorProfile,
    EmailVerificationCode, PasswordResetCode, UserLoginLog
)
from .tasks import (
    send_verification_code_email, send_welcome_email, send_password_reset_code
)
from children.models import Child, Group
from attendance.models import AttendanceSheet, AttendanceRecord

def get_client_ip(request):
    """Получает IP адрес клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
def profile(request):
    """Страница профиля пользователя"""
    user = request.user
    
    # Создаем профиль, если его нет
    from .models import ParentProfile, TeacherProfile, DirectorProfile
    
    if user.role == 'parent' and not hasattr(user, 'parentprofile'):
        ParentProfile.objects.create(user=user)
    elif user.role == 'teacher' and not hasattr(user, 'teacherprofile'):
        TeacherProfile.objects.create(user=user)
    elif user.role == 'director' and not hasattr(user, 'directorprofile'):
        DirectorProfile.objects.create(user=user)
    
    return render(request, 'accounts/profile.html', {'user': user})

@login_required
def check_username_ajax(request):
    """Проверка доступности логина (AJAX)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username', '').strip()
            
            if not username:
                return JsonResponse({'available': False, 'error': 'Логин не указан'})
            
            # Проверка формата
            import re
            if not re.match(r'^[a-zA-Z0-9]{3,30}$', username):
                return JsonResponse({'available': False, 'error': 'Неверный формат логина'})
            
            # Проверка существования
            from .models import CustomUser
            exists = CustomUser.objects.filter(username__iexact=username).exists()
            
            return JsonResponse({'available': not exists})
        except Exception as e:
            return JsonResponse({'available': False, 'error': str(e)})
    
    return JsonResponse({'error': 'Метод не разрешен'}, status=405)


def create_user_profile(user):
    """Создает профиль пользователя в зависимости от роли"""
    if user.role == 'parent' and not hasattr(user, 'parentprofile'):
        ParentProfile.objects.create(
            user=user,
            passport_series='0000',
            passport_number='000000',
            passport_issued_by='Не указано',
            passport_issue_date=timezone.now().date(),
            registration_address='Не указан',
            actual_address='Не указан'
        )
    elif user.role == 'teacher' and not hasattr(user, 'teacherprofile'):
        TeacherProfile.objects.create(
            user=user,
            education='Не указано',
            specialization='Не указано',
            experience=0,
            hire_date=timezone.now().date()
        )
    elif user.role == 'director' and not hasattr(user, 'directorprofile'):
        DirectorProfile.objects.create(
            user=user,
            education='Не указано',
            management_experience=0
        )

# accounts/views.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm 
from django.core.cache import cache
from django.db.models import Q
from datetime import timedelta
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.views.decorators.http import require_http_methods
import json

from .forms import (
    CustomUserCreationForm, EmailVerificationForm, ResendVerificationForm,
    CustomAuthenticationForm, PasswordResetRequestForm, PasswordResetCodeForm,
    CustomSetPasswordForm, ProfileEditForm, TeacherProfileForm, DirectorProfileForm
)

from .models import (
    CustomUser, ParentProfile, TeacherProfile, DirectorProfile,
    EmailVerificationCode, PasswordResetCode, UserLoginLog
)
from .tasks import (
    send_verification_code_email, send_welcome_email, send_password_reset_code
)
from children.models import Child, Group
from attendance.models import AttendanceSheet, AttendanceRecord


@require_http_methods(["POST"])
def verify_email_ajax(request):
    """AJAX обработка подтверждения email"""
    import json
    
    try:
        data = json.loads(request.body)
        code = data.get('code', '')
        
        user_id = request.session.get('pending_user_id')
        if not user_id:
            return JsonResponse({'success': False, 'error': 'Сессия истекла'}, status=400)
        
        user = CustomUser.objects.get(id=user_id)
        
        # Поиск кода
        verification_code = EmailVerificationCode.objects.filter(
            user=user,
            code=code,
            is_used=False
        ).latest('created_at')
        
        if not verification_code.is_valid():
            return JsonResponse({'success': False, 'error': 'Срок действия кода истек'}, status=400)
        
        # Подтверждаем
        verification_code.is_used = True
        verification_code.save()
        
        user.email_verified = True
        user.save()
        
        # Авторизуем
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Очищаем сессию
        if 'pending_user_id' in request.session:
            del request.session['pending_user_id']
        
        # Отправляем приветственное письмо (синхронно, без .delay)
        send_welcome_email(user.id)
        
        return JsonResponse({
            'success': True,
            'redirect_url': reverse('dashboard')
        })
        
    except EmailVerificationCode.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Неверный код подтверждения'}, status=400)
    except Exception as e:
        print(f"Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def register(request):
    """Регистрация пользователя с отладкой"""
    
    print("\n" + "="*70)
    print("🔵 [REGISTER] Функция register вызвана")
    print(f"🔵 [REGISTER] Метод запроса: {request.method}")
    print(f"🔵 [REGISTER] Пользователь авторизован: {request.user.is_authenticated}")
    print("="*70)
    
    if request.user.is_authenticated:
        print("🟡 [REGISTER] Пользователь уже авторизован, перенаправление на dashboard")
        return redirect('dashboard')
    
    if request.method == 'POST':
        print("\n📥 [REGISTER] Обработка POST запроса")
        print(f"📥 [REGISTER] POST данные: {request.POST}")
        
        form = CustomUserCreationForm(request.POST)
        
        if form.is_valid():
            print("✅ [REGISTER] Форма валидна")
            
            try:
                user = form.save(commit=False)
                user.email_verified = False
                user.save()
                print(f"✅ [REGISTER] Пользователь создан: ID={user.id}, username={user.username}, email={user.email}, role={user.role}")
                
                # Создаем профиль
                if user.role == 'parent':
                    profile = ParentProfile.objects.create(
                        user=user,
                        has_completed_initial_profile=False,
                    )
                    print(f"✅ [REGISTER] Создан ParentProfile для user_id={user.id}")
                elif user.role == 'teacher':
                    profile = TeacherProfile.objects.create(user=user)
                    print(f"✅ [REGISTER] Создан TeacherProfile для user_id={user.id}")
                elif user.role == 'director':
                    profile = DirectorProfile.objects.create(user=user)
                    print(f"✅ [REGISTER] Создан DirectorProfile для user_id={user.id}")
                
                # Сохраняем в сессии
                request.session['pending_user_id'] = user.id
                print(f"✅ [REGISTER] Сессия: pending_user_id={user.id}")
                
                # Отправляем код
                print(f"📧 [REGISTER] Отправка кода подтверждения на {user.email}")
                result = send_verification_code_email(user.id, user.email)
                print(f"📧 [REGISTER] Результат отправки: {result}")
                
                messages.success(request, 'На ваш email отправлен код подтверждения. Проверьте вашу почту.')
                print("✅ [REGISTER] Успешная регистрация, перенаправление на verify_email")
                return redirect('accounts:verify_email')
                
            except Exception as e:
                print(f"❌ [REGISTER] ОШИБКА при создании пользователя: {str(e)}")
                print(f"❌ [REGISTER] Трассировка: {traceback.format_exc()}")
                messages.error(request, f'Ошибка при регистрации: {str(e)}')
        else:
            print("❌ [REGISTER] Форма НЕ валидна")
            print(f"❌ [REGISTER] Ошибки формы: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    print(f"   - {field}: {error}")
                    messages.error(request, f'{field}: {error}')
    else:
        print("📝 [REGISTER] GET запрос, показываем пустую форму")
        form = CustomUserCreationForm(initial={'role': 'parent'})
    
    print("🖥️ [REGISTER] Рендеринг шаблона register.html")
    return render(request, 'accounts/register.html', {'form': form})


def verify_email(request):
    """Подтверждение email с отладкой"""
    
    print("\n" + "="*70)
    print("🔵 [VERIFY_EMAIL] Функция verify_email вызвана")
    print(f"🔵 [VERIFY_EMAIL] Метод запроса: {request.method}")
    print(f"🔵 [VERIFY_EMAIL] AJAX запрос: {request.headers.get('X-Requested-With') == 'XMLHttpRequest'}")
    print("="*70)
    
    user_id = request.session.get('pending_user_id')
    print(f"📌 [VERIFY_EMAIL] pending_user_id из сессии: {user_id}")
    
    if not user_id:
        print("❌ [VERIFY_EMAIL] Нет pending_user_id в сессии")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Сессия истекла'}, status=400)
        messages.error(request, 'Сессия истекла. Пожалуйста, зарегистрируйтесь снова.')
        return redirect('accounts:register')
    
    try:
        user = CustomUser.objects.get(id=user_id)
        print(f"✅ [VERIFY_EMAIL] Найден пользователь: {user.username}, email={user.email}")
        print(f"   - email_verified: {user.email_verified}")
    except CustomUser.DoesNotExist:
        print(f"❌ [VERIFY_EMAIL] Пользователь с id={user_id} не найден")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Пользователь не найден'}, status=400)
        messages.error(request, 'Пользователь не найден.')
        return redirect('accounts:register')
    
    # AJAX обработка
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        print("📡 [VERIFY_EMAIL] Обработка AJAX POST запроса")
        try:
            data = json.loads(request.body)
            code = data.get('code', '')
            print(f"📝 [VERIFY_EMAIL] Получен код: {code}")
            
            verification_code = EmailVerificationCode.objects.filter(
                user=user,
                code=code,
                is_used=False
            ).latest('created_at')
            print(f"✅ [VERIFY_EMAIL] Найден код в БД: id={verification_code.id}")
            print(f"   - expires_at: {verification_code.expires_at}")
            print(f"   - is_used: {verification_code.is_used}")
            print(f"   - is_valid: {verification_code.is_valid()}")
            
            if not verification_code.is_valid():
                print("❌ [VERIFY_EMAIL] Код истек")
                return JsonResponse({'success': False, 'error': 'Срок действия кода истек'}, status=400)
            
            # Подтверждаем
            verification_code.is_used = True
            verification_code.save()
            user.email_verified = True
            user.save()
            print(f"✅ [VERIFY_EMAIL] Email подтвержден для {user.email}")
            
            # Авторизуем
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            print(f"✅ [VERIFY_EMAIL] Пользователь авторизован")
            
            # Очищаем сессию
            if 'pending_user_id' in request.session:
                del request.session['pending_user_id']
                print("✅ [VERIFY_EMAIL] Сессия очищена")
            
            # Отправляем приветственное письмо
            send_welcome_email(user.id)
            
            redirect_url = reverse('dashboard')
            print(f"✅ [VERIFY_EMAIL] Перенаправление на: {redirect_url}")
            
            return JsonResponse({
                'success': True,
                'message': 'Email успешно подтвержден',
                'redirect_url': redirect_url
            })
            
        except EmailVerificationCode.DoesNotExist:
            print(f"❌ [VERIFY_EMAIL] Код {code} не найден в БД")
            return JsonResponse({'success': False, 'error': 'Неверный код подтверждения'}, status=400)
        except Exception as e:
            print(f"❌ [VERIFY_EMAIL] Ошибка: {str(e)}")
            print(f"❌ [VERIFY_EMAIL] Трассировка: {traceback.format_exc()}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    # Обычный POST запрос
    if request.method == 'POST':
        print("📡 [VERIFY_EMAIL] Обработка обычного POST запроса")
        form = EmailVerificationForm(request.POST, user=user)
        if form.is_valid():
            print("✅ [VERIFY_EMAIL] Форма валидна")
            form.verification_code.is_used = True
            form.verification_code.save()
            user.email_verified = True
            user.save()
            
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            del request.session['pending_user_id']
            send_welcome_email(user.id)
            
            messages.success(request, 'Email успешно подтвержден! Добро пожаловать!')
            return redirect('dashboard')
        else:
            print(f"❌ [VERIFY_EMAIL] Ошибки формы: {form.errors}")
    else:
        form = EmailVerificationForm(user=user)
    
    # Получаем время истечения кода
    try:
        latest_code = EmailVerificationCode.objects.filter(
            user=user, is_used=False
        ).latest('created_at')
        expires_in = int((latest_code.expires_at - timezone.now()).total_seconds() // 60)
        print(f"📌 [VERIFY_EMAIL] Код действителен еще {expires_in} минут")
    except EmailVerificationCode.DoesNotExist:
        expires_in = 15
        print("⚠️ [VERIFY_EMAIL] Код не найден, установлен expires_in=15")
    
    return render(request, 'accounts/verify_email.html', {
        'form': form,
        'email': user.email,
        'expires_in': expires_in
    })

def resend_verification_code(request):
    """Повторная отправка кода подтверждения (не AJAX версия)"""
    print("\n" + "="*70)
    print("🔵 [RESEND_CODE_FORM] Функция resend_verification_code вызвана")
    print(f"🔵 [RESEND_CODE_FORM] Метод запроса: {request.method}")
    print("="*70)
    
    if request.method == 'POST':
        form = ResendVerificationForm(request.POST)
        if form.is_valid():
            user = form.user
            print(f"✅ [RESEND_CODE_FORM] Найден пользователь: {user.email}")
            
            # Отправляем новый код
            send_verification_code_email(user.id, user.email)
            
            # Обновляем сессию
            request.session['pending_user_id'] = user.id
            
            messages.success(request, 'Новый код подтверждения отправлен на ваш email.')
            return redirect('accounts:verify_email')
        else:
            print(f"❌ [RESEND_CODE_FORM] Ошибки формы: {form.errors}")
    else:
        form = ResendVerificationForm()
    
    return render(request, 'accounts/resend_verification.html', {'form': form})


def resend_verification_ajax(request):
    """AJAX повторная отправка кода с отладкой"""
    
    print("\n" + "="*70)
    print("🔵 [RESEND_CODE] Функция resend_verification_ajax вызвана")
    print(f"🔵 [RESEND_CODE] Метод запроса: {request.method}")
    print("="*70)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            print(f"📝 [RESEND_CODE] Email для повторной отправки: {email}")
            
            if not email:
                print("❌ [RESEND_CODE] Email не указан")
                return JsonResponse({'success': False, 'error': 'Email не указан'})
            
            try:
                user = CustomUser.objects.get(email=email, email_verified=False)
                print(f"✅ [RESEND_CODE] Найден пользователь: {user.username}, id={user.id}")
            except CustomUser.DoesNotExist:
                print(f"❌ [RESEND_CODE] Пользователь с email={email} не найден или уже подтвержден")
                return JsonResponse({'success': False, 'error': 'Пользователь не найден или уже подтвержден'})
            
            print(f"📧 [RESEND_CODE] Отправка нового кода на {email}")
            result = send_verification_code_email(user.id, user.email)
            print(f"📧 [RESEND_CODE] Результат отправки: {result}")
            
            request.session['pending_user_id'] = user.id
            print(f"✅ [RESEND_CODE] Сессия обновлена: pending_user_id={user.id}")
            
            return JsonResponse({
                'success': True,
                'message': 'Код подтверждения отправлен повторно',
                'expires_in': 15
            })
            
        except Exception as e:
            print(f"❌ [RESEND_CODE] Ошибка: {str(e)}")
            print(f"❌ [RESEND_CODE] Трассировка: {traceback.format_exc()}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    print("❌ [RESEND_CODE] Неверный метод запроса")
    return JsonResponse({'success': False, 'error': 'Неверный запрос'})

def custom_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Проверяем существование модели UserLoginLog перед записью
                try:
                    from .models import UserLoginLog
                    # Создаем запись в логе входа
                    UserLoginLog.objects.create(
                        user=user,
                        ip_address=request.META.get('REMOTE_ADDR', ''),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255]
                    )
                except (ImportError, AttributeError, Exception):
                    # Если модели нет или другая ошибка, просто пропускаем
                    pass
                
                messages.success(request, f'Добро пожаловать, {user.username}!')
                
                # Перенаправление на основе роли
                if user.role == 'director':
                    return redirect('dashboard')
                elif user.role == 'teacher':
                    return redirect('attendance:attendance_dashboard')
                elif user.role == 'parent':
                    return redirect('dashboard')
                else:
                    return redirect('dashboard')
            else:
                messages.error(request, 'Неверное имя пользователя или пароль.')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки ниже.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def custom_logout(request):
    """Выход из системы"""
    logout(request)
   
    return redirect('home')

def password_reset_request(request):
    """Запрос на восстановление пароля"""
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            user = form.user
            
            # Отправляем код восстановления
            send_password_reset_code.delay(user.id, user.email)
            
            # Сохраняем user_id в сессии
            request.session['password_reset_user_id'] = user.id
            
            messages.success(request, 'Код для восстановления пароля отправлен на ваш email.')
            return redirect('accounts:password_reset_verify')
    else:
        form = PasswordResetRequestForm()
    
    return render(request, 'accounts/password_reset_request.html', {'form': form})

def password_reset_verify(request):
    """Проверка кода восстановления пароля"""
    user_id = request.session.get('password_reset_user_id')
    
    if not user_id:
        messages.error(request, 'Сессия истекла. Пожалуйста, начните восстановление пароля заново.')
        return redirect('accounts:password_reset_request')
    
    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'Пользователь не найден.')
        return redirect('accounts:password_reset_request')
    
    if request.method == 'POST':
        form = PasswordResetCodeForm(request.POST, user=user)
        if form.is_valid():
            # Отмечаем код как использованный
            form.reset_code.is_used = True
            form.reset_code.save()
            
            # Сохраняем в сессии, что код подтвержден
            request.session['password_reset_verified'] = True
            
            messages.success(request, 'Код подтвержден. Теперь вы можете установить новый пароль.')
            return redirect('accounts:password_reset_confirm')
    else:
        form = PasswordResetCodeForm(user=user)
    
    # Показываем, сколько времени осталось до истечения кода
    try:
        latest_code = PasswordResetCode.objects.filter(
            user=user, is_used=False
        ).latest('created_at')
        expires_in = (latest_code.expires_at - timezone.now()).total_seconds() // 60
    except PasswordResetCode.DoesNotExist:
        expires_in = 15
    
    return render(request, 'accounts/password_reset_verify.html', {
        'form': form,
        'email': user.email,
        'expires_in': int(expires_in)
    })

def password_reset_confirm(request):
    """Установка нового пароля"""
    user_id = request.session.get('password_reset_user_id')
    verified = request.session.get('password_reset_verified', False)
    
    if not user_id or not verified:
        messages.error(request, 'Неверная последовательность действий. Пожалуйста, начните восстановление пароля заново.')
        return redirect('accounts:password_reset_request')
    
    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'Пользователь не найден.')
        return redirect('accounts:password_reset_request')
    
    if request.method == 'POST':
        form = CustomSetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            
            # Очищаем сессию
            del request.session['password_reset_user_id']
            del request.session['password_reset_verified']
            
            messages.success(request, 'Пароль успешно изменен! Теперь вы можете войти с новым паролем.')
            return redirect('accounts:login')
    else:
        form = CustomSetPasswordForm(user)
    
    return render(request, 'accounts/password_reset_confirm.html', {'form': form})

# accounts/views.py - добавьте эту функцию

# accounts/views.py - уберите @login_required

def resend_verification_ajax(request):  # Убрали @login_required
    """AJAX запрос на повторную отправку кода"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({'success': False, 'error': 'Email не указан'})
            
            try:
                user = CustomUser.objects.get(email=email, email_verified=False)
            except CustomUser.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Пользователь не найден или уже подтвержден'})
            
            send_verification_code_email(user.id, user.email)
            request.session['pending_user_id'] = user.id
            
            return JsonResponse({
                'success': True,
                'message': 'Код подтверждения отправлен повторно',
                'expires_in': 15
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Неверный запрос'})

def get_teacher_dashboard_context(user):
    """Получает контекст для панели воспитателя"""
    current_date = timezone.now().date()
    current_time = timezone.now().time()
    
    days_russian = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда', 
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }
    current_day_name = days_russian.get(current_date.strftime('%A'), current_date.strftime('%A'))
    
    context = {
        'current_date': current_date,
        'current_time': current_time,
        'current_day_name': current_day_name,
    }
    
    try:
        group = Group.objects.filter(teacher=user).first()
    except Group.DoesNotExist:
        group = None
    
    if group:
        group_children = Child.objects.filter(group=group, is_active=True)
        
        # ИСПРАВЛЕНО: получаем данные из табелей вместо старой модели Attendance
        present_count = 0
        absent_count = 0
        sick_count = 0
        vacation_count = 0
        
        try:
            # Получаем табель за текущий месяц
            sheet = AttendanceSheet.objects.get(
                group=group,
                month=current_date.month,
                year=current_date.year
            )
            
            # Получаем записи для всех детей
            for child in group_children:
                try:
                    record = AttendanceRecord.objects.get(sheet=sheet, child=child)
                    status = record.get_day_status(current_date.day)
                    
                    if status == 'present':
                        present_count += 1
                    elif status == 'absent':
                        absent_count += 1
                    elif status == 'sick':
                        sick_count += 1
                    elif status == 'vacation':
                        vacation_count += 1
                    else:
                        absent_count += 1
                except AttendanceRecord.DoesNotExist:
                    absent_count += 1
        except AttendanceSheet.DoesNotExist:
            # Если табель не создан, все дети считаются отсутствующими
            absent_count = group_children.count()
        
        present_ids = []
        absent_ids = []
        
        # Получаем IDs для статистики
        try:
            sheet = AttendanceSheet.objects.get(
                group=group,
                month=current_date.month,
                year=current_date.year
            )
            for child in group_children:
                try:
                    record = AttendanceRecord.objects.get(sheet=sheet, child=child)
                    status = record.get_day_status(current_date.day)
                    if status == 'present':
                        present_ids.append(child.id)
                    else:
                        absent_ids.append(child.id)
                except AttendanceRecord.DoesNotExist:
                    absent_ids.append(child.id)
        except AttendanceSheet.DoesNotExist:
            absent_ids = [child.id for child in group_children]
        
        today = timezone.now().date()
        birthdays_today = group_children.filter(
            birth_date__month=today.month,
            birth_date__day=today.day
        )
        
        birthdays_this_month = group_children.filter(
            birth_date__month=today.month
        ).order_by('birth_date__day')
        
        # Данные за неделю
        weekly_attendance = []
        for i in range(6, -1, -1):
            day_date = current_date - timedelta(days=i)
            day_present = 0
            day_total = group_children.count()
            
            try:
                sheet = AttendanceSheet.objects.get(
                    group=group,
                    month=day_date.month,
                    year=day_date.year
                )
                for child in group_children:
                    try:
                        record = AttendanceRecord.objects.get(sheet=sheet, child=child)
                        if record.get_day_status(day_date.day) == 'present':
                            day_present += 1
                    except AttendanceRecord.DoesNotExist:
                        pass
            except AttendanceSheet.DoesNotExist:
                pass
            
            day_rate = round((day_present / day_total) * 100, 1) if day_total > 0 else 0
            
            weekly_attendance.append({
                'date': day_date,
                'present': day_present,
                'total': day_total,
                'rate': day_rate
            })
        
        avg_rate = round(sum(day['rate'] for day in weekly_attendance) / len(weekly_attendance), 1) if weekly_attendance else 0
        
        context.update({
            'group': group,
            'group_children': group_children,
            'today_attendance': {
                'present_count': present_count,
                'absent_count': absent_count,
                'sick_count': sick_count,
                'vacation_count': vacation_count,
                'present_ids': present_ids,
                'absent_ids': absent_ids,
                'total': group_children.count()
            },
            'today_attendance_rate': round((present_count / group_children.count()) * 100, 1) if group_children.count() > 0 else 0,
            'birthdays_today': birthdays_today,
            'birthdays_this_month': birthdays_this_month,
            'weekly_attendance': {
                'days': weekly_attendance,
                'average_rate': avg_rate
            }
        })
    else:
        context.update({
            'group': None,
            'group_children': Child.objects.none(),
            'today_attendance': {
                'present_count': 0,
                'absent_count': 0,
                'sick_count': 0,
                'vacation_count': 0,
                'present_ids': [],
                'absent_ids': [],
                'total': 0
            },
            'today_attendance_rate': 0,
            'birthdays_today': [],
            'birthdays_this_month': [],
            'weekly_attendance': {
                'days': [],
                'average_rate': 0
            }
        })
    
    return context

def get_director_dashboard_context(user):
    """Получает контекст для панели заведующей"""
    from applications.models import ChildApplication
    from children.models import Child, Group
    from accounts.models import CustomUser
    from attendance.models import AttendanceSheet, AttendanceRecord
    from payments.models import Payment
    from datetime import date, timedelta
    from django.db.models import Q, Sum
    
    # Получаем текущий месяц
    today = date.today()
    current_month = today.month
    current_year = today.year
    
    # Статистика посещаемости за текущий месяц
    total_possible = 0
    total_present = 0
    
    groups = Group.objects.all()
    for group in groups:
        try:
            sheet = AttendanceSheet.objects.get(
                group=group,
                month=current_month,
                year=current_year
            )
            # Количество рабочих дней
            workdays = sheet.get_working_days()
            # Количество детей в группе
            children_count = group.children_count
            # Всего возможных посещений
            group_possible = workdays * children_count
            
            # Считаем фактические посещения
            group_present = 0
            for record in sheet.records.all():
                group_present += record.get_present_days()
            
            total_possible += group_possible
            total_present += group_present
        except AttendanceSheet.DoesNotExist:
            pass
    
    # Процент посещаемости
    attendance_rate = round((total_present / total_possible) * 100, 1) if total_possible > 0 else 0
    
    # Статистика платежей
    pending_payments_count = Payment.objects.filter(
        status='pending'
    ).count()
    
    # Сумма ожидающих платежей
    pending_payments_sum = Payment.objects.filter(
        status='pending'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    return {
        'pending_applications_count': ChildApplication.objects.filter(status='pending').count(),
        'total_children_count': Child.objects.filter(is_active=True).count(),
        'staff_count': CustomUser.objects.filter(role__in=['teacher', 'director']).count(),
        'groups_count': Group.objects.count(),
        'pending_applications': ChildApplication.objects.filter(status='pending')[:5],
        'attendance_rate': attendance_rate,
        'pending_payments_count': pending_payments_count,
        'pending_payments_sum': pending_payments_sum,
    }

@login_required
def dashboard(request):
    user = request.user
    create_user_profile(user)
    
    # === НОВЫЙ КОД: Проверка для родителей ===
    if user.role == 'parent' and hasattr(user, 'parentprofile'):
        profile = user.parentprofile
        
        # Если родитель еще не заполнил анкету после регистрации
        if not profile.has_completed_initial_profile:
            # Проверяем, есть ли уже заполненные данные
            has_data = (
                profile.full_name or 
                profile.passport_series not in ['', '0000'] or
                profile.registration_address not in ['', 'Не указан']
            )
            
            if not has_data:
                # Первый вход - перенаправляем на анкету
                messages.info(request, 'Пожалуйста, заполните анкету родителя для продолжения работы')
                return redirect('accounts:parent_profile')
    
    # Остальной код dashboard
    context = {'user': user}
    
    if user.role == 'director' and hasattr(user, 'directorprofile'):
        context.update(get_director_dashboard_context(user))
        template_name = 'dashboard/director_dashboard_simple.html'
    elif user.role == 'teacher' and hasattr(user, 'teacherprofile'):
        context.update(get_teacher_dashboard_context(user))
        template_name = 'dashboard/teacher_dashboard_simple.html'
    elif user.role == 'parent' and hasattr(user, 'parentprofile'):
        # ===== ДОБАВЬТЕ ЭТУ ФУНКЦИЮ ДЛЯ РОДИТЕЛЯ =====
        context.update(get_parent_dashboard_context(user))
        template_name = 'dashboard/parent_dashboard.html'
    else:
        template_name = 'dashboard/base_dashboard.html'
    
    return render(request, template_name, context)


def get_parent_dashboard_context(user):
    """Получает контекст для панели родителя"""
    from children.models import ChildParent, Child
    from applications.models import ChildApplication
    from payments.models import Payment
    from datetime import date
    from django.db.models import Sum  # <-- ДОБАВИТЬ
    
    profile = user.parentprofile
    
    # ===== ДЕТИ =====
    child_ids = ChildParent.objects.filter(parent=profile).values_list('child_id', flat=True)
    children = Child.objects.filter(id__in=child_ids, is_active=True)
    children_count = children.count()
    
    # ===== ЗАЯВЛЕНИЯ =====
    applications = ChildApplication.objects.filter(parent=profile)
    applications_count = applications.count()
    recent_applications = applications.order_by('-created_at')[:5]
    
    # ===== АКТИВНОЕ ЗАЯВЛЕНИЕ ДЛЯ ОЧЕРЕДИ =====
    active_statuses = ['pending', 'queue', 'invited', 'processing']
    active_application = applications.filter(status__in=active_statuses).first()
    
    # ===== ДАННЫЕ ДЛЯ ОЧЕРЕДИ =====
    queue_position = None
    total_in_queue = 0
    
    if active_application:
        queue_position = active_application.get_queue_position()
        total_in_queue = ChildApplication.objects.filter(status='queue').count()
        if active_application.age_category:
            total_in_queue = ChildApplication.objects.filter(
                status='queue',
                age_category=active_application.age_category
            ).count()
    
    # ===== НЕОПЛАЧЕННЫЕ ПЛАТЕЖИ =====
    pending_payments_count = 0
    if children.exists():
        pending_payments_count = Payment.objects.filter(
            child__in=children,
            status='pending'
        ).count()
    
    # ===== ФИНАНСОВАЯ СТАТИСТИКА =====
    total_charged = Payment.objects.filter(
        child__in=children
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    total_paid = Payment.objects.filter(
        child__in=children,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    current_balance = total_paid - total_charged
    
    # ===== ТЕКУЩИЙ МЕСЯЦ =====
    today = date.today()
    current_month_payment = Payment.objects.filter(
        child__in=children,
        month=today.month,
        year=today.year,
        status__in=['pending', 'overdue']
    ).first()
    
    context = {
        'children': children,
        'children_count': children_count,
        'applications': applications,
        'applications_count': applications_count,
        'recent_applications': recent_applications,
        'active_application': active_application,
        'queue_position': queue_position,
        'total_in_queue': total_in_queue,
        'pending_payments_count': pending_payments_count,
        'total_charged': total_charged,
        'total_paid': total_paid,
        'current_balance': current_balance,
        'current_month_payment': current_month_payment,
    }
    
    return context

# accounts/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages


import os
@login_required
def change_photo(request):
    """Изменение фото профиля (AJAX)"""
    if request.method == 'POST':
        user = request.user
        
        # Проверяем, нужно ли удалить фото
        try:
            data = json.loads(request.body)
            if data.get('delete'):
                if user.photo:
                    # Удаляем файл
                    if os.path.isfile(user.photo.path):
                        os.remove(user.photo.path)
                    user.photo = None
                    user.save()
                return JsonResponse({'success': True, 'message': 'Фото удалено'})
        except:
            pass
        
        # Загрузка нового фото
        if request.FILES.get('photo'):
            photo = request.FILES['photo']
            
            # Проверка типа файла
            if not photo.content_type.startswith('image/'):
                return JsonResponse({'success': False, 'error': 'Можно загружать только изображения'})
            
            # Проверка размера (максимум 5MB)
            if photo.size > 5 * 1024 * 1024:
                return JsonResponse({'success': False, 'error': 'Размер файла не должен превышать 5MB'})
            
            # Удаляем старое фото, если есть
            if user.photo and os.path.isfile(user.photo.path):
                os.remove(user.photo.path)
            
            # Сохраняем новое фото
            user.photo = photo
            user.save()
            
            return JsonResponse({
                'success': True,
                'photo_url': user.photo.url,
                'message': 'Фото успешно загружено'
            })
        
        return JsonResponse({'success': False, 'error': 'Файл не выбран'})
    
    return JsonResponse({'success': False, 'error': 'Метод не разрешен'}, status=405)


# accounts/views.py

@login_required
def profile_view(request):
    """Профиль пользователя"""
    user = request.user
    
    # Получаем фото пользователя из разных мест
    user_photo = None
    if user.photo and user.photo.url:
        user_photo = user.photo
        print(f"DEBUG: Фото найдено в user.photo: {user_photo.url}")
    elif hasattr(user, 'parentprofile') and user.parentprofile.photo and user.parentprofile.photo.url:
        user_photo = user.parentprofile.photo
        print(f"DEBUG: Фото найдено в parentprofile.photo: {user_photo.url}")
    else:
        print("DEBUG: Фото не найдено")
    
    parent_profile = None
    teacher_profile = None
    director_profile = None
    
    if user.role == 'parent':
        parent_profile = getattr(user, 'parentprofile', None)
    elif user.role == 'teacher':
        teacher_profile = getattr(user, 'teacherprofile', None)
    elif user.role == 'director':
        director_profile = getattr(user, 'directorprofile', None)
    
    context = {
        'user': user,
        'user_photo': user_photo,
        'parent_profile': parent_profile,
        'teacher_profile': teacher_profile,
        'director_profile': director_profile,
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def upload_parent_photo(request):
    """Загрузка фото родителя (AJAX)"""
    if request.method == 'POST':
        user = request.user
        
        if not hasattr(user, 'parentprofile'):
            return JsonResponse({'success': False, 'error': 'Профиль родителя не найден'})
        
        profile = user.parentprofile
        
        if request.FILES.get('photo'):
            photo = request.FILES['photo']
            
            # Проверка типа файла
            if not photo.content_type.startswith('image/'):
                return JsonResponse({'success': False, 'error': 'Можно загружать только изображения'})
            
            # Проверка размера
            if photo.size > 5 * 1024 * 1024:
                return JsonResponse({'success': False, 'error': 'Размер файла не должен превышать 5MB'})
            
            # Удаляем старое фото
            if profile.photo and os.path.isfile(profile.photo.path):
                os.remove(profile.photo.path)
            
            # Сохраняем новое фото
            profile.photo = photo
            profile.save()
            
            return JsonResponse({
                'success': True,
                'photo_url': profile.photo.url,
                'message': 'Фото успешно загружено'
            })
        
        # Удаление фото
        try:
            data = json.loads(request.body)
            if data.get('delete'):
                if profile.photo and os.path.isfile(profile.photo.path):
                    os.remove(profile.photo.path)
                profile.photo = None
                profile.save()
                return JsonResponse({'success': True, 'message': 'Фото удалено'})
        except:
            pass
        
        return JsonResponse({'success': False, 'error': 'Файл не выбран'})
    
    return JsonResponse({'success': False, 'error': 'Метод не разрешен'}, status=405)

from datetime import datetime

# accounts/views.py
@login_required
def edit_profile(request):
    """Редактирование профиля"""
    user = request.user
    
    # Для отладки - выведем данные в консоль
    print("=" * 50)
    print(f"Пользователь: {user.username}")
    print(f"Имя: {user.first_name}")
    print(f"Фамилия: {user.last_name}")
    print(f"Email: {user.email}")
    print(f"Телефон: {user.phone}")
    print(f"Дата рождения: {user.birth_date}")
    print(f"Адрес: {user.address}")
    print("=" * 50)
    
    if request.method == 'POST':
        # Сохраняем данные
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.phone = request.POST.get('phone', '')
        user.address = request.POST.get('address', '')
        
        birth_date = request.POST.get('birth_date', '')
        if birth_date:
            from datetime import datetime
            try:
                user.birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            except:
                pass
        else:
            user.birth_date = None
        
        user.save()
        
        messages.success(request, 'Профиль успешно обновлен!')
        return redirect('accounts:profile')
    
    # Передаем все данные в шаблон
    context = {
        'user': user,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'phone': user.phone or '',
        'birth_date': user.birth_date.strftime('%Y-%m-%d') if user.birth_date else '',
        'address': user.address or '',
    }
    
    # Добавляем данные для воспитателя
    if user.role == 'teacher' and hasattr(user, 'teacherprofile'):
        context['education'] = user.teacherprofile.education or ''
        context['specialization'] = user.teacherprofile.specialization or ''
        context['experience'] = user.teacherprofile.experience or 0
        print(f"Образование: {context['education']}")
        print(f"Специализация: {context['specialization']}")
        print(f"Стаж: {context['experience']}")
    
    # Добавляем данные для заведующей
    elif user.role == 'director' and hasattr(user, 'directorprofile'):
        context['education'] = user.directorprofile.education or ''
        context['management_experience'] = user.directorprofile.management_experience or 0
    
    # Добавляем данные для родителя
    elif user.role == 'parent' and hasattr(user, 'parentprofile'):
        context['passport_series'] = user.parentprofile.passport_series or ''
        context['passport_number'] = user.parentprofile.passport_number or ''
        context['passport_issued_by'] = user.parentprofile.passport_issued_by or ''
        context['passport_issue_date'] = user.parentprofile.passport_issue_date.strftime('%Y-%m-%d') if user.parentprofile.passport_issue_date else ''
        context['registration_address'] = user.parentprofile.registration_address or ''
        context['actual_address'] = user.parentprofile.actual_address or ''
    
    return render(request, 'accounts/edit_profile.html', context)

@login_required
def change_password(request):
    """Смена пароля пользователя"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Обновляем сессию, чтобы пользователя не разлогинило
            update_session_auth_hash(request, user)
            messages.success(request, 'Пароль успешно изменен!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {
        'form': form
    })
 
 
 # accounts/views.py - добавьте эту функцию

@login_required
def parent_profile_edit(request):
    """Редактирование профиля родителя"""
    
    if request.user.role != 'parent':
        messages.error(request, 'Доступ только для родителей')
        return redirect('dashboard')
    
    profile, created = ParentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Обновляем профиль
        profile.full_name = request.POST.get('full_name', profile.full_name)
        
        birth_date = request.POST.get('birth_date', '')
        if birth_date:
            from datetime import datetime
            try:
                profile.birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            except:
                pass
        
        profile.nationality = request.POST.get('nationality', '')
        profile.passport_series = request.POST.get('passport_series', '')
        profile.passport_number = request.POST.get('passport_number', '')
        
        passport_issue_date = request.POST.get('passport_issue_date', '')
        if passport_issue_date:
            try:
                profile.passport_issue_date = datetime.strptime(passport_issue_date, '%Y-%m-%d').date()
            except:
                pass
        
        profile.passport_issued_by = request.POST.get('passport_issued_by', '')
        profile.registration_address = request.POST.get('registration_address', '')
        
        address_same = request.POST.get('address_same_as_registration')
        profile.address_same_as_registration = address_same == 'on'
        
        if profile.address_same_as_registration:
            profile.actual_address = profile.registration_address
        else:
            profile.actual_address = request.POST.get('actual_address', '')
        
        profile.mobile_phone = request.POST.get('mobile_phone', '')
        profile.home_phone = request.POST.get('home_phone', '')
        profile.work_phone = request.POST.get('work_phone', '')
        profile.workplace = request.POST.get('workplace', '')
        profile.position = request.POST.get('position', '')
        profile.not_working = request.POST.get('not_working') == 'on'
        
        profile.has_completed_initial_profile = True
        profile.profile_completed = True
        profile.save()
        
        # Обновляем пользователя
        request.user.phone = profile.mobile_phone
        request.user.birth_date = profile.birth_date
        
        name_parts = profile.full_name.split()
        if len(name_parts) >= 2:
            request.user.last_name = name_parts[0]
            request.user.first_name = ' '.join(name_parts[1:])
        elif len(name_parts) == 1:
            request.user.first_name = name_parts[0]
        
        request.user.save()
        
        messages.success(request, 'Профиль успешно обновлен!')
        return redirect('accounts:profile')
    
    nationalities = [
        "Русский", "Татарский", "Украинский", "Белорусский", "Казахский",
        "Армянский", "Азербайджанский", "Грузинский", "Молдавский", "Узбекский",
        "Таджикский", "Киргизский", "Туркменский", "Чеченский", "Осетинский",
        "Еврейский", "Немецкий", "Французский", "Английский", "Итальянский",
        "Испанский", "Греческий", "Китайский", "Вьетнамский", "Корейский",
        "Другой"
    ]
    
    context = {
        'profile': profile,
        'nationalities': nationalities,
    }
    
    return render(request, 'accounts/parent_profile_edit.html', context)
 
 
from .forms import ParentProfileFullForm  
    
@login_required
def parent_profile_view(request):
    """Представление для заполнения анкеты родителя"""
    
    if request.user.role != 'parent':
        messages.error(request, 'Доступ только для родителей')
        return redirect('dashboard')
    
    profile, created = ParentProfile.objects.get_or_create(user=request.user)
    
    if created:
        profile.full_name = request.user.get_full_name()
        profile.birth_date = request.user.birth_date
        profile.mobile_phone = request.user.phone
        profile.save()
    
    # Обработка AJAX-запроса
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # ... код для AJAX (остается без изменений) ...
        pass
    
    # Обработка сохранения формы
    if request.method == 'POST':
        form = ParentProfileFullForm(request.POST, instance=profile)
        if form.is_valid():
            saved_profile = form.save(commit=False)
            
            # Обработка чекбоксов
            address_same = request.POST.get('address_same_as_registration') == 'on'
            not_working = request.POST.get('not_working') == 'on'
            
            saved_profile.address_same_as_registration = address_same
            saved_profile.not_working = not_working
            
            if address_same:
                saved_profile.actual_address = saved_profile.registration_address
            
            saved_profile.has_completed_initial_profile = True
            saved_profile.profile_completed = True
            saved_profile.save()
            
            # Обновляем пользователя
            request.user.phone = saved_profile.mobile_phone
            request.user.birth_date = saved_profile.birth_date
            name_parts = saved_profile.full_name.split()
            if len(name_parts) >= 2:
                request.user.last_name = name_parts[0]
                request.user.first_name = ' '.join(name_parts[1:])
            request.user.save()
            
            messages.success(request, 'Анкета успешно сохранена!')
            return redirect('dashboard')
    else:
        form = ParentProfileFullForm(instance=profile)
        # Устанавливаем начальные значения для чекбоксов
        form.initial['address_same_as_registration'] = profile.address_same_as_registration
        form.initial['not_working'] = profile.not_working
    
    # Подготавливаем остальной контекст
    nationalities = [
        "Русский", "Татарский", "Украинский", "Белорусский", "Казахский",
        "Армянский", "Азербайджанский", "Грузинский", "Молдавский", "Узбекский",
        "Таджикский", "Киргизский", "Туркменский", "Чеченский", "Осетинский",
        "Еврейский", "Немецкий", "Французский", "Английский", "Итальянский",
        "Испанский", "Греческий", "Китайский", "Вьетнамский", "Корейский",
        "Другой"
    ]
    
    completed_tabs = []
    if profile.full_name and profile.birth_date and profile.nationality:
        completed_tabs.append(1)
    if profile.passport_series and profile.passport_number and profile.passport_issued_by:
        completed_tabs.append(2)
    if profile.registration_address:
        completed_tabs.append(3)
    if profile.mobile_phone:
        completed_tabs.append(4)
    if profile.not_working or (profile.workplace and profile.position):
        completed_tabs.append(5)
    
    context = {
        'profile': profile,
        'form': form,
        'nationalities': json.dumps(nationalities),
        'completed_tabs': completed_tabs,
        'completed_tabs_count': len(completed_tabs),
        'total_tabs': 6,
        'is_primary_parent': profile.is_primary_parent,
        'is_initial_profile': not profile.has_completed_initial_profile,
    }
    
    return render(request, 'accounts/parent_profile_form.html', context)

