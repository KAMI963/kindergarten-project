from django.utils import timezone
from accounts.models import ParentProfile, TeacherProfile, DirectorProfile

class AutoCreateProfileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Создаем профиль для авторизованных пользователей, если его нет
        if request.user.is_authenticated:
            user = request.user
            
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
            elif user.role == 'teacher' and not hasattr(user, 'teacherprofile'):
                TeacherProfile.objects.create(
                    user=user,
                    education='Не указано',
                    specialization='Не указано',
                    experience=0,
                    hire_date=timezone.now().date()
                )
            elif user.role == 'director' and not hasattr(user, 'directorprofile'):
                DirectorProfile.objects.create(
                    user=user,
                    education='Не указано',
                    management_experience=0
                )
        
        response = self.get_response(request)
        return response
