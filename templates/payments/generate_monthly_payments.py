from django.core.management.base import BaseCommand
from django.utils import timezone
from children.models import Child
from payments.models import Payment
from datetime import datetime

class Command(BaseCommand):
    help = 'Генерация ежемесячных платежей для всех детей'

    def handle(self, *args, **options):
        now = timezone.now()
        month = now.month
        year = now.year
        
        children = Child.objects.filter(is_active=True)
        
        created_count = 0
        updated_count = 0
        
        for child in children:
            payment, created = Payment.objects.get_or_create(
                child=child,
                month=month,
                year=year,
                defaults={'amount': 0}
            )
            
            # Пересчитываем сумму
            amount = payment.calculate_amount()
            payment.save()
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Создан платеж для {child.full_name}: {amount} ₽')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Обновлен платеж для {child.full_name}: {amount} ₽')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно создано: {created_count}, обновлено: {updated_count} платежей'
            )
        )
