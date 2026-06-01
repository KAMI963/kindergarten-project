# applications/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import ChildApplication, ApplicationStatus, recalc_category_queue_positions
from datetime import date
from .queue_logic import auto_invite_from_queue
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ChildApplication)
def calculate_age_category_on_save(sender, instance, **kwargs):
    """Автоматический расчёт возрастной категории при сохранении"""
    if instance.child_birth_date and not instance.age_category:
        instance.age_category = instance.calculate_age_category()
    
    if instance.status == ApplicationStatus.QUEUE:
        instance.queue_priority = instance.calculate_priority_score()


@receiver(post_save, sender=ChildApplication)
def auto_invite_on_status_change(sender, instance, created, **kwargs):
    """Автоматическое приглашение при изменении статуса заявления"""
    if instance.status in [ApplicationStatus.ENROLLED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN]:
        if instance.age_category:
            auto_invite_from_queue(instance.age_category)
    
    if created and instance.status == ApplicationStatus.QUEUE:
        auto_invite_from_queue(instance.age_category)


@receiver(post_save, sender=ChildApplication)
def update_queue_on_status_change(sender, instance, created, **kwargs):
    """Обновление очереди при изменении статуса"""
    update_fields = kwargs.get('update_fields')
    
    if update_fields and set(update_fields) <= {'queue_priority', 'queue_position', 'last_queue_update', 'sibling_application'}:
        return
    
    if instance.status == ApplicationStatus.QUEUE and instance.age_category:
        priority = instance.calculate_priority_score()
        ChildApplication.objects.filter(pk=instance.pk).update(queue_priority=priority)
        recalc_category_queue_positions(instance.age_category)
    
    elif instance.status in [
        ApplicationStatus.ENROLLED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.RETURNED,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.EXPIRED,
    ]:
        if instance.age_category:
            recalc_category_queue_positions(instance.age_category)


@receiver(post_save, sender=ChildApplication)
def check_sibling_priority(sender, instance, created, **kwargs):
    """Проверка наличия брата/сестры"""
    update_fields = kwargs.get('update_fields')
    if update_fields:
        return
    
    if created and instance.sibling_in_kindergarten:
        sibling_apps = ChildApplication.objects.filter(
            parent=instance.parent,
            status__in=[ApplicationStatus.ENROLLED, ApplicationStatus.QUEUE]
        ).exclude(id=instance.id)
        
        if sibling_apps.exists():
            ChildApplication.objects.filter(pk=instance.pk).update(
                sibling_application=sibling_apps.first()
            )


# ==================== СОЗДАНИЕ ЛИЧНОГО ДЕЛА РЕБЕНКА ====================

