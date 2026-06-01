from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import ParentProfile, TeacherProfile, DirectorProfile
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Создает отсутствующие профили для существующих пользователей'

    def handle(self, *args, **options):
        users = User.objects.all()
        
        for user in users:
            if user.role == 'parent' and not hasattr(user, 'parentprofile'):
                ParentProfile.objects.create(
                    user=user,
                    passport_series='0000',
                    passport_number='000000',
                    passport_issued_by='Не указано',
                    passport_issue_date=timezone.now().date(),
                    registration_address='Не указан',
                    actual_address='Не указан'
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Создан ParentProfile для {user.username}')
                )
            elif user.role == 'teacher' and not hasattr(user, 'teacherprofile'):
                TeacherProfile.objects.create(
                    user=user,
                    education='Не указано',
                    specialization='Не указано',
                    experience=0,
                    hire_date=timezone.now().date()
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Создан TeacherProfile для {user.username}')
                )
            elif user.role == 'director' and not hasattr(user, 'directorprofile'):
                DirectorProfile.objects.create(
                    user=user,
                    education='Не указано',
                    management_experience=0
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Создан DirectorProfile для {user.username}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Все отсутствующие профили созданы')
        )
