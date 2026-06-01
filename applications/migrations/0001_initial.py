# applications/migrations/0001_initial.py
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChildApplication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('application_number', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('child_full_name', models.CharField(max_length=200, verbose_name='ФИО ребенка')),
                ('child_birth_date', models.DateField(verbose_name='Дата рождения ребенка')),
                ('child_gender', models.CharField(choices=[('M', 'Мальчик'), ('F', 'Девочка')], max_length=1, verbose_name='Пол ребенка')),
                ('birth_certificate_series', models.CharField(blank=True, max_length=10, verbose_name='Серия свидетельства')),
                ('birth_certificate_number', models.CharField(blank=True, max_length=20, verbose_name='Номер свидетельства')),
                ('birth_certificate_issue_date', models.DateField(blank=True, null=True, verbose_name='Дата выдачи свидетельства')),
                ('birth_certificate_issued_by', models.CharField(blank=True, max_length=200, verbose_name='Кем выдано свидетельство')),
                ('registration_address', models.TextField(verbose_name='Адрес регистрации')),
                ('actual_address', models.TextField(verbose_name='Фактический адрес проживания')),
                ('phone_number', models.CharField(blank=True, max_length=20, verbose_name='Контактный телефон')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Электронная почта')),
                ('mother_full_name', models.CharField(blank=True, max_length=200, verbose_name='ФИО матери')),
                ('mother_phone', models.CharField(blank=True, max_length=20, verbose_name='Телефон матери')),
                ('father_full_name', models.CharField(blank=True, max_length=200, verbose_name='ФИО отца')),
                ('father_phone', models.CharField(blank=True, max_length=20, verbose_name='Телефон отца')),
                ('legal_representative', models.TextField(blank=True, verbose_name='Данные законного представителя')),
                ('has_vaccinations', models.BooleanField(default=False, verbose_name='Наличие прививок')),
                ('chronic_diseases', models.TextField(blank=True, verbose_name='Хронические заболевания')),
                ('medical_notes', models.TextField(blank=True, verbose_name='Медицинские примечания')),
                ('blood_type', models.CharField(blank=True, max_length=5, verbose_name='Группа крови')),
                ('allergies', models.TextField(blank=True, verbose_name='Аллергии')),
                ('special_needs', models.TextField(blank=True, verbose_name='Особые потребности')),
                ('preferred_group', models.CharField(blank=True, max_length=100, verbose_name='Предпочтительная группа')),
                ('enrollment_date', models.DateField(blank=True, null=True, verbose_name='Желаемая дата зачисления')),
                ('additional_info', models.TextField(blank=True, verbose_name='Дополнительная информация')),
                ('birth_certificate_file', models.FileField(upload_to='applications/birth_certificates/', verbose_name='Копия свидетельства о рождении')),
                ('medical_card', models.FileField(upload_to='documents/medical_cards/', verbose_name='Медицинская карта')),
                ('vaccination_certificate_file', models.FileField(blank=True, null=True, upload_to='applications/vaccinations/', verbose_name='Копия прививочного сертификата')),
                ('parent_passport_file', models.FileField(blank=True, null=True, upload_to='applications/passports/', verbose_name='Копия паспорта родителя')),
                ('additional_documents', models.FileField(blank=True, null=True, upload_to='documents/additional/', verbose_name='Дополнительные документы')),
                ('priority', models.CharField(choices=[('standard', 'Стандартный'), ('district', 'Районный'), ('benefit', 'Льготный'), ('staff', 'Сотрудник ДОУ')], default='standard', max_length=10, verbose_name='Приоритет')),
                ('status', models.CharField(choices=[('pending', 'На рассмотрении'), ('approved', 'Одобрено'), ('rejected', 'Отклонено'), ('needs_correction', 'Требует корректировки'), ('enrolled', 'Зачислен'), ('graduated', 'Выпущен')], default='pending', max_length=20, verbose_name='Статус заявления')),
                ('director_notes', models.TextField(blank=True, verbose_name='Заметки заведующей')),
                ('rejection_reason', models.TextField(blank=True, verbose_name='Причина отклонения')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('submission_date', models.DateTimeField(auto_now_add=True, verbose_name='Дата подачи')),
                ('data_processing_consent', models.BooleanField(default=False, verbose_name='Согласие на обработку персональных данных')),
                ('rules_acquainted', models.BooleanField(default=False, verbose_name='Ознакомление с правилами')),
                ('medical_examination_consent', models.BooleanField(default=False, verbose_name='Согласие на медицинский осмотр')),
                ('photo_video_consent', models.BooleanField(default=False, verbose_name='Согласие на фото/видеосъемку')),
                ('generated_application', models.FileField(blank=True, null=True, upload_to='applications/generated/', verbose_name='Сгенерированное заявление')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='accounts.parentprofile')),
            ],
            options={
                'verbose_name': 'Заявление',
                'verbose_name_plural': 'Заявления',
                'ordering': ['-created_at'],
            },
        ),
    ]