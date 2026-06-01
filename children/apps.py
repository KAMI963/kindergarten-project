# children/apps.py
from django.apps import AppConfig

class ChildrenConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'children'
    verbose_name = 'Дети и личные дела'
    
    def ready(self):
        import children.signals
