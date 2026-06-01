import traceback
import sys
import os

print("=== ЗАПУСК ДИАГНОСТИКИ ===")
print(f"Python path: {sys.path}")
print(f"Current directory: {os.getcwd()}")
print(f"Files in directory: {os.listdir('.')}")

try:
    print("Пытаемся импортировать django...")
    import django
    print(f"Django version: {django.__version__}")
    
    print("Настраиваем Django...")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kindergarten_project.settings')
    django.setup()
    
    print("Пытаемся проверить соединение с БД...")
    from django.db import connections
    from django.db.utils import OperationalError
    
    try:
        connections['default'].ensure_connection()
        print("✅ Подключение к базе данных УСПЕШНО!")
    except OperationalError as e:
        print(f"❌ Ошибка подключения к БД: {e}")
    
    print("Проверяем миграции...")
    from django.core.management import call_command
    call_command('check')
    print("✅ Проверка пройдена!")
    
except Exception as e:
    print(f"❌ ОШИБКА: {e}")
    traceback.print_exc()