# applications/migrations/0002_add_queue_and_documents.py
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='childapplication',
            name='benefit_points',
            field=models.IntegerField(default=0, verbose_name='Баллы льготы'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='benefit_verified',
            field=models.BooleanField(default=False, verbose_name='Льгота подтверждена'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='benefit_category',
            field=models.CharField(choices=[('none', 'Без льготы'), ('extraordinary', 'Внеочередное право'), ('priority', 'Первоочередное право'), ('preferential', 'Преимущественное право')], default='none', max_length=20, verbose_name='Категория льготы'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='benefit_document',
            field=models.FileField(blank=True, null=True, upload_to='applications/benefits/', verbose_name='Подтверждающий документ льготы'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='documents_verified',
            field=models.BooleanField(default=False, verbose_name='Документы проверены'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='foreign_documents',
            field=models.FileField(blank=True, null=True, upload_to='applications/foreign_docs/', verbose_name='Документы для иностранцев'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='guardianship_act',
            field=models.FileField(blank=True, null=True, upload_to='applications/guardianship/', verbose_name='Акт о назначении опекуна'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='health_certificate',
            field=models.FileField(blank=True, null=True, upload_to='applications/health_certificates/', verbose_name='Медицинская справка'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='last_queue_update',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Последнее обновление очереди'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='pmpk_file',
            field=models.FileField(blank=True, null=True, upload_to='applications/pmpk/', verbose_name='Заключение ПМПК'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='queue_priority',
            field=models.IntegerField(default=0, verbose_name='Приоритет очереди'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='queue_position',
            field=models.IntegerField(blank=True, null=True, verbose_name='Позиция в очереди'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='residence_proof_file',
            field=models.FileField(blank=True, null=True, upload_to='applications/residence_proof/', verbose_name='Подтверждение места жительства'),
        ),
        migrations.AddField(
            model_name='childapplication',
            name='verification_comment',
            field=models.TextField(blank=True, verbose_name='Примечание проверяющего'),
        ),
        migrations.AlterField(
            model_name='childapplication',
            name='status',
            field=models.CharField(choices=[('draft', 'Черновик'), ('pending', 'На проверке'), ('queue', 'В очереди'), ('invited', 'Приглашен на оформление'), ('processing', 'На оформлении'), ('enrolled', 'Зачислен'), ('rejected', 'Отказ'), ('deferred', 'Отложен'), ('no_show', 'Не явился'), ('withdrawn', 'Отозвана')], default='draft', max_length=20, verbose_name='Статус заявления'),
        ),
        migrations.CreateModel(
            name='QueueHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('changed_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата изменения')),
                ('old_position', models.IntegerField(blank=True, null=True, verbose_name='Старая позиция')),
                ('new_position', models.IntegerField(verbose_name='Новая позиция')),
                ('reason', models.CharField(blank=True, max_length=255, verbose_name='Причина изменения')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='queue_history', to='applications.childapplication', verbose_name='Заявление')),
            ],
            options={
                'verbose_name': 'История очереди',
                'verbose_name_plural': 'История очереди',
                'ordering': ['-changed_at'],
            },
        ),
    ]