@receiver(post_save, sender=ChildApplication)
def create_or_update_child_record(sender, instance, created, **kwargs):
    """
    СОЗДАЕТ ЛИЧНОЕ ДЕЛО РЕБЕНКА
    Срабатывает при статусах: ENROLLED, PROCESSING, INVITED, QUEUE, APPROVED
    """
    from children.models import Child, ChildParent, PersonalFile, Group
    from django.core.files.base import ContentFile
    import os
    from datetime import date
    
    # ДОБАВЛЯЕМ APPROVED В СПИСОК СТАТУСОВ
    target_statuses = [
        ApplicationStatus.ENROLLED, 
        ApplicationStatus.PROCESSING, 
        ApplicationStatus.INVITED, 
        ApplicationStatus.QUEUE,
        ApplicationStatus.APPROVED  # <-- ДОБАВЛЯЕМ APPROVED
    ]
    
    # Также проверяем строковые значения на всякий случай
    status_str = instance.status if isinstance(instance.status, str) else str(instance.status)
    
    if instance.status in target_statuses or status_str in ['approved', 'enrolled', 'processing', 'invited', 'queue']:
        
        print(f"\n{'='*60}")
        print(f"🔔 СОЗДАНИЕ/ОБНОВЛЕНИЕ ЛИЧНОГО ДЕЛА")
        print(f"   Заявление ID: {instance.id}")
        print(f"   Статус: {instance.status} ({status_str})")
        print(f"   Ребенок: {instance.child_full_name}")
        print(f"{'='*60}")
        
        # Ищем существующего ребенка
        child = Child.objects.filter(
            full_name=instance.child_full_name,
            birth_date=instance.child_birth_date
        ).first()
        
        if not child:
            try:
                # Формируем номер свидетельства
                birth_certificate = ""
                if instance.birth_certificate_series and instance.birth_certificate_number:
                    birth_certificate = f"{instance.birth_certificate_series} {instance.birth_certificate_number}"
                
                # Копируем фото
                child_photo = None
                if instance.child_photo:
                    try:
                        old_photo = instance.child_photo
                        old_photo.open()
                        filename = os.path.basename(old_photo.name)
                        child_photo = ContentFile(old_photo.read(), name=f'child_photos/{filename}')
                        old_photo.close()
                        print(f"   ✅ Фото скопировано")
                    except Exception as e:
                        print(f"   ⚠️ Ошибка копирования фото: {e}")
                
                # Функция копирования файлов
                def copy_file(file_field, target_folder):
                    if file_field and hasattr(file_field, 'name') and file_field.name:
                        try:
                            file_field.open()
                            filename = os.path.basename(file_field.name)
                            file_content = file_field.read()
                            file_field.close()
                            return ContentFile(file_content, name=f'{target_folder}/{filename}')
                        except Exception as e:
                            print(f"   ⚠️ Ошибка копирования файла {target_folder}: {e}")
                            return None
                    return None
                
                # Создаем ребенка
                child = Child.objects.create(
                    application=instance,
                    full_name=instance.child_full_name,
                    birth_date=instance.child_birth_date,
                    gender=instance.child_gender,
                    snils=instance.child_snils or '',
                    registration_address=instance.registration_address,
                    actual_address=instance.actual_address or instance.registration_address,
                    birth_certificate=birth_certificate,
                    birth_certificate_issued_by=instance.birth_certificate_issued_by or '',
                    birth_certificate_issue_date=instance.birth_certificate_issue_date,
                    allergies=instance.allergies or '',
                    chronic_diseases=instance.chronic_diseases or '',
                    special_needs=instance.special_needs or '',
                    blood_type=instance.blood_type or '',
                    has_vaccinations=instance.has_vaccinations or False,
                    photo=child_photo,
                    birth_certificate_file=copy_file(instance.birth_certificate_file, 'birth_certificates'),
                    snils_file=copy_file(instance.child_snils_file, 'snils'),
                    insurance_policy_file=copy_file(instance.insurance_policy_file, 'insurance'),
                    vaccination_certificate_file=copy_file(instance.vaccination_certificate_file, 'vaccinations'),
                    medical_card_file=copy_file(instance.medical_card, 'medical_cards'),
                    registration_certificate=copy_file(instance.residence_certificate, 'registration'),
                    is_active=True,
                    enrollment_date=date.today() if instance.status == ApplicationStatus.ENROLLED else None
                )
                
                print(f"   ✅ СОЗДАН РЕБЕНОК {child.full_name} (ID: {child.id})")
                
                # Связь с родителем
                relation = 'mother' if instance.parent.user.gender == 'female' else 'father'
                if not instance.parent.user.gender:
                    relation = 'parent'
                    
                ChildParent.objects.get_or_create(
                    child=child,
                    parent=instance.parent,
                    defaults={
                        'relation': relation,
                        'is_primary': True
                    }
                )
                print(f"   ✅ Создана связь с родителем ({relation})")
                
                # ЛИЧНОЕ ДЕЛО - СОЗДАЕМ ОБЯЗАТЕЛЬНО
                personal_file, created_pf = PersonalFile.objects.get_or_create(
                    child=child,
                    defaults={
                        'status': 'active',
                        'opening_date': date.today()
                    }
                )
                if created_pf:
                    print(f"   ✅ СОЗДАНО ЛИЧНОЕ ДЕЛО для {child.full_name} (№{personal_file.file_number})")
                else:
                    print(f"   ℹ️ Личное дело уже существует для {child.full_name}")
                
                # Если статус ENROLLED - назначаем группу
                if instance.status == ApplicationStatus.ENROLLED and instance.enrolled_group:
                    group = Group.objects.filter(name=instance.enrolled_group).first()
                    if group:
                        child.group = group
                        child.save()
                        print(f"   ✅ Ребенок зачислен в группу {group.name}")
                
            except Exception as e:
                print(f"   ❌ ОШИБКА ПРИ СОЗДАНИИ РЕБЕНКА: {e}")
                import traceback
                traceback.print_exc()
        else:
            # Обновляем существующего ребенка
            print(f"   ℹ️ Найден существующий ребенок {child.full_name} (ID: {child.id})")
            
            # Обновляем данные
            updated = False
            
            if child.has_vaccinations != (instance.has_vaccinations or False):
                child.has_vaccinations = instance.has_vaccinations or False
                updated = True
            
            if child.allergies != (instance.allergies or ''):
                child.allergies = instance.allergies or ''
                updated = True
            
            if child.chronic_diseases != (instance.chronic_diseases or ''):
                child.chronic_diseases = instance.chronic_diseases or ''
                updated = True
            
            if child.special_needs != (instance.special_needs or ''):
                child.special_needs = instance.special_needs or ''
                updated = True
            
            if child.blood_type != (instance.blood_type or ''):
                child.blood_type = instance.blood_type or ''
                updated = True
            
            if updated:
                child.save()
                print(f"   ✅ Обновлены данные ребенка {child.full_name}")
            
            # Проверяем наличие личного дела
            personal_file, created_pf = PersonalFile.objects.get_or_create(
                child=child,
                defaults={
                    'status': 'active',
                    'opening_date': date.today()
                }
            )
            if created_pf:
                print(f"   ✅ СОЗДАНО ЛИЧНОЕ ДЕЛО для существующего ребенка {child.full_name}")
            else:
                print(f"   ℹ️ Личное дело уже есть у {child.full_name}")
            
            # Если заявление переходит в статус ENROLLED - обновляем группу
            if instance.status == ApplicationStatus.ENROLLED and instance.enrolled_group:
                group = Group.objects.filter(name=instance.enrolled_group).first()
                if group and child.group != group:
                    child.group = group
                    child.enrollment_date = date.today()
                    child.save()
                    print(f"   ✅ Ребенок зачислен в группу {group.name}")


