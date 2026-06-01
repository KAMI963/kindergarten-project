import os
from pathlib import Path
from decouple import config
from celery.schedules import crontab

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ========== ОПРЕДЕЛЕНИЕ ОКРУЖЕНИЯ (RAILWAY vs LOCAL) ==========
# Определяем, запущены ли мы на Railway
IS_RAILWAY = os.environ.get('RAILWAY_ENVIRONMENT', False) or os.environ.get('RAILWAY_PUBLIC_DOMAIN', False)

# ========== НАСТРОЙКИ ДЛЯ RAILWAY (ПРОДАКШЕН) ==========
if IS_RAILWAY:
    # Security
    SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("DJANGO_SECRET_KEY must be set on Railway")
    
    DEBUG = os.environ.get('DEBUG', 'False') == 'True'
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '.railway.app,localhost,127.0.0.1').split(',')
    BASE_URL = os.environ.get('BASE_URL', 'https://your-project.up.railway.app')
    
    # ========== CSRF TRUSTED ORIGINS - ИСПРАВЛЕННЫЙ БЛОК ==========
    # Базовые адреса Railway
    railway_origins = [
        'https://kindergarten-project.up.railway.app',
        'https://kindergarten-project-production.up.railway.app',
        'http://kindergarten-project.up.railway.app',
        'http://kindergarten-project-production.up.railway.app',
    ]
    
    # Пытаемся прочитать переменную окружения
    csrf_origins_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
    if csrf_origins_env:
        # Если переменная есть, добавляем её адреса
        env_origins = [origin.strip() for origin in csrf_origins_env.split(',') if origin.strip()]
        CSRF_TRUSTED_ORIGINS = list(set(railway_origins + env_origins))
    else:
        # Если переменной нет, используем адреса Railway
        CSRF_TRUSTED_ORIGINS = railway_origins
    
    # Выводим в лог для проверки
    print(f"=== CSRF_TRUSTED_ORIGINS: {CSRF_TRUSTED_ORIGINS} ===")
    # ============================================================
    
    # Database - PostgreSQL (автоматически подставляется Railway)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('PGDATABASE'),
            'USER': os.environ.get('PGUSER'),
            'PASSWORD': os.environ.get('PGPASSWORD'),
            'HOST': os.environ.get('PGHOST'),
            'PORT': os.environ.get('PGPORT', '5432'),
        }
    }
    
    # Email settings из переменных окружения
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.mail.ru')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 465))
    EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'True') == 'True'
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False') == 'True'
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')
    
    # Celery настройки для Railway (если есть Redis)
    if os.environ.get('REDIS_URL'):
        CELERY_BROKER_URL = os.environ.get('REDIS_URL')
        CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL')
        CELERY_TASK_ALWAYS_EAGER = False
        CELERY_TASK_EAGER_PROPAGATES = False
    else:
        CELERY_TASK_ALWAYS_EAGER = True
        CELERY_TASK_EAGER_PROPAGATES = True
        CELERY_BROKER_URL = None
        CELERY_RESULT_BACKEND = None
    
    # Celery Beat периодические задачи
    CELERY_BEAT_SCHEDULE = {
        'generate-monthly-payments': {
            'task': 'payments.tasks.generate_monthly_payments',
            'schedule': crontab(0, 0, day_of_month=25),
        },
        'recalculate-pending-payments': {
            'task': 'payments.tasks.recalculate_pending_payments',
            'schedule': crontab(0, 6),
        },
        'cleanup-expired-verification-codes': {
            'task': 'accounts.tasks.cleanup_expired_verification_codes',
            'schedule': crontab(hour=3, minute=0),
        },
    }

