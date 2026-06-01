# contracts/debug.py
import datetime
import os
import sys
from django.conf import settings

def debug_log(message):
    """Запись отладочной информации в файл с принудительным сбросом"""
    log_path = os.path.join(settings.BASE_DIR, 'contract_debug.log')
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Пытаемся записать в файл
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f'[{timestamp}] {message}\n')
            f.flush()
            os.fsync(f.fileno())
    except:
        pass
    
    # Также пробуем записать в консоль
    try:
        print(f"DEBUG: {message}", flush=True)
        sys.stdout.flush()
    except:
        pass
