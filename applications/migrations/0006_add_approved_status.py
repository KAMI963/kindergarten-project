# applications/migrations/000X_add_approved_status.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='childapplication',
            name='status',
            field=models.CharField(choices=[
                ('draft', 'Черновик'),
                ('pending', 'На проверке'),
                ('queue', 'В очереди'),
                ('approved', 'Одобрено'),  # Добавляем approved
                ('invited', 'Приглашен на оформление'),
                ('processing', 'На оформлении'),
                ('enrolled', 'Зачислен'),
                ('rejected', 'Отказ'),
                ('returned', 'Возвращено на доработку'),
                ('expired', 'Срок приглашения истек'),
                ('withdrawn', 'Отозвана')
            ], default='draft', max_length=20, verbose_name='Статус заявления'),
        ),
    ]