# ========== НАСТРОЙКИ ДЛЯ ЛОКАЛЬНОЙ РАЗРАБОТКИ ==========
else:
    # Security
    SECRET_KEY = config('SECRET_KEY', default='django-insecure-key-change-in-production')
    DEBUG = config('DEBUG', default=True, cast=bool)
    ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')
    BASE_URL = config('BASE_URL', default='http://localhost:8000')
    
    # Database - локальная PostgreSQL
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='kindergarten_db'),
            'USER': config('DB_USER', default='kindergarten_user'),
            'PASSWORD': config('DB_PASSWORD', default='1240630'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }
    
    # Email настройки для локальной разработки
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.mail.ru'
    EMAIL_PORT = 465
    EMAIL_USE_SSL = True      
    EMAIL_HOST_USER = 'dou_ryabinushka_karabash@internet.ru'
    EMAIL_HOST_PASSWORD = 'KAz4tlI2dCl1fqOeYTYD'
    DEFAULT_FROM_EMAIL = 'dou_ryabinushka_karabash@internet.ru'
    
    # Celery отключен для локальной разработки
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None
    CELERY_BEAT_SCHEDULE = {}

# ========== ОБЩИЕ НАСТРОЙКИ (РАБОТАЮТ ВЕЗДЕ) ==========

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    
    # Сторонние приложения
    'crispy_forms',
    'crispy_bootstrap5',
    'django_cleanup',
    'celery',
    
    # Мои приложения
    'accounts',
    'applications',
    'children',
    'payments',
    'attendance',
    'staff',
    'staff.templatetags',
    'orders',  
    'communication',
    'nutrition',
    'lessons',
    'contracts',
    'notifications',
]

MIDDLEWARE = [
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ВАЖНО: должен быть первым!
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'accounts.middleware.AutoCreateProfileMiddleware',
]

ROOT_URLCONF = 'kindergarten_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'staff.context_processors.staff_notifications',
                'staff.context_processors.staff_sidebar_menu',
            ],
        },
    },
]

WSGI_APPLICATION = 'kindergarten_project.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise для статических файлов в продакшене
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (загружаемые пользователями файлы)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Custom User Model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Login/Logout URLs
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'
LOGIN_URL = 'home'

# Site ID for allauth
SITE_ID = 1

# Allauth settings
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_RATE_LIMITS = {
    'login_failed': (5, 300),  # 5 попыток за 300 секунд
}
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGOUT_REDIRECT_URL = 'home'
ACCOUNT_SESSION_REMEMBER = True

# Настройки для разных провайдеров email
EMAIL_CONFIGS = {
    'gmail.com': {
        'host': 'smtp.gmail.com',
        'port': 587,
        'use_tls': True,
    },
    'mail.ru': {
        'host': 'smtp.mail.ru',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
    },
    'yandex.ru': {
        'host': 'smtp.yandex.ru',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
    },
    'yandex.by': {
        'host': 'smtp.yandex.ru',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
    },
    'yandex.kz': {
        'host': 'smtp.yandex.ru',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
    },
    'rambler.ru': {
        'host': 'smtp.rambler.ru',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
    },
    'icloud.com': {
        'host': 'smtp.mail.me.com',
        'port': 587,
        'use_tls': True,
    },
    'me.com': {
        'host': 'smtp.mail.me.com',
        'port': 587,
        'use_tls': True,
    },
    'mac.com': {
        'host': 'smtp.mail.me.com',
        'port': 587,
        'use_tls': True,
    },
    'outlook.com': {
        'host': 'smtp-mail.outlook.com',
        'port': 587,
        'use_tls': True,
    },
    'hotmail.com': {
        'host': 'smtp-mail.outlook.com',
        'port': 587,
        'use_tls': True,
    },
    'live.com': {
        'host': 'smtp-mail.outlook.com',
        'port': 587,
        'use_tls': True,
    },
    'yahoo.com': {
        'host': 'smtp.mail.yahoo.com',
        'port': 465,
        'use_tls': False,
        'use_ssl': True,
    },
}

# Animate.css для анимаций
ANIMATE_CSS_VERSION = '4.1.1'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ CSRF - ПРИНУДИТЕЛЬНОЕ ДОБАВЛЕНИЕ АДРЕСОВ
# ВРЕМЕННО (только для тестирования)
CSRF_TRUSTED_ORIGINS = ['*']