from celery import shared_task
from django.utils import timezone
from datetime import date
from children.models import Child
from payments.models import Payment


@shared_task
def generate_monthly_payments():
    """
    Автоматическая генерация платежей 25 числа каждого месяца
    """
    today = date.today()
    # Если сегодня 25-е число или запуск принудительный
    month = today.month
    year = today.year
    
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
        payment.calculate_amount()
        payment.save()
        
        if created:
            created_count += 1
        else:
            updated_count += 1
    
    return f"Сгенерировано/обновлено платежей: создано {created_count}, обновлено {updated_count}"


@shared_task
def check_overdue_payments():
    """
    Проверка просроченных платежей (после 15 числа)
    """
    today = date.today()
    current_month_payments = Payment.objects.filter(
        month=today.month,
        year=today.year,
        status='pending'
    )
    
    # Если прошло больше 15 дней месяца
    if today.day > 15:
        overdue_count = current_month_payments.update(status='overdue')
        return f"Отмечено просроченных платежей: {overdue_count}"
    
    return "Проверка не требуется (до 15 числа)"