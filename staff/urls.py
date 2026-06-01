# staff/urls.py
from django.urls import path
from . import views
from . import views_timesheet

app_name = 'staff'

urlpatterns = [
    # Главная страница сотрудников
    path('', views.staff_dashboard, name='dashboard'),
    
    # Список сотрудников
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/create/', views.employee_create, name='employee_create'),
    path('employees/<int:employee_id>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:employee_id>/edit/', views.employee_edit, name='employee_edit'),
    path('employees/<int:employee_id>/delete/', views.employee_delete, name='employee_delete'),
    path('contracts/<int:contract_id>/word/', views.generate_contract_word, name='contract_word'),
    
    # Расчет заработной платы
    path('salary/', views.salary_dashboard, name='salary_dashboard'),
    path('salary/calculate/', views.salary_calculate, name='salary_calculate'),
    path('salary/calculations/', views.salary_calculations_list, name='salary_calculations_list'),
    path('salary/<int:calc_id>/', views.salary_detail, name='salary_detail'),
    path('salary/<int:calc_id>/payslip/', views.generate_payslip, name='generate_payslip'),
    path('salary/<int:calc_id>/approve/', views.salary_approve, name='salary_approve'),
    path('salary/payroll/', views.payroll_register, name='payroll_register'),
    
    # Личные дела
    path('employees/<int:employee_id>/personal-file/', views.personal_file_detail, name='personal_file_detail'),
    path('employees/<int:employee_id>/personal-file/edit/', views.personal_file_edit, name='personal_file_edit'),
    
    # Паспортные данные
    path('employees/<int:employee_id>/passport/', views.passport_data, name='passport_data'),
    
    # ИНН, СНИЛС
    path('employees/<int:employee_id>/inn/', views.inn_data, name='inn_data'),
    path('employees/<int:employee_id>/snils/', views.snils_data, name='snils_data'),
    
    # Образование
    path('employees/<int:employee_id>/education/', views.education_list, name='education_list'),
    path('employees/<int:employee_id>/education/add/', views.education_add, name='education_add'),
    path('education/<int:doc_id>/edit/', views.education_edit, name='education_edit'),
    path('education/<int:doc_id>/delete/', views.education_delete, name='education_delete'),
    
    # Курсы повышения квалификации
    path('employees/<int:employee_id>/courses/', views.courses_list, name='courses_list'),
    path('employees/<int:employee_id>/courses/add/', views.course_add, name='course_add'),
    path('courses/<int:course_id>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:course_id>/delete/', views.course_delete, name='course_delete'),
    
    # Аттестация
    path('employees/<int:employee_id>/attestations/', views.attestation_list, name='attestation_list'),
    path('employees/<int:employee_id>/attestations/add/', views.attestation_add, name='attestation_add'),
    path('attestations/<int:att_id>/edit/', views.attestation_edit, name='attestation_edit'),
    path('attestations/<int:att_id>/delete/', views.attestation_delete, name='attestation_delete'),
    
    # Медосмотры
    path('employees/<int:employee_id>/medical/', views.medical_examinations, name='medical_examinations'),
    path('employees/<int:employee_id>/medical/add/', views.medical_examination_add, name='medical_examination_add'),
    path('medical/<int:med_id>/edit/', views.medical_examination_edit, name='medical_examination_edit'),
    path('medical/<int:med_id>/delete/', views.medical_examination_delete, name='medical_examination_delete'),
    
    # Справки об отсутствии судимости
    path('employees/<int:employee_id>/criminal-check/', views.criminal_check_detail, name='criminal_check_detail'),
    path('employees/<int:employee_id>/criminal-check/edit/', views.criminal_check_edit, name='criminal_check_edit'),
    
    # Напоминания об истечении документов
    path('reminders/', views.document_reminders, name='document_reminders'),
    
    # Штатное расписание
    path('staffing/', views.staffing_table, name='staffing_table'),
    path('staffing/positions/', views.position_list, name='position_list'),
    path('staffing/positions/create/', views.position_create, name='position_create'),
    path('staffing/positions/<int:position_id>/edit/', views.position_edit, name='position_edit'),
    path('staffing/units/create/', views.staff_unit_create, name='staff_unit_create'),
    path('staffing/units/<int:unit_id>/edit/', views.staff_unit_edit, name='staff_unit_edit'),
    path('staffing/units/<int:unit_id>/delete/', views.staff_unit_delete, name='staff_unit_delete'),
    
    # Вакансии
    path('vacancies/', views.vacancy_list, name='vacancy_list'),
    path('vacancies/create/', views.vacancy_create, name='vacancy_create'),
    path('vacancies/<int:vacancy_id>/', views.vacancy_detail, name='vacancy_detail'),
    path('vacancies/<int:vacancy_id>/edit/', views.vacancy_edit, name='vacancy_edit'),
    path('vacancies/<int:vacancy_id>/close/', views.vacancy_close, name='vacancy_close'),
    path('vacancies/<int:vacancy_id>/candidates/add/', views.candidate_add, name='candidate_add'),
    
    # Трудовые договоры
    path('contracts/', views.contract_list, name='contract_list'),
    path('employees/<int:employee_id>/contracts/', views.employee_contracts, name='employee_contracts'),
    path('employees/<int:employee_id>/contracts/create/', views.contract_create, name='contract_create'),
    path('contracts/<int:contract_id>/', views.contract_detail, name='contract_detail'),
    path('contracts/<int:contract_id>/edit/', views.contract_edit, name='contract_edit'),
    path('contracts/<int:contract_id>/terminate/', views.contract_terminate, name='contract_terminate'),
    path('contracts/<int:contract_id>/agreements/add/', views.agreement_add, name='agreement_add'),
    
    # Учет рабочего времени (существующие)
    path('timesheets/', views.timesheet_list, name='timesheet_list'),
    path('timesheets/create/', views.timesheet_create, name='timesheet_create'),
    path('timesheets/<int:timesheet_id>/', views.timesheet_detail, name='timesheet_detail'),
    path('timesheets/<int:timesheet_id>/edit/', views.timesheet_edit, name='timesheet_edit'),
    path('timesheets/<int:timesheet_id>/close/', views.timesheet_close, name='timesheet_close'),
    path('timesheets/current/', views.current_timesheet, name='current_timesheet'),
    
    path('director/timesheet/<int:timesheet_id>/fill-all-workdays/', views_timesheet.fill_all_workdays, name='fill_all_workdays'),
    path('director/timesheet/<int:timesheet_id>/export-word/', views_timesheet.export_timesheet_t12_from_template, name='export_timesheet_t12_word'),
    
    # ========== МАРШРУТЫ ДЛЯ ТАБЕЛЯ ==========
    path('director/timesheet/', views_timesheet.director_timesheet, name='director_timesheet'),
    path('director/timesheet/quick-edit/', views_timesheet.timesheet_quick_edit, name='timesheet_quick_edit'),
    path('director/timesheet/<int:timesheet_id>/export/', views_timesheet.timesheet_export_excel, name='timesheet_export_excel'),
    path('director/timesheet/<int:timesheet_id>/close/', views_timesheet.timesheet_close, name='timesheet_close'),
    path('director/timesheet/<int:timesheet_id>/export-t13/', views_timesheet.export_timesheet_t13_template, name='export_timesheet_t13_template'),
    path('director/timesheet/<int:timesheet_id>/export-word/', views_timesheet.export_timesheet_t12_from_template, name='export_timesheet_t12_word'),
    
    # НОВЫЕ URL ДЛЯ ДОБАВЛЕНИЯ СОТРУДНИКОВ
    path('director/timesheet/<int:timesheet_id>/available-employees/', views_timesheet.get_available_employees, name='get_available_employees'),
    path('director/timesheet/<int:timesheet_id>/add-employees/', views_timesheet.add_employees_to_timesheet, name='add_employees_to_timesheet'),
    
    # AJAX
    path('api/check-dispensary-right/', views_timesheet.check_dispensary_right, name='check_dispensary_right'),
    
    # Графики работы
    path('schedules/', views.schedule_list, name='schedule_list'),
    path('schedules/create/', views.schedule_create, name='schedule_create'),
    path('schedules/<int:schedule_id>/', views.schedule_detail, name='schedule_detail'),
    path('schedules/<int:schedule_id>/edit/', views.schedule_edit, name='schedule_edit'),
    path('schedules/<int:schedule_id>/entries/add/', views.schedule_entry_add, name='schedule_entry_add'),
    
    # Отпуска
    path('leave/', views.leave_dashboard, name='leave_dashboard'),
    path('leave/schedule/', views.leave_schedule_list, name='leave_schedule_list'),
    path('leave/schedule/create/', views.leave_schedule_create, name='leave_schedule_create'),
    path('leave/schedule/<int:schedule_id>/edit/', views.leave_schedule_edit, name='leave_schedule_edit'),
    path('leave/requests/', views.leave_requests, name='leave_requests'),
    path('leave/requests/create/', views.leave_request_create, name='leave_request_create'),
    path('leave/requests/<int:request_id>/process/', views.leave_request_process, name='leave_request_process'),
    
    # Дисциплинарные взыскания и поощрения
    path('discipline/', views.discipline_dashboard, name='discipline_dashboard'),
    path('discipline/actions/', views.disciplinary_actions_list, name='disciplinary_actions_list'),
    path('employees/<int:employee_id>/actions/add/', views.disciplinary_action_add, name='disciplinary_action_add'),
    path('actions/<int:action_id>/lift/', views.disciplinary_action_lift, name='disciplinary_action_lift'),
    path('actions/<int:action_id>/edit/', views.disciplinary_action_edit, name='disciplinary_action_edit'),
    path('encouragements/', views.encouragements_list, name='encouragements_list'),
    path('employees/<int:employee_id>/encouragements/add/', views.encouragement_add, name='encouragement_add'),
    path('encouragements/<int:enc_id>/edit/', views.encouragement_edit, name='encouragement_edit'),
    
    # Диспансеризация
    path('dispensary/', views.dispensary_list, name='dispensary_list'),
    path('employees/<int:employee_id>/dispensary/add/', views.dispensary_add, name='dispensary_add'),
    path('dispensary/<int:record_id>/edit/', views.dispensary_edit, name='dispensary_edit'),
    
    # ============ КОНСТРУКТОР ЗАРПЛАТЫ (Payroll) ============
    path('payroll/types/', views.payroll_type_list, name='payroll_type_list'),
    path('payroll/types/create/', views.payroll_type_create, name='payroll_type_create'),
    path('payroll/types/<int:pk>/edit/', views.payroll_type_edit, name='payroll_type_edit'),
    path('payroll/types/<int:pk>/delete/', views.payroll_type_delete, name='payroll_type_delete'),
    
    # Назначение начислений сотрудникам
    path('employees/<int:employee_id>/assignments/', views.employee_payroll_assignments, name='employee_payroll_assignments'),
    path('employees/<int:employee_id>/assignments/add/', views.employee_payroll_assignment_add, name='employee_payroll_assignment_add'),
    path('assignments/<int:assignment_id>/edit/', views.employee_payroll_assignment_edit, name='employee_payroll_assignment_edit'),
    path('assignments/<int:assignment_id>/delete/', views.employee_payroll_assignment_delete, name='employee_payroll_assignment_delete'),
    
    # Графики работы сотрудников
    path('employee-schedules/', views.employee_schedule_list, name='employee_schedule_list'),
    path('employee-schedules/create/', views.employee_schedule_create, name='employee_schedule_create'),
    
    # Приказы о приеме
    path('hire-orders/', views.hire_order_list, name='hire_order_list'),
    path('hire-orders/create/<int:employee_id>/', views.hire_order_create, name='hire_order_create'),
    path('hire-orders/<int:order_id>/', views.hire_order_detail, name='hire_order_detail'),
    path('hire-orders/<int:order_id>/pdf/', views.hire_order_generate_pdf, name='hire_order_generate_pdf'),
    path('hire-orders/<int:order_id>/print/', views.hire_order_print, name='hire_order_print'),
    
    # Профиль сотрудника
    path('profile/', views.employee_profile, name='employee_profile'),
    path('change-photo/', views.change_photo, name='change_photo'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Инвайты
    path('invite/<int:employee_id>/', views.invite_employee, name='invite_employee'),
    path('accept-invite/<str:token>/', views.accept_invite, name='accept_invite'),
    
    # Отчеты (экспорт)
    path('reports/staff-list/excel/', views.export_staff_list_excel, name='export_staff_list_excel'),
    path('reports/leave-schedule/pdf/', views.export_leave_schedule_pdf, name='export_leave_schedule_pdf'),
    path('reports/salary-payroll/excel/', views.export_salary_payroll_excel, name='export_salary_payroll_excel'),
    
    # AJAX
    path('api/check-document-expiry/', views.check_document_expiry_ajax, name='check_document_expiry'),
    path('api/get-employee-contracts/', views.get_employee_contracts_ajax, name='get_employee_contracts'),
    path('api/calculate-salary/', views.calculate_salary_ajax, name='calculate_salary'),
    path('debug-template/', views_timesheet.debug_template_structure, name='debug_template'),
]