@receiver(post_save, sender=ChildApplication)
def update_child_on_application_change(sender, instance, **kwargs):
    """Обновляет данные ребенка при изменении заявления"""
    from children.models import Child
    
    # Ищем ребенка по ФИО и дате рождения
    child = Child.objects.filter(
        full_name=instance.child_full_name,
        birth_date=instance.child_birth_date
    ).first()
    
    if child:
        needs_update = False
        
        if child.full_name != instance.child_full_name:
            child.full_name = instance.child_full_name
            needs_update = True
        
        if child.birth_date != instance.child_birth_date:
            child.birth_date = instance.child_birth_date
            needs_update = True
        
        if child.gender != instance.child_gender:
            child.gender = instance.child_gender
            needs_update = True
        
        if child.registration_address != instance.registration_address:
            child.registration_address = instance.registration_address
            needs_update = True
        
        if child.actual_address != (instance.actual_address or instance.registration_address):
            child.actual_address = instance.actual_address or instance.registration_address
            needs_update = True
        
        if needs_update:
            child.save()
            print(f"   ✅ Обновлены данные ребенка {child.full_name}")


@receiver(post_save, sender=ChildApplication)
def auto_assign_group_on_enrollment(sender, instance, **kwargs):
    """Автоматически назначает группу ребенку при зачислении"""
    from children.models import Group, Child
    
    if instance.status == ApplicationStatus.ENROLLED and instance.enrolled_group:
        
        # Ищем ребенка
        child = Child.objects.filter(
            full_name=instance.child_full_name,
            birth_date=instance.child_birth_date
        ).first()
        
        if child:
            group = Group.objects.filter(name=instance.enrolled_group).first()
            if group and child.group != group:
                child.group = group
                child.enrollment_date = date.today()
                child.save()
                print(f"   ✅ Ребенок {child.full_name} зачислен в группу {group.name}")


# ==================== АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ДОГОВОРА ====================

