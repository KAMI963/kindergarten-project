# applications/apps.py
from django.apps import AppConfig


class ApplicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'applications'
    verbose_name = 'Заявления'

    def ready(self):
        # Импортируем сигналы только когда приложение готово
        import applications.signals
        print("✅ Applications signals loaded")