from django.db.models.signals import post_save
from django.dispatch import receiver
from children.models import Child
from .models import ChildAccount


@receiver(post_save, sender=Child)
def create_child_account(sender, instance, created, **kwargs):
    """При создании ребенка автоматически создаем лицевой счет"""
    if created:
        ChildAccount.objects.get_or_create(child=instance)


@receiver(post_save, sender=Child)
def save_child_account(sender, instance, **kwargs):
    """Сохраняем лицевой счет"""
    if hasattr(instance, 'account'):
        instance.account.save()
    else:
        ChildAccount.objects.create(child=instance)