@receiver(post_save, sender=ChildApplication)
def auto_create_contract_on_approval(sender, instance, created, **kwargs):
    """
    АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ДОГОВОРА ПРИ ОДОБРЕНИИ ЗАЯВЛЕНИЯ
    Срабатывает когда статус заявления меняется на APPROVED или QUEUE
    """
    print(f"\n{'='*60}")
    print(f"🔔 СИГНАЛ: auto_create_contract_on_approval")
    print(f"   Заявление ID: {instance.id}")
    print(f"   Статус: {instance.status}")
    print(f"{'='*60}")
    
    # Проверяем статус - договор создаем при APPROVED или QUEUE
    if instance.status not in ['approved', 'queue']:
        print(f"   ⏭️ Статус {instance.status} не подходит (нужен 'approved' или 'queue')")
        return
    
    try:
        from contracts.models import EducationContract
        from payments.models import Tariff
        from contracts.services import ContractWordGenerator
        from django.core.files.base import ContentFile
        from notifications.models import Notification
        from accounts.models import CustomUser
        
        # Проверяем, нет ли уже договора
        existing = EducationContract.objects.filter(application=instance).first()
        if existing:
            print(f"   ℹ️ Договор уже существует: {existing.contract_number}")
            return
        
        print(f"   ✅ Начинаем создание договора...")
        
        # Получаем возраст ребенка
        child_age = instance.get_age()
        print(f"   Возраст ребенка: {child_age} лет")
        
        # Определяем категорию по возрасту
        if child_age < 3:
            age_category = 'nursery'
            print(f"   Категория: ясельная (nursery)")
        else:
            age_category = 'kindergarten'
            print(f"   Категория: садовая (kindergarten)")
        
        current_year = date.today().year
        print(f"   Текущий год: {current_year}")
        
        # Получаем тариф
        tariff = Tariff.objects.filter(age_category=age_category, year=current_year).first()
        
        if tariff:
            content_amount = float(tariff.content_amount)
            food_amount = float(tariff.food_amount)
            total_amount = content_amount + food_amount
            print(f"   ✅ Тариф найден: содержание={content_amount}, питание={food_amount}, итого={total_amount}")
        else:
            # Если тарифа нет на текущий год, пробуем найти без года
            tariff = Tariff.objects.filter(age_category=age_category).first()
            if tariff:
                content_amount = float(tariff.content_amount)
                food_amount = float(tariff.food_amount)
                total_amount = content_amount + food_amount
                print(f"   ⚠️ Тариф найден без учета года: содержание={content_amount}, питание={food_amount}")
            else:
                # Значения по умолчанию
                content_amount = 1684.00
                food_amount = 2503.00
                total_amount = content_amount + food_amount
                print(f"   ⚠️ Тариф не найден, используются значения по умолчанию: {total_amount}")
        
        # Определяем группу по возрасту
        if child_age < 2:
            group_name = "Первая младшая группа (1-2 года)"
        elif child_age < 3:
            group_name = "Вторая младшая группа (2-3 года)"
        elif child_age < 4:
            group_name = "Младшая группа (3-4 года)"
        elif child_age < 5:
            group_name = "Средняя группа (4-5 лет)"
        elif child_age < 6:
            group_name = "Старшая группа (5-6 лет)"
        else:
            group_name = "Подготовительная группа (6-7 лет)"
        
        print(f"   Группа: {group_name}")
        
        # Создаем договор
        contract = EducationContract(
            application=instance,
            parent=instance.parent,
            child_full_name=instance.child_full_name,
            child_birth_date=instance.child_birth_date,
            group_name=group_name,
            enrollment_date=date.today(),
            study_period=5,
            stay_regimen='пятидневная неделя (понедельник – пятница), 12 часов (с 6.00 до 18.00)',
            parent_fee=total_amount,
            subscription_fee=content_amount,
            food_fee=food_amount,
            basis_documents=f"На основании заявления родителей, свидетельства о рождении, медицинской карты",
            educational_program='Основная общеобразовательная программа дошкольного образования',
            status='draft',
            is_active=True
        )
        contract.save()
        
        print(f"   ✅ ДОГОВОР СОЗДАН! Номер: {contract.contract_number}")
        
        # Генерируем Word-документ
        try:
            generator = ContractWordGenerator(contract)
            document_buffer = generator.generate()
            filename = f"Договор_{contract.contract_number}_{contract.child_full_name}.docx".replace(' ', '_')
            contract.generated_contract.save(filename, ContentFile(document_buffer.getvalue()))
            contract.save()
            print(f"   ✅ Документ сгенерирован и сохранен")
        except Exception as e:
            print(f"   ⚠️ Ошибка генерации документа: {e}")
        
        # Отправка уведомления родителю
        try:
            Notification.objects.create(
                user=instance.parent.user,
                title="📄 Создан договор об образовании",
                message=f"Для вашего ребенка {instance.child_full_name} создан договор №{contract.contract_number}. Пожалуйста, ознакомьтесь и подпишите его в личном кабинете.",
                notification_type='enrollment',
                link=f"/contracts/{contract.pk}/"
            )
            print(f"   ✅ Уведомление отправлено родителю {instance.parent.user.email}")
        except Exception as e:
            print(f"   ⚠️ Ошибка отправки уведомления родителю: {e}")
        
        # Отправка уведомления заведующей
        try:
            director = CustomUser.objects.filter(role='director').first()
            if director:
                Notification.objects.create(
                    user=director,
                    title="📄 Создан новый договор",
                    message=f"Автоматически создан договор №{contract.contract_number} для ребенка {instance.child_full_name}",
                    notification_type='enrollment',
                    link=f"/contracts/{contract.pk}/"
                )
                print(f"   ✅ Уведомление отправлено заведующей")
        except Exception as e:
            print(f"   ⚠️ Ошибка отправки уведомления заведующей: {e}")
        
    except Exception as e:
        print(f"   ❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


@receiver(post_save, sender=ChildApplication)
def auto_create_contract_on_enrolled(sender, instance, **kwargs):
    """ДОПОЛНИТЕЛЬНЫЙ СИГНАЛ: создает договор при изменении статуса на ENROLLED"""
    if instance.status == ApplicationStatus.ENROLLED:
        print(f"\n🔔 ДОПОЛНИТЕЛЬНЫЙ СИГНАЛ: создание договора при зачислении")
        
        try:
            from contracts.models import EducationContract
            
            # Проверяем, нет ли уже договора
            existing = EducationContract.objects.filter(application=instance).first()
            if existing:
                print(f"   ℹ️ Договор уже существует: {existing.contract_number}")
                return
            
            # Вызываем основную функцию создания договора
            auto_create_contract_on_approval(sender, instance, created=False, **kwargs)
            
        except Exception as e:
            print(f"   ❌ Ошибка в дополнительном сигнале: {e}")