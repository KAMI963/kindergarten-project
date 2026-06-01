from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import EmailVerificationCode, PasswordResetCode, CustomUser
import random
import string
import logging

logger = logging.getLogger(__name__)

def generate_verification_code():
    """Генерирует 6-значный код подтверждения"""
    return ''.join(random.choices(string.digits, k=6))

def get_email_config(email):
    """Определяет конфигурацию SMTP в зависимости от домена email"""
    domain = email.split('@')[1].lower()
    return settings.EMAIL_CONFIGS.get(domain, {
        'host': settings.EMAIL_HOST,
        'port': settings.EMAIL_PORT,
        'use_tls': settings.EMAIL_USE_TLS,
    })

@shared_task
def send_verification_code_email(user_id, email):
    """Отправляет код подтверждения на email"""
    import random
    import string
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.conf import settings
    from django.utils import timezone
    from .models import EmailVerificationCode, CustomUser
    
    print(f"\n{'='*50}")
    print(f"📧 ОТПРАВКА КОДА ПОДТВЕРЖДЕНИЯ")
    print(f"📧 Кому: {email}")
    print(f"📧 User ID: {user_id}")
    print(f"{'='*50}\n")
    
    try:
        # Деактивируем старые коды
        old_codes = EmailVerificationCode.objects.filter(
            user_id=user_id,
            is_used=False
        )
        old_count = old_codes.count()
        old_codes.update(is_used=True)
        print(f"✅ Деактивировано старых кодов: {old_count}")
        
        # Генерируем новый код
        code = ''.join(random.choices(string.digits, k=6))
        print(f"✅ Сгенерирован код: {code}")
        
        # Создаем запись в БД
        verification_code = EmailVerificationCode.objects.create(
            user_id=user_id,
            code=code
        )
        print(f"✅ Код сохранен в БД, истекает: {verification_code.expires_at}")
        
        # Получаем пользователя
        user = CustomUser.objects.get(id=user_id)
        
        # Контекст для шаблона
        context = {
            'code': code,
            'user': user,
            'expires_at': verification_code.expires_at,
        }
        
        # Рендерим HTML и текстовую версию
        html_message = render_to_string('accounts/emails/verification_code.html', context)
        plain_message = strip_tags(html_message)
        
        # Отправляем email
        send_mail(
            subject='Код подтверждения регистрации',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        
        print(f"✅ Код подтверждения успешно отправлен на {email}")
        return True
        
    except CustomUser.DoesNotExist:
        print(f"❌ Пользователь с id {user_id} не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка отправки кода: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def send_welcome_email(user_id):
    """Отправляет приветственное письмо после успешной регистрации"""
    import logging
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.conf import settings
    from .models import CustomUser
    
    logger = logging.getLogger(__name__)
    
    try:
        user = CustomUser.objects.get(id=user_id)
        
        print(f"\n{'='*50}")
        print(f"📧 ОТПРАВКА ПРИВЕТСТВЕННОГО ПИСЬМА")
        print(f"📧 Кому: {user.email}")
        print(f"{'='*50}\n")
        
        # Получаем BASE_URL из settings или используем значение по умолчанию
        base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        
        context = {
            'user': user,
            'login_url': f"{base_url}/accounts/login/",
            'site_url': base_url,
            'year': timezone.now().year,
        }
        
        # Рендерим HTML и текстовую версию
        html_message = render_to_string('accounts/emails/welcome.html', context)
        plain_message = strip_tags(html_message)
        
        # Отправляем email
        send_mail(
            subject='Добро пожаловать в детский сад "Рябинушка"!',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        print(f"✅ Приветственное письмо успешно отправлено на {user.email}")
        return True
        
    except CustomUser.DoesNotExist:
        print(f"❌ Пользователь с id {user_id} не найден")
        return False
    except Exception as e:
        print(f"❌ Ошибка отправки приветственного письма: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

@shared_task
def send_password_reset_code(user_id, email):
    """Отправляет код для сброса пароля"""
    try:
        # Деактивируем старые коды
        PasswordResetCode.objects.filter(
            user_id=user_id,
            is_used=False
        ).update(is_used=True)
        
        # Генерируем новый код
        code = generate_verification_code()
        
        # Создаем запись в БД
        reset_code = PasswordResetCode.objects.create(
            user_id=user_id,
            code=code
        )
        
        user = CustomUser.objects.get(id=user_id)
        
        context = {
            'code': code,
            'user': user,
            'expires_at': reset_code.expires_at,
        }
        
        html_message = render_to_string('accounts/emails/password_reset_code.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject='Восстановление пароля',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Password reset code sent to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset code to {email}: {str(e)}")
        return False

@shared_task
def cleanup_expired_verification_codes():
    """Очищает просроченные коды подтверждения"""
    expired_email_codes = EmailVerificationCode.objects.filter(
        expires_at__lt=timezone.now(),
        is_used=False
    )
    count_email = expired_email_codes.count()
    expired_email_codes.delete()
    
    expired_password_codes = PasswordResetCode.objects.filter(
        expires_at__lt=timezone.now(),
        is_used=False
    )
    count_password = expired_password_codes.count()
    expired_password_codes.delete()
    
    logger.info(f"Cleaned up expired verification codes: {count_email} email, {count_password} password")
    return f"Deleted {count_email} email codes and {count_password} password reset codes"
