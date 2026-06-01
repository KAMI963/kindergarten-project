# children/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from applications.models import ChildApplication, ApplicationStatus
from .models import Child, Group
from accounts.models import ParentProfile


@receiver(post_save, sender=ChildApplication)
def create_child_record_on_approval(sender, instance, created, **kwargs):
    """
    Автоматически создает личное дело ребенка при утверждении заявления
    """
    if instance.status == ApplicationStatus.APPROVED and not hasattr(instance, 'child_record'):
        
        parent_profile = instance.parent
        
        age = instance.child_age
        group = None
        if age <= 3:
            group = Group.objects.filter(age_category='nursery').first()
        elif age <= 4:
            group = Group.objects.filter(age_category='junior').first()
        elif age <= 5:
            group = Group.objects.filter(age_category='middle').first()
        elif age <= 6:
            group = Group.objects.filter(age_category='senior').first()
        else:
            group = Group.objects.filter(age_category='preparatory').first()
        
        birth_certificate = ""
        if instance.birth_certificate_series and instance.birth_certificate_number:
            birth_certificate = f"{instance.birth_certificate_series} {instance.birth_certificate_number}"
        
        child = Child.objects.create(
            application=instance,
            full_name=instance.child_full_name,
            birth_date=instance.child_birth_date,
            gender=instance.child_gender,
            registration_address=instance.registration_address,
            actual_address=instance.actual_address or instance.registration_address,
            group=group,
            enrollment_date=timezone.now().date(),
            is_active=True,
            birth_certificate=birth_certificate,
            birth_certificate_issued_by=instance.birth_certificate_issued_by or '',
            birth_certificate_issue_date=instance.birth_certificate_issue_date,
            allergies=instance.allergies or '',
            chronic_diseases=instance.chronic_diseases or '',
            special_needs=instance.special_needs or '',
            blood_type=instance.blood_type or '',
        )
        
        from .models import ChildParent
        ChildParent.objects.get_or_create(
            child=child,
            parent=parent_profile,
            defaults={
                'relation': 'mother' if parent_profile.user.gender == 'female' else 'father',
                'is_primary': True
            }
        )
        
        if group:
            group.current_count = group.child_set.count()
            group.save()


@receiver(post_save, sender=ChildApplication)
def update_child_record_on_status_change(sender, instance, **kwargs):
    """
    Обновляет статус личного дела при изменении статуса заявления
    """
    if hasattr(instance, 'child_record'):
        child = instance.child_record
        if instance.status == ApplicationStatus.APPROVED:
            child.is_active = True
        elif instance.status == ApplicationStatus.REJECTED:
            child.is_active = False
        # УБИРАЕМ ОШИБОЧНУЮ СТРОКУ - ApplicationStatus.GRADUATED не существует
        # elif instance.status == ApplicationStatus.GRADUATED:
        #     child.is_active = False
        #     child.graduation_date = timezone.now().date()
        child.save()


@receiver(post_save, sender=ChildApplication)
def create_child_from_application(sender, instance, created, **kwargs):
    """Создание ребенка при одобрении заявления"""
    if instance.status == 'approved' and not hasattr(instance, 'child_record'):
        try:
            child, created = Child.objects.get_or_create(
                full_name=instance.child_full_name,
                birth_date=instance.child_birth_date,
                defaults={
                    'gender': instance.child_gender,
                    'snils': getattr(instance, 'child_snils', ''),
                    'registration_address': instance.registration_address,
                    'actual_address': instance.actual_address,
                }
            )
            instance.child_record = child
            instance.save(update_fields=['child_record'])
        except Exception as e:
            print(f"Ошибка создания ребенка: {e}")


@receiver(post_save, sender=ChildApplication)
def update_child_from_application(sender, instance, **kwargs):
    """
    Обновляет данные ребенка при изменении заявления
    """
    if hasattr(instance, 'child_record'):
        child = instance.child_record
        child.full_name = instance.child_full_name
        child.birth_date = instance.child_birth_date
        child.gender = instance.child_gender
        child.registration_address = instance.registration_address
        child.actual_address = instance.actual_address or instance.registration_address
        child.birth_certificate = f"{instance.birth_certificate_series} {instance.birth_certificate_number}" if instance.birth_certificate_series and instance.birth_certificate_number else ''
        child.birth_certificate_issued_by = instance.birth_certificate_issued_by or ''
        child.birth_certificate_issue_date = instance.birth_certificate_issue_date
        child.allergies = instance.allergies or ''
        child.chronic_diseases = instance.chronic_diseases or ''
        child.special_needs = instance.special_needs or ''
        child.blood_type = instance.blood_type or ''
        child.save()