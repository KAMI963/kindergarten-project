# staff/context_processors.py
from .models import Employee, LeaveRequest, MedicalExamination, CriminalRecordCheck
from django.utils import timezone
from datetime import date, timedelta

def staff_notifications(request):
    """
    Контекстный процессор для уведомлений в шаблонах
    Доступен во всех шаблонах как {{ staff_notifications }}
    """
    notifications = {
        'pending_leave_requests': 0,
        'expiring_medical': 0,
        'expiring_criminal': 0,
        'total': 0
    }
    
    if request.user.is_authenticated:
        # Для заведующей показываем все уведомления
        if hasattr(request.user, 'role') and request.user.role == 'director':
            # Заявления на отпуск на рассмотрении
            notifications['pending_leave_requests'] = LeaveRequest.objects.filter(
                status='pending'
            ).count()
            
            # Истекающие медосмотры (30 дней)
            thirty_days_later = date.today() + timedelta(days=30)
            notifications['expiring_medical'] = MedicalExamination.objects.filter(
                valid_until__lte=thirty_days_later,
                valid_until__gte=date.today()
            ).count()
            
            # Истекающие справки о несудимости
            notifications['expiring_criminal'] = CriminalRecordCheck.objects.filter(
                valid_until__lte=thirty_days_later,
                valid_until__gte=date.today()
            ).count()
            
            # Общее количество
            notifications['total'] = (
                notifications['pending_leave_requests'] + 
                notifications['expiring_medical'] + 
                notifications['expiring_criminal']
            )
        
        # Для сотрудника показываем его личные уведомления
        elif hasattr(request.user, 'employee_profile'):
            employee = request.user.employee_profile
            
            # Личные истекающие документы
            thirty_days_later = date.today() + timedelta(days=30)
            
            # Медосмотры сотрудника
            notifications['expiring_medical'] = MedicalExamination.objects.filter(
                employee=employee,
                valid_until__lte=thirty_days_later,
                valid_until__gte=date.today()
            ).count()
            
            # Справки сотрудника
            notifications['expiring_criminal'] = CriminalRecordCheck.objects.filter(
                employee=employee,
                valid_until__lte=thirty_days_later,
                valid_until__gte=date.today()
            ).count()
            
            notifications['total'] = (
                notifications['expiring_medical'] + 
                notifications['expiring_criminal']
            )
    
    return {'staff_notifications': notifications}


def staff_sidebar_menu(request):
    """
    Контекстный процессор для меню сотрудников
    Доступен во всех шаблонах как {{ staff_menu }}
    """
    menu = {
        'main': [
            {'title': 'Панель управления', 'url': 'staff:dashboard', 'icon': 'tachometer-alt'},
            {'title': 'Сотрудники', 'url': 'staff:employee_list', 'icon': 'users'},
            {'title': 'Штатное расписание', 'url': 'staff:staffing_table', 'icon': 'sitemap'},
        ],
        'accounting': [
            {'title': 'Виды начислений', 'url': 'staff:payroll_type_list', 'icon': 'calculator'},
            {'title': 'Графики работы', 'url': 'staff:schedule_list', 'icon': 'clock'},
            {'title': 'Табель учета', 'url': 'staff:timesheet_list', 'icon': 'calendar-check'},
            {'title': 'Расчет зарплаты', 'url': 'staff:salary_dashboard', 'icon': 'money-bill-wave'},
        ],
        'documents': [
            {'title': 'График отпусков', 'url': 'staff:leave_dashboard', 'icon': 'umbrella-beach'},
            {'title': 'Дисциплина', 'url': 'staff:discipline_dashboard', 'icon': 'gavel'},
            {'title': 'Диспансеризация', 'url': 'staff:dispensary_list', 'icon': 'stethoscope'},
            {'title': 'Напоминания', 'url': 'staff:document_reminders', 'icon': 'bell'},
        ],
        'reports': [
            {'title': 'Отчеты по сотрудникам', 'url': '#', 'icon': 'chart-bar'},
            {'title': 'Экспорт данных', 'url': '#', 'icon': 'file-excel'},
        ]
    }
    
    # Если пользователь не авторизован или не директор, показываем ограниченное меню
    if not request.user.is_authenticated:
        menu = {}
    elif not (hasattr(request.user, 'role') and request.user.role == 'director'):
        # Для обычных сотрудников
        menu = {
            'main': [
                {'title': 'Мой профиль', 'url': 'staff:employee_profile', 'icon': 'user'},
                {'title': 'Мои документы', 'url': '#', 'icon': 'folder'},
            ],
            'requests': [
                {'title': 'Заявление на отпуск', 'url': 'staff:leave_request_create', 'icon': 'calendar-plus'},
                {'title': 'Мои отпуска', 'url': 'staff:leave_schedule_list', 'icon': 'umbrella-beach'},
            ]
        }
    
    return {'staff_menu': menu}
