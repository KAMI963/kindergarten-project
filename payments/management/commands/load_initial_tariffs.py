from django.core.management.base import BaseCommand
from payments.models import Tariff
from decimal import Decimal

class Command(BaseCommand):
    help = 'Загрузка начальных тарифов'

    def handle(self, *args, **options):
        tariffs_data = [
            # 2024 год
            {
                'age_category': 'nursery',
                'family_type': 'regular',
                'year': 2024,
                'total_amount': Decimal('3603.00'),
                'content_amount': Decimal('1289.00'),
                'food_amount': Decimal('2314.00')
            },
            {
                'age_category': 'nursery',
                'family_type': 'multi_child',
                'year': 2024,
                'total_amount': Decimal('1802.00'),
                'content_amount': Decimal('645.00'),
                'food_amount': Decimal('1157.00')
            },
            {
                'age_category': 'kindergarten',
                'family_type': 'regular',
                'year': 2024,
                'total_amount': Decimal('3881.00'),
                'content_amount': Decimal('966.00'),
                'food_amount': Decimal('2915.00')
            },
            {
                'age_category': 'kindergarten',
                'family_type': 'multi_child',
                'year': 2024,
                'total_amount': Decimal('1941.00'),
                'content_amount': Decimal('483.00'),
                'food_amount': Decimal('1458.00')
            },
            # 2025 год
            {
                'age_category': 'nursery',
                'family_type': 'regular',
                'year': 2025,
                'total_amount': Decimal('3902.00'),
                'content_amount': Decimal('1495.00'),
                'food_amount': Decimal('2407.00')
            },
            {
                'age_category': 'nursery',
                'family_type': 'multi_child',
                'year': 2025,
                'total_amount': Decimal('1951.00'),
                'content_amount': Decimal('747.00'),
                'food_amount': Decimal('1204.00')
            },
            {
                'age_category': 'kindergarten',
                'family_type': 'regular',
                'year': 2025,
                'total_amount': Decimal('4203.00'),
                'content_amount': Decimal('1171.00'),
                'food_amount': Decimal('3032.00')
            },
            {
                'age_category': 'kindergarten',
                'family_type': 'multi_child',
                'year': 2025,
                'total_amount': Decimal('2102.00'),
                'content_amount': Decimal('586.00'),
                'food_amount': Decimal('1516.00')
            },
        ]

        created_count = 0
        updated_count = 0

        for tariff_data in tariffs_data:
            tariff, created = Tariff.objects.update_or_create(
                age_category=tariff_data['age_category'],
                family_type=tariff_data['family_type'],
                year=tariff_data['year'],
                defaults={
                    'total_amount': tariff_data['total_amount'],
                    'content_amount': tariff_data['content_amount'],
                    'food_amount': tariff_data['food_amount']
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Создан тариф: {tariff}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Обновлен тариф: {tariff}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Успешно создано: {created_count}, обновлено: {updated_count} тарифов')
        )
