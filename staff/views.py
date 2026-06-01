# staff/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.db import transaction
from datetime import datetime, timedelta, date
import json
import calendar
from decimal import Decimal
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
import io
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter


import os
from django.conf import settings
from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from django.http import HttpResponse

import uuid
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.conf import settings

# Импорт модели пользователя
from accounts.models import CustomUser

# Импорт форм профиля
from .forms_profile import EmployeeProfileForm, ChangePasswordForm

# staff/views.py - исправленные импорты (строки 35-45)
# staff/views.py - исправленные импорты (строки 35-45)

from .models import (
    Employee, PersonalFile, PassportData, INN, SNILS,
    EducationDocument, QualificationCourse, Attestation,
    MedicalExamination, CriminalRecordCheck, StaffPosition,
    StaffUnit, Vacancy, VacancyCandidate, LaborContract,
    AdditionalAgreement, WorkSchedule,  # Убрали WorkScheduleEntry
    Timesheet, TimesheetEntry, LeaveSchedule, LeaveRequest,
    DisciplinaryAction, Encouragement, DispensaryRecord,
    SalaryCalculation, SalaryComponent, HireOrder
)

# staff/views.py - исправленные импорты форм

from .forms import (
    EmployeeForm, PassportDataForm, INNForm, SNILSForm,
    EducationDocumentForm, QualificationCourseForm, AttestationForm,
    MedicalExaminationForm, CriminalRecordCheckForm, StaffPositionForm,
    StaffUnitForm, VacancyForm, VacancyCandidateForm, LaborContractForm,
    AdditionalAgreementForm, WorkScheduleForm,  # Убрали WorkScheduleEntryForm
    TimesheetEntryForm, LeaveScheduleForm, LeaveRequestForm,
    DisciplinaryActionForm, EncouragementForm, DispensaryRecordForm,
    HireOrderForm
)

def director_required(view_func):
    """Декоратор для проверки прав заведующей"""
    decorated_view_func = user_passes_test(
        lambda u: u.is_authenticated and u.role == 'director',
        login_url='/accounts/login/'
    )(view_func)
    return decorated_view_func


@login_required
@director_required
def staff_dashboard(request):
    """Главная панель управления сотрудниками"""
    
    # Статистика
    total_employees = Employee.objects.filter(is_active=True).count()
    
    # Распределение по категориям
    employee_types = []
    for type_code, type_name in Employee.EMPLOYEE_TYPES:
        count = Employee.objects.filter(employee_type=type_code, is_active=True).count()
        if count > 0:
            employee_types.append({
                'code': type_code,
                'name': type_name,
                'count': count
            })
    
    # Вакансии
    vacancies_count = StaffUnit.objects.filter(is_vacant=True).count()
    
    # Истекающие документы (медосмотры)
    expiring_medical = MedicalExamination.objects.filter(
        valid_until__lte=date.today() + timedelta(days=30),
        valid_until__gte=date.today()
    ).select_related('employee').count()
    
    # Истекающие справки об отсутствии судимости
    expiring_criminal = CriminalRecordCheck.objects.filter(
        valid_until__lte=date.today() + timedelta(days=30),
        valid_until__gte=date.today()
    ).select_related('employee').count()
    
    # Просроченные документы
    expired_medical = MedicalExamination.objects.filter(
        valid_until__lt=date.today()
    ).select_related('employee').count()
    
    # Заявления на отпуск на рассмотрении
    pending_leave_requests = LeaveRequest.objects.filter(status='pending').count()
    
    # Табель за текущий месяц
    current_month = date.today().month
    current_year = date.today().year
    current_timesheet = Timesheet.objects.filter(month=current_month, year=current_year).first()
    
    # Последние добавленные сотрудники
    recent_employees = Employee.objects.order_by('-created_at')[:5]
    
    # Активные вакансии
    active_vacancies = Vacancy.objects.filter(is_published=True, staff_unit__is_vacant=True)[:5]
    
    context = {
        'total_employees': total_employees,
        'employee_types': employee_types,
        'vacancies_count': vacancies_count,
        'expiring_medical': expiring_medical,
        'expiring_criminal': expiring_criminal,
        'expired_medical': expired_medical,
        'pending_leave_requests': pending_leave_requests,
        'current_timesheet': current_timesheet,
        'recent_employees': recent_employees,
        'active_vacancies': active_vacancies,
        'current_month': current_month,
        'current_year': current_year,
        'now': timezone.now(),
    }
    
    return render(request, 'staff/dashboard.html', context)


# ==================== CRUD СОТРУДНИКОВ ====================

@login_required
@director_required
def employee_list(request):
    """Список сотрудников"""
    
    # Фильтры
    employee_type = request.GET.get('type', '')
    is_active = request.GET.get('is_active', '')
    search = request.GET.get('search', '')
    
    employees = Employee.objects.all()
    
    if employee_type:
        employees = employees.filter(employee_type=employee_type)
    
    if is_active == 'active':
        employees = employees.filter(is_active=True)
    elif is_active == 'inactive':
        employees = employees.filter(is_active=False)
    
    if search:
        employees = employees.filter(
            Q(full_name__icontains=search) |
            Q(position__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )
    
    employees = employees.order_by('full_name')
    
    # Группировка по категориям
    grouped_employees = {}
    for type_code, type_name in Employee.EMPLOYEE_TYPES:
        grouped = employees.filter(employee_type=type_code)
        if grouped.exists():
            grouped_employees[type_name] = grouped
    
    context = {
        'grouped_employees': grouped_employees,
        'employee_types': Employee.EMPLOYEE_TYPES,
        'filters': {
            'type': employee_type,
            'is_active': is_active,
            'search': search,
        }
    }
    
    return render(request, 'staff/employee_list.html', context)


@login_required
@director_required
def employee_create(request):
    """Создание нового сотрудника"""
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            employee = form.save()
            
            # Автоматически создаем личное дело
            PersonalFile.objects.create(
                employee=employee,
                file_number=f"LD-{employee.id}-{date.today().year}"
            )
            
            messages.success(request, f'Сотрудник {employee.full_name} успешно добавлен!')
            return redirect('staff:employee_detail', employee_id=employee.id)
    else:
        form = EmployeeForm()
    
    return render(request, 'staff/employee_form.html', {
        'form': form,
        'title': 'Добавление сотрудника',
        'submit_text': 'Добавить'
    })


@login_required
@director_required
def employee_detail(request, employee_id):
    """Детальная страница сотрудника"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    # 👇 ОПРЕДЕЛЯЕМ today В САМОМ НАЧАЛЕ
    today = date.today()
    
    # Получаем связанные данные
    passport = PassportData.objects.filter(employee=employee).first()
    inn = INN.objects.filter(employee=employee).first()
    snils = SNILS.objects.filter(employee=employee).first()
    criminal_check = CriminalRecordCheck.objects.filter(employee=employee).first()
    personal_file = PersonalFile.objects.filter(employee=employee).first()
    
    # Образование
    education_docs = EducationDocument.objects.filter(employee=employee)
    
    # Курсы
    courses = QualificationCourse.objects.filter(employee=employee).order_by('-end_date')
    
    # Аттестации
    attestations = Attestation.objects.filter(employee=employee).order_by('-attestation_date')
    
    # Медосмотры
    medical_exams = MedicalExamination.objects.filter(employee=employee).order_by('-examination_date')
    
    # Договоры
    contracts = LaborContract.objects.filter(employee=employee, is_active=True)
    
    # Текущий статус документов
    documents_status = {
        'passport': passport is not None,
        'inn': inn is not None,
        'snils': snils is not None,
        'criminal_check': criminal_check is not None and criminal_check.is_valid,
        'medical': any(exam.is_valid for exam in medical_exams) if medical_exams else False,
    }
    
    # Предупреждения об истечении документов
    expiring_documents = []
    
    # Медосмотры, истекающие в ближайшие 30 дней
    for med in medical_exams:
        if med.valid_until >= today:  # 👉 ИСПОЛЬЗУЕМ today
            days = med.days_until_expiry
            if 0 <= days <= 30:
                expiring_documents.append({
                    'type': 'Медосмотр',
                    'date': med.valid_until,
                    'days_left': days
                })
    
    # Справка об отсутствии судимости
    if criminal_check and criminal_check.valid_until >= today:  # 👉 ИСПОЛЬЗУЕМ today
        days = criminal_check.days_until_expiry
        if 0 <= days <= 30:
            expiring_documents.append({
                'type': 'Справка о несудимости',
                'date': criminal_check.valid_until,
                'days_left': days
            })
    
    # Аттестации - 👇 ТЕПЕРЬ today УЖЕ ОПРЕДЕЛЕНА
    for att in attestations:
        if att.valid_until >= today:  # 👉 ИСПОЛЬЗУЕМ today
            days = (att.valid_until - today).days
            if 0 <= days <= 30:
                expiring_documents.append({
                    'type': 'Аттестация',
                    'date': att.valid_until,
                    'days_left': days
                })
    
    context = {
        'employee': employee,
        'today': today,  # 👇 ПЕРЕДАЕМ В ШАБЛОН
        'passport': passport,
        'inn': inn,
        'snils': snils,
        'criminal_check': criminal_check,
        'personal_file': personal_file,
        'education_docs': education_docs,
        'courses': courses,
        'attestations': attestations,
        'medical_exams': medical_exams,
        'contracts': contracts,
        'documents_status': documents_status,
        'expiring_documents': expiring_documents,
    }
    
    return render(request, 'staff/employee_detail.html', context)


@login_required
@director_required
def employee_edit(request, employee_id):
    """Редактирование сотрудника"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = EmployeeForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, f'Данные сотрудника {employee.full_name} обновлены!')
            return redirect('staff:employee_detail', employee_id=employee.id)
    else:
        form = EmployeeForm(instance=employee)
    
    return render(request, 'staff/employee_form.html', {
        'form': form,
        'employee': employee,
        'title': f'Редактирование: {employee.full_name}',
        'submit_text': 'Сохранить'
    })


@login_required
@director_required
def employee_delete(request, employee_id):
    """Удаление сотрудника"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        employee.delete()
        messages.success(request, f'Сотрудник {employee.full_name} удален!')
        return redirect('staff:employee_list')
    
    return render(request, 'staff/employee_confirm_delete.html', {
        'employee': employee
    })


# ==================== ЛИЧНЫЕ ДЕЛА ====================

@login_required
@director_required
def personal_file_detail(request, employee_id):
    """Просмотр личного дела"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    personal_file = PersonalFile.objects.get_or_create(
        employee=employee,
        defaults={'file_number': f"LD-{employee.id}-{date.today().year}"}
    )[0]
    
    return render(request, 'staff/personal_file_detail.html', {
        'employee': employee,
        'personal_file': personal_file
    })


@login_required
@director_required
def personal_file_edit(request, employee_id):
    """Редактирование личного дела"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    personal_file = PersonalFile.objects.get_or_create(
        employee=employee,
        defaults={'file_number': f"LD-{employee.id}-{date.today().year}"}
    )[0]
    
    if request.method == 'POST':
        # Обновляем файлы - ИСПРАВЛЕНО: 'order' на 'order_file'
        for field in ['personal_card', 'employment_history', 'application',
                      'order_file', 'military_registration', 'additional_docs']:
            if field in request.FILES:
                setattr(personal_file, field, request.FILES[field])
        
        personal_file.notes = request.POST.get('notes', '')
        personal_file.save()
        
        messages.success(request, 'Личное дело обновлено!')
        return redirect('staff:personal_file_detail', employee_id=employee.id)
    
    return render(request, 'staff/personal_file_edit.html', {
        'employee': employee,
        'personal_file': personal_file
    })


# ==================== ПАСПОРТНЫЕ ДАННЫЕ ====================

# staff/views.py

@login_required
@director_required
def passport_data(request, employee_id):
    """Просмотр/редактирование паспортных данных"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    # Используем try/except вместо get_or_create, чтобы избежать создания пустой записи
    try:
        passport = PassportData.objects.get(employee=employee)
        created = False
    except PassportData.DoesNotExist:
        passport = None
        created = True
    
    if request.method == 'POST':
        if passport:
            form = PassportDataForm(request.POST, request.FILES, instance=passport)
        else:
            form = PassportDataForm(request.POST, request.FILES)
        
        if form.is_valid():
            passport = form.save(commit=False)
            passport.employee = employee
            passport.save()
            messages.success(request, 'Паспортные данные сохранены!')
            return redirect('staff:employee_detail', employee_id=employee.id)
    else:
        # GET запрос - показываем форму
        if passport:
            form = PassportDataForm(instance=passport)
        else:
            # Для новой записи показываем пустую форму
            form = PassportDataForm()
    
    return render(request, 'staff/passport_form.html', {
        'form': form,
        'employee': employee,
        'passport': passport
    })


# ==================== ИНН ====================

@login_required
@director_required
def inn_data(request, employee_id):
    """Просмотр/редактирование ИНН"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    inn, created = INN.objects.get_or_create(employee=employee)
    
    if request.method == 'POST':
        form = INNForm(request.POST, request.FILES, instance=inn)
        if form.is_valid():
            form.save()
            messages.success(request, 'ИНН сохранен!')
            return redirect('staff:employee_detail', employee_id=employee.id)
    else:
        form = INNForm(instance=inn)
    
    return render(request, 'staff/inn_form.html', {
        'form': form,
        'employee': employee
    })


# ==================== СНИЛС ====================

@login_required
@director_required
def snils_data(request, employee_id):
    """Просмотр/редактирование СНИЛС"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    snils, created = SNILS.objects.get_or_create(employee=employee)
    
    if request.method == 'POST':
        form = SNILSForm(request.POST, request.FILES, instance=snils)
        if form.is_valid():
            form.save()
            messages.success(request, 'СНИЛС сохранен!')
            return redirect('staff:employee_detail', employee_id=employee.id)
    else:
        form = SNILSForm(instance=snils)
    
    return render(request, 'staff/snils_form.html', {
        'form': form,
        'employee': employee
    })


# ==================== ОБРАЗОВАНИЕ ====================

@login_required
@director_required
def education_list(request, employee_id):
    """Список документов об образовании"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    education_docs = EducationDocument.objects.filter(employee=employee).order_by('-issue_date')
    
    return render(request, 'staff/education_list.html', {
        'employee': employee,
        'education_docs': education_docs
    })


@login_required
@director_required
def education_add(request, employee_id):
    """Добавление документа об образовании"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = EducationDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            education = form.save(commit=False)
            education.employee = employee
            education.save()
            messages.success(request, 'Документ об образовании добавлен!')
            return redirect('staff:education_list', employee_id=employee.id)
    else:
        form = EducationDocumentForm()
    
    return render(request, 'staff/education_form.html', {
        'form': form,
        'employee': employee,
        'title': 'Добавление документа об образовании'
    })


@login_required
@director_required
def education_edit(request, doc_id):
    """Редактирование документа об образовании"""
    
    education = get_object_or_404(EducationDocument, id=doc_id)
    
    if request.method == 'POST':
        form = EducationDocumentForm(request.POST, request.FILES, instance=education)
        if form.is_valid():
            form.save()
            messages.success(request, 'Документ обновлен!')
            return redirect('staff:education_list', employee_id=education.employee.id)
    else:
        form = EducationDocumentForm(instance=education)
    
    return render(request, 'staff/education_form.html', {
        'form': form,
        'employee': education.employee,
        'education': education,
        'title': 'Редактирование документа'
    })


@login_required
@director_required
def education_delete(request, doc_id):
    """Удаление документа об образовании"""
    
    education = get_object_or_404(EducationDocument, id=doc_id)
    employee_id = education.employee.id
    
    if request.method == 'POST':
        education.delete()
        messages.success(request, 'Документ удален!')
        return redirect('staff:education_list', employee_id=employee_id)
    
    return render(request, 'staff/education_confirm_delete.html', {
        'education': education
    })


# ==================== КУРСЫ ПОВЫШЕНИЯ КВАЛИФИКАЦИИ ====================

@login_required
@director_required
def courses_list(request, employee_id):
    """Список курсов повышения квалификации"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    courses = QualificationCourse.objects.filter(employee=employee).order_by('-end_date')
    
    return render(request, 'staff/courses_list.html', {
        'employee': employee,
        'courses': courses
    })


@login_required
@director_required
def course_add(request, employee_id):
    """Добавление курса"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = QualificationCourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.employee = employee
            course.save()
            messages.success(request, 'Курс добавлен!')
            return redirect('staff:courses_list', employee_id=employee.id)
    else:
        form = QualificationCourseForm()
    
    return render(request, 'staff/course_form.html', {
        'form': form,
        'employee': employee,
        'title': 'Добавление курса'
    })


@login_required
@director_required
def course_edit(request, course_id):
    """Редактирование курса"""
    
    course = get_object_or_404(QualificationCourse, id=course_id)
    
    if request.method == 'POST':
        form = QualificationCourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, 'Курс обновлен!')
            return redirect('staff:courses_list', employee_id=course.employee.id)
    else:
        form = QualificationCourseForm(instance=course)
    
    return render(request, 'staff/course_form.html', {
        'form': form,
        'employee': course.employee,
        'course': course,
        'title': 'Редактирование курса'
    })


@login_required
@director_required
def course_delete(request, course_id):
    """Удаление курса"""
    
    course = get_object_or_404(QualificationCourse, id=course_id)
    employee_id = course.employee.id
    
    if request.method == 'POST':
        course.delete()
        messages.success(request, 'Курс удален!')
        return redirect('staff:courses_list', employee_id=employee_id)
    
    return render(request, 'staff/course_confirm_delete.html', {
        'course': course
    })


# ==================== АТТЕСТАЦИЯ ====================

@login_required
@director_required
def attestation_list(request, employee_id):
    """Список аттестаций"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    attestations = Attestation.objects.filter(employee=employee).order_by('-attestation_date')
    
    return render(request, 'staff/attestation_list.html', {
        'employee': employee,
        'attestations': attestations
    })


@login_required
@director_required
def attestation_add(request, employee_id):
    """Добавление аттестации"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = AttestationForm(request.POST, request.FILES)
        if form.is_valid():
            attestation = form.save(commit=False)
            attestation.employee = employee
            attestation.save()
            messages.success(request, 'Аттестация добавлена!')
            return redirect('staff:attestation_list', employee_id=employee.id)
    else:
        form = AttestationForm()
    
    return render(request, 'staff/attestation_form.html', {
        'form': form,
        'employee': employee,
        'title': 'Добавление аттестации'
    })


@login_required
@director_required
def attestation_edit(request, att_id):
    """Редактирование аттестации"""
    
    attestation = get_object_or_404(Attestation, id=att_id)
    
    if request.method == 'POST':
        form = AttestationForm(request.POST, request.FILES, instance=attestation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Аттестация обновлена!')
            return redirect('staff:attestation_list', employee_id=attestation.employee.id)
    else:
        form = AttestationForm(instance=attestation)
    
    return render(request, 'staff/attestation_form.html', {
        'form': form,
        'employee': attestation.employee,
        'attestation': attestation,
        'title': 'Редактирование аттестации'
    })


@login_required
@director_required
def attestation_delete(request, att_id):
    """Удаление аттестации"""
    
    attestation = get_object_or_404(Attestation, id=att_id)
    employee_id = attestation.employee.id
    
    if request.method == 'POST':
        attestation.delete()
        messages.success(request, 'Аттестация удалена!')
        return redirect('staff:attestation_list', employee_id=employee_id)
    
    return render(request, 'staff/attestation_confirm_delete.html', {
        'attestation': attestation
    })


# ==================== МЕДОСМОТРЫ ====================

@login_required
@director_required
def medical_examinations(request, employee_id):
    """Список медосмотров"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    examinations = MedicalExamination.objects.filter(employee=employee).order_by('-examination_date')
    
    return render(request, 'staff/medical_list.html', {
        'employee': employee,
        'examinations': examinations
    })


@login_required
@director_required
def medical_examination_add(request, employee_id):
    """Добавление медосмотра"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = MedicalExaminationForm(request.POST, request.FILES)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.employee = employee
            exam.save()
            messages.success(request, 'Медосмотр добавлен!')
            return redirect('staff:medical_examinations', employee_id=employee.id)
    else:
        form = MedicalExaminationForm()
    
    return render(request, 'staff/medical_form.html', {
        'form': form,
        'employee': employee,
        'title': 'Добавление медосмотра'
    })


@login_required
@director_required
def medical_examination_edit(request, med_id):
    """Редактирование медосмотра"""
    
    examination = get_object_or_404(MedicalExamination, id=med_id)
    
    if request.method == 'POST':
        form = MedicalExaminationForm(request.POST, request.FILES, instance=examination)
        if form.is_valid():
            form.save()
            messages.success(request, 'Медосмотр обновлен!')
            return redirect('staff:medical_examinations', employee_id=examination.employee.id)
    else:
        form = MedicalExaminationForm(instance=examination)
    
    return render(request, 'staff/medical_form.html', {
        'form': form,
        'employee': examination.employee,
        'examination': examination,
        'title': 'Редактирование медосмотра'
    })


@login_required
@director_required
def medical_examination_delete(request, med_id):
    """Удаление медосмотра"""
    
    examination = get_object_or_404(MedicalExamination, id=med_id)
    employee_id = examination.employee.id
    
    if request.method == 'POST':
        examination.delete()
        messages.success(request, 'Медосмотр удален!')
        return redirect('staff:medical_examinations', employee_id=employee_id)
    
    return render(request, 'staff/medical_confirm_delete.html', {
        'examination': examination
    })


# ==================== СПРАВКИ ОБ ОТСУТСТВИИ СУДИМОСТИ ====================

@login_required
@director_required
def criminal_check_detail(request, employee_id):
    """Просмотр справки о несудимости"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    criminal_check, created = CriminalRecordCheck.objects.get_or_create(employee=employee)
    
    return render(request, 'staff/criminal_check_detail.html', {
        'employee': employee,
        'criminal_check': criminal_check
    })


@login_required
@director_required
def criminal_check_edit(request, employee_id):
    """Редактирование справки о несудимости"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    criminal_check, created = CriminalRecordCheck.objects.get_or_create(employee=employee)
    
    if request.method == 'POST':
        form = CriminalRecordCheckForm(request.POST, request.FILES, instance=criminal_check)
        if form.is_valid():
            form.save()
            messages.success(request, 'Справка обновлена!')
            return redirect('staff:criminal_check_detail', employee_id=employee.id)
    else:
        form = CriminalRecordCheckForm(instance=criminal_check)
    
    return render(request, 'staff/criminal_check_form.html', {
        'form': form,
        'employee': employee
    })


# ==================== НАПОМИНАНИЯ ОБ ИСТЕЧЕНИИ ДОКУМЕНТОВ ====================

@login_required
@director_required
def document_reminders(request):
    """Напоминания об истечении срока документов"""
    
    today = date.today()
    thirty_days_later = today + timedelta(days=30)
    
    # Медосмотры
    expiring_medical = MedicalExamination.objects.filter(
        valid_until__lte=thirty_days_later,
        valid_until__gte=today
    ).select_related('employee').order_by('valid_until')
    
    # Истекшие медосмотры
    expired_medical = MedicalExamination.objects.filter(
        valid_until__lt=today
    ).select_related('employee').order_by('valid_until')
    
    # Справки о несудимости
    expiring_criminal = CriminalRecordCheck.objects.filter(
        valid_until__lte=thirty_days_later,
        valid_until__gte=today
    ).select_related('employee').order_by('valid_until')
    
    expired_criminal = CriminalRecordCheck.objects.filter(
        valid_until__lt=today
    ).select_related('employee').order_by('valid_until')
    
    # Аттестации
    expiring_attestations = Attestation.objects.filter(
        valid_until__lte=thirty_days_later,
        valid_until__gte=today
    ).select_related('employee').order_by('valid_until')
    
    expired_attestations = Attestation.objects.filter(
        valid_until__lt=today
    ).select_related('employee').order_by('valid_until')
    
    # Срочные договоры
    expiring_contracts = LaborContract.objects.filter(
        contract_type='fixed_term',
        end_date__lte=thirty_days_later,
        end_date__gte=today,
        is_active=True
    ).select_related('employee').order_by('end_date')
    
    context = {
        'expiring_medical': expiring_medical,
        'expired_medical': expired_medical,
        'expiring_criminal': expiring_criminal,
        'expired_criminal': expired_criminal,
        'expiring_attestations': expiring_attestations,
        'expired_attestations': expired_attestations,
        'expiring_contracts': expiring_contracts,
        'today': today,
    }
    
    return render(request, 'staff/document_reminders.html', context)


# ==================== ШТАТНОЕ РАСПИСАНИЕ ====================

@login_required
@director_required
def staffing_table(request):
    """Штатное расписание"""
    
    positions = StaffPosition.objects.filter(is_active=True)
    
    # Статистика
    total_units = StaffUnit.objects.count()
    filled_units = StaffUnit.objects.filter(is_vacant=False).count()
    vacant_units = StaffUnit.objects.filter(is_vacant=True).count()
    
    # Группировка по категориям
    staffing_by_category = []
    for category_code, category_name in StaffPosition.POSITION_CATEGORIES:
        category_positions = positions.filter(category=category_code)
        units = StaffUnit.objects.filter(position__in=category_positions)
        
        total = units.count()
        filled = units.filter(is_vacant=False).count()
        vacant = units.filter(is_vacant=True).count()
        
        if total > 0:
            staffing_by_category.append({
                'name': category_name,
                'total': total,
                'filled': filled,
                'vacant': vacant,
                'fill_percentage': round((filled / total) * 100, 1) if total > 0 else 0,
                'positions': category_positions,
            })
    
    # Все штатные единицы с детализацией
    staff_units = StaffUnit.objects.select_related('position', 'employee').all()
    
    context = {
        'staffing_by_category': staffing_by_category,
        'staff_units': staff_units,
        'total_units': total_units,
        'filled_units': filled_units,
        'vacant_units': vacant_units,
        'fill_percentage': round((filled_units / total_units) * 100, 1) if total_units > 0 else 0,
    }
    
    return render(request, 'staff/staffing_table.html', context)

@login_required
@director_required
def position_list(request):
    """Список должностей"""
    
    category = request.GET.get('category', '')
    
    positions = StaffPosition.objects.all().order_by('category', 'title')
    
    if category:
        positions = positions.filter(category=category)
    
    # Статистика
    positions_active = positions.filter(is_active=True).count()
    categories_count = positions.values('category').distinct().count()
    
    context = {
        'positions': positions,
        'positions_active': positions_active,
        'categories_count': categories_count,
        'categories': StaffPosition.POSITION_CATEGORIES,
    }
    
    return render(request, 'staff/position_list.html', context)


@login_required
@director_required
def position_create(request):
    """Создание должности"""
    
    if request.method == 'POST':
        form = StaffPositionForm(request.POST)
        if form.is_valid():
            position = form.save()
            messages.success(request, f'Должность {position.title} создана!')
            return redirect('staff:position_list')
    else:
        form = StaffPositionForm()
    
    return render(request, 'staff/position_form.html', {
        'form': form,
        'title': 'Новая должность'
    })


@login_required
@director_required
def position_edit(request, position_id):
    """Редактирование должности"""
    
    position = get_object_or_404(StaffPosition, id=position_id)
    
    if request.method == 'POST':
        form = StaffPositionForm(request.POST, instance=position)
        if form.is_valid():
            form.save()
            messages.success(request, 'Должность обновлена!')
            return redirect('staff:position_list')
    else:
        form = StaffPositionForm(instance=position)
    
    return render(request, 'staff/position_form.html', {
        'form': form,
        'position': position,
        'title': f'Редактирование: {position.title}'
    })


@login_required
@director_required
def staff_unit_create(request):
    """Создание штатной единицы"""
    
    if request.method == 'POST':
        form = StaffUnitForm(request.POST)
        if form.is_valid():
            unit = form.save()
            # Если указан сотрудник, снимаем флаг вакансии
            if unit.employee:
                unit.is_vacant = False
                unit.save()
            
            # Создаем вакансию, если единица вакантна
            if unit.is_vacant:
                Vacancy.objects.create(
                    staff_unit=unit,
                    requirements="Требования к кандидату не указаны",
                    responsibilities="Обязанности согласно должностной инструкции",
                    conditions="Условия работы согласно ТК РФ"
                )
            
            messages.success(request, 'Штатная единица создана!')
            return redirect('staff:staffing_table')
    else:
        form = StaffUnitForm()
    
    return render(request, 'staff/staff_unit_form.html', {
        'form': form,
        'title': 'Новая штатная единица'
    })


@login_required
@director_required
def staff_unit_edit(request, unit_id):
    """Редактирование штатной единицы"""
    
    unit = get_object_or_404(StaffUnit, id=unit_id)
    
    if request.method == 'POST':
        form = StaffUnitForm(request.POST, instance=unit)
        if form.is_valid():
            unit = form.save()
            # Обновляем статус вакансии
            unit.is_vacant = unit.employee is None
            unit.save()
            
            messages.success(request, 'Штатная единица обновлена!')
            return redirect('staff:staffing_table')
    else:
        form = StaffUnitForm(instance=unit)
    
    return render(request, 'staff/staff_unit_form.html', {
        'form': form,
        'unit': unit,
        'title': f'Редактирование штатной единицы'
    })


@login_required
@director_required
def staff_unit_delete(request, unit_id):
    """Удаление штатной единицы"""
    
    unit = get_object_or_404(StaffUnit, id=unit_id)
    
    if request.method == 'POST':
        unit.delete()
        messages.success(request, 'Штатная единица удалена!')
        return redirect('staff:staffing_table')
    
    return render(request, 'staff/staff_unit_confirm_delete.html', {
        'unit': unit
    })


# ==================== ВАКАНСИИ ====================

@login_required
@director_required
def vacancy_list(request):
    """Список вакансий"""
    
    vacancies = Vacancy.objects.filter(is_published=True).select_related('staff_unit__position')
    
    return render(request, 'staff/vacancy_list.html', {
        'vacancies': vacancies
    })


@login_required
@director_required
def vacancy_create(request):
    """Создание вакансии"""
    
    # Получаем свободные штатные единицы без вакансий
    available_units = StaffUnit.objects.filter(is_vacant=True).exclude(
        vacancy__isnull=False
    )
    
    if request.method == 'POST':
        unit_id = request.POST.get('staff_unit')
        staff_unit = get_object_or_404(StaffUnit, id=unit_id)
        
        # Проверяем, нет ли уже вакансии
        if hasattr(staff_unit, 'vacancy'):
            messages.error(request, 'Для этой штатной единицы уже есть вакансия')
            return redirect('staff:vacancy_create')
        
        form = VacancyForm(request.POST)
        if form.is_valid():
            vacancy = form.save(commit=False)
            vacancy.staff_unit = staff_unit
            vacancy.save()
            messages.success(request, 'Вакансия создана!')
            return redirect('staff:vacancy_detail', vacancy_id=vacancy.id)
    else:
        form = VacancyForm()
    
    return render(request, 'staff/vacancy_form.html', {
        'form': form,
        'available_units': available_units,
        'title': 'Новая вакансия'
    })


@login_required
@director_required
def vacancy_detail(request, vacancy_id):
    """Детальная страница вакансии"""
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    candidates = VacancyCandidate.objects.filter(vacancy=vacancy).order_by('-created_at')
    
    return render(request, 'staff/vacancy_detail.html', {
        'vacancy': vacancy,
        'candidates': candidates
    })


@login_required
@director_required
def vacancy_edit(request, vacancy_id):
    """Редактирование вакансии"""
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    
    if request.method == 'POST':
        form = VacancyForm(request.POST, instance=vacancy)
        if form.is_valid():
            form.save()
            messages.success(request, 'Вакансия обновлена!')
            return redirect('staff:vacancy_detail', vacancy_id=vacancy.id)
    else:
        form = VacancyForm(instance=vacancy)
    
    return render(request, 'staff/vacancy_form.html', {
        'form': form,
        'vacancy': vacancy,
        'title': f'Редактирование вакансии: {vacancy.staff_unit.position.title}'
    })


@login_required
@director_required
def vacancy_close(request, vacancy_id):
    """Закрытие вакансии (принят сотрудник)"""
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        if employee_id:
            employee = get_object_or_404(Employee, id=employee_id)
            
            # Заполняем штатную единицу
            vacancy.staff_unit.employee = employee
            vacancy.staff_unit.is_vacant = False
            vacancy.staff_unit.save()
            
            # Закрываем вакансию
            vacancy.is_published = False
            vacancy.save()
            
            messages.success(request, f'Вакансия закрыта, сотрудник {employee.full_name} принят!')
        else:
            # Просто закрываем вакансию без назначения сотрудника
            vacancy.is_published = False
            vacancy.save()
            messages.success(request, 'Вакансия закрыта')
        
        return redirect('staff:vacancy_list')
    
    # Список кандидатов для быстрого назначения
    candidates = VacancyCandidate.objects.filter(vacancy=vacancy, status='accepted')
    
    return render(request, 'staff/vacancy_close.html', {
        'vacancy': vacancy,
        'candidates': candidates
    })


@login_required
@director_required
def candidate_add(request, vacancy_id):
    """Добавление кандидата на вакансию"""
    
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    
    if request.method == 'POST':
        form = VacancyCandidateForm(request.POST, request.FILES)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.vacancy = vacancy
            candidate.save()
            messages.success(request, f'Кандидат {candidate.full_name} добавлен!')
            return redirect('staff:vacancy_detail', vacancy_id=vacancy.id)
    else:
        form = VacancyCandidateForm()
    
    return render(request, 'staff/candidate_form.html', {
        'form': form,
        'vacancy': vacancy
    })


# ==================== ТРУДОВЫЕ ДОГОВОРЫ ====================

@login_required
@director_required
def contract_list(request):
    """Список всех трудовых договоров"""
    
    contracts = LaborContract.objects.filter(is_active=True).select_related('employee').order_by('-start_date')
    
    # Фильтры
    contract_type = request.GET.get('type', '')
    if contract_type:
        contracts = contracts.filter(contract_type=contract_type)
    
    expiring_soon = contracts.filter(
        contract_type='fixed_term',
        end_date__lte=date.today() + timedelta(days=30)
    )
    
    context = {
        'contracts': contracts,
        'expiring_soon': expiring_soon,
        'contract_type': contract_type,
    }
    
    return render(request, 'staff/contract_list.html', context)


@login_required
@director_required
def employee_contracts(request, employee_id):
    """Договоры конкретного сотрудника"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    contracts = LaborContract.objects.filter(employee=employee).order_by('-start_date')
    
    return render(request, 'staff/employee_contracts.html', {
        'employee': employee,
        'contracts': contracts
    })


@login_required
@director_required
def contract_create(request, employee_id):
    """Создание трудового договора"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = LaborContractForm(request.POST, request.FILES)
        if form.is_valid():
            contract = form.save(commit=False)
            contract.employee = employee
            contract.save()
            messages.success(request, f'Договор №{contract.contract_number} создан!')
            return redirect('staff:employee_contracts', employee_id=employee.id)
    else:
        # Предзаполняем некоторые поля
        initial = {
            'start_date': employee.hire_date,
        }
        form = LaborContractForm(initial=initial)
    
    return render(request, 'staff/contract_form.html', {
        'form': form,
        'employee': employee,
        'title': 'Новый трудовой договор'
    })


@login_required
@director_required
def contract_detail(request, contract_id):
    """Детальная страница договора"""
    
    contract = get_object_or_404(LaborContract, id=contract_id)
    additional_agreements = AdditionalAgreement.objects.filter(contract=contract).order_by('-agreement_date')
    
    return render(request, 'staff/contract_detail.html', {
        'contract': contract,
        'additional_agreements': additional_agreements
    })


@login_required
@director_required
def contract_edit(request, contract_id):
    """Редактирование договора"""
    
    contract = get_object_or_404(LaborContract, id=contract_id)
    
    if request.method == 'POST':
        form = LaborContractForm(request.POST, request.FILES, instance=contract)
        if form.is_valid():
            form.save()
            messages.success(request, 'Договор обновлен!')
            return redirect('staff:contract_detail', contract_id=contract.id)
    else:
        form = LaborContractForm(instance=contract)
    
    return render(request, 'staff/contract_form.html', {
        'form': form,
        'contract': contract,
        'employee': contract.employee,
        'title': f'Редактирование договора №{contract.contract_number}'
    })


@login_required
@director_required
def contract_terminate(request, contract_id):
    """Расторжение договора"""
    
    contract = get_object_or_404(LaborContract, id=contract_id)
    
    if request.method == 'POST':
        termination_date = request.POST.get('termination_date')
        termination_reason = request.POST.get('termination_reason')
        
        if termination_date:
            contract.termination_date = termination_date
            contract.termination_reason = termination_reason
            contract.is_active = False
            contract.save()
            
            # Также помечаем сотрудника как уволенного, если это основной договор
            if contract.employee.is_active:
                contract.employee.is_active = False
                contract.employee.dismissal_date = termination_date
                contract.employee.dismissal_reason = termination_reason
                contract.employee.save()
            
            messages.success(request, 'Договор расторгнут')
            return redirect('staff:contract_detail', contract_id=contract.id)
    
    return render(request, 'staff/contract_terminate.html', {
        'contract': contract
    })


@login_required
@director_required
def agreement_add(request, contract_id):
    """Добавление дополнительного соглашения"""
    
    contract = get_object_or_404(LaborContract, id=contract_id)
    
    if request.method == 'POST':
        form = AdditionalAgreementForm(request.POST, request.FILES)
        if form.is_valid():
            agreement = form.save(commit=False)
            agreement.contract = contract
            agreement.save()
            messages.success(request, 'Дополнительное соглашение добавлено!')
            return redirect('staff:contract_detail', contract_id=contract.id)
    else:
        form = AdditionalAgreementForm()
    
    return render(request, 'staff/agreement_form.html', {
        'form': form,
        'contract': contract
    })


# ==================== УЧЕТ РАБОЧЕГО ВРЕМЕНИ ====================

@login_required
@director_required
def timesheet_list(request):
    """Список табелей"""
    
    timesheets = Timesheet.objects.all().order_by('-year', '-month')
    
    return render(request, 'staff/timesheet_list.html', {
        'timesheets': timesheets
    })


@login_required
@director_required
def timesheet_create(request):
    """Создание нового табеля"""
    
    if request.method == 'POST':
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        
        # Проверяем, существует ли уже табель
        timesheet, created = Timesheet.objects.get_or_create(
            month=month,
            year=year,
            defaults={'created_by': request.user}
        )
        
        if created:
            # Создаем записи для всех активных сотрудников
            employees = Employee.objects.filter(is_active=True)
            for employee in employees:
                TimesheetEntry.objects.create(
                    timesheet=timesheet,
                    employee=employee
                )
            messages.success(request, f'Табель за {month}.{year} создан!')
        else:
            messages.warning(request, f'Табель за {month}.{year} уже существует')
        
        return redirect('staff:timesheet_detail', timesheet_id=timesheet.id)
    
    # Текущий месяц и год для предзаполнения
    today = date.today()
    context = {
        'current_month': today.month,
        'current_year': today.year,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(today.year - 2, today.year + 2),
    }
    
    return render(request, 'staff/timesheet_create.html', context)


@login_required
@director_required
def timesheet_detail(request, timesheet_id):
    """Просмотр и редактирование табеля"""
    
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    entries = TimesheetEntry.objects.filter(timesheet=timesheet).select_related('employee').order_by('employee__full_name')
    
    # Количество дней в месяце
    days_in_month = calendar.monthrange(timesheet.year, timesheet.month)[1]
    days = list(range(1, days_in_month + 1))
    
    # Словарь для кодов
    attendance_codes = dict(TimesheetEntry.ATTENDANCE_CODES)
    
    if request.method == 'POST':
        # Сохраняем изменения
        for entry in entries:
            for day in days:
                day_field = f'day_{day}_{entry.id}'
                if day_field in request.POST:
                    setattr(entry, f'day_{day}', request.POST[day_field])
            
            # Сохраняем информацию об отстранении
            entry.suspension_start = request.POST.get(f'suspension_start_{entry.id}') or None
            entry.suspension_end = request.POST.get(f'suspension_end_{entry.id}') or None
            entry.suspension_reason = request.POST.get(f'suspension_reason_{entry.id}', '')
            entry.suspension_order = request.POST.get(f'suspension_order_{entry.id}', '')
            entry.notes = request.POST.get(f'notes_{entry.id}', '')
            
            entry.calculate_totals()
            entry.save()
        
        messages.success(request, 'Табель сохранен!')
        return redirect('staff:timesheet_detail', timesheet_id=timesheet.id)
    
    context = {
        'timesheet': timesheet,
        'entries': entries,
        'days': days,
        'days_in_month': days_in_month,
        'attendance_codes': attendance_codes,
    }
    
    return render(request, 'staff/timesheet_detail.html', context)


@login_required
@director_required
def timesheet_edit(request, timesheet_id):
    """Альтернативный просмотр табеля"""
    return timesheet_detail(request, timesheet_id)


@login_required
@director_required
def timesheet_close(request, timesheet_id):
    """Закрытие табеля (после этого нельзя редактировать)"""
    
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    
    if request.method == 'POST':
        timesheet.is_closed = True
        timesheet.closed_at = timezone.now()
        timesheet.save()
        messages.success(request, 'Табель закрыт!')
    
    return redirect('staff:timesheet_detail', timesheet_id=timesheet.id)


@login_required
@director_required
def current_timesheet(request):
    """Переход к текущему табелю"""
    
    today = date.today()
    timesheet = Timesheet.objects.filter(month=today.month, year=today.year).first()
    
    if timesheet:
        return redirect('staff:timesheet_detail', timesheet_id=timesheet.id)
    else:
        return redirect('staff:timesheet_create')


# ==================== ГРАФИКИ РАБОТЫ ====================

@login_required
@director_required
def schedule_list(request):
    """Список графиков работы"""
    
    schedules = WorkSchedule.objects.all()
    
    return render(request, 'staff/schedule_list.html', {
        'schedules': schedules
    })


@login_required
@director_required
def schedule_create(request):
    """Создание графика работы"""
    
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save()
            messages.success(request, f'График "{schedule.name}" создан!')
            return redirect('staff:schedule_detail', schedule_id=schedule.id)
    else:
        form = WorkScheduleForm()
    
    return render(request, 'staff/schedule_form.html', {
        'form': form,
        'title': 'Новый график работы'
    })



@login_required
@director_required
def schedule_edit(request, schedule_id):
    """Редактирование графика"""
    
    schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, 'График обновлен!')
            return redirect('staff:schedule_detail', schedule_id=schedule.id)
    else:
        form = WorkScheduleForm(instance=schedule)
    
    return render(request, 'staff/schedule_form.html', {
        'form': form,
        'schedule': schedule,
        'title': f'Редактирование: {schedule.name}'
    })


# ==================== ОТПУСКА ====================

@login_required
@director_required
def leave_dashboard(request):
    """Панель управления отпусками"""
    
    current_year = date.today().year
    
    # График отпусков на текущий год
    leave_schedule = LeaveSchedule.objects.filter(
        year=current_year
    ).select_related('employee').order_by('start_date')
    
    # Статистика
    total_days_planned = leave_schedule.aggregate(total=Sum('duration'))['total'] or 0
    
    # Заявления на рассмотрении
    pending_requests = LeaveRequest.objects.filter(status='pending').select_related('employee').order_by('request_date')
    
    # Конфликты (наложение отпусков)
    overlapping_leaves = []
    for leave in leave_schedule.filter(status__in=['planned', 'approved']):
        if leave.is_overlapping:
            overlapping_leaves.append(leave)
    
    context = {
        'current_year': current_year,
        'leave_schedule': leave_schedule,
        'pending_requests': pending_requests,
        'total_days_planned': total_days_planned,
        'overlapping_leaves': overlapping_leaves,
        'years': range(current_year - 1, current_year + 3),
    }
    
    return render(request, 'staff/leave_dashboard.html', context)


@login_required
@director_required
def leave_schedule_list(request):
    """Список записей в графике отпусков"""
    
    year = request.GET.get('year', date.today().year)
    
    try:
        year = int(year)
    except ValueError:
        year = date.today().year
    
    leave_schedule = LeaveSchedule.objects.filter(year=year).select_related('employee').order_by('start_date')
    
    # Группировка по месяцам
    by_month = {}
    for i in range(1, 13):
        month_leaves = leave_schedule.filter(start_date__month=i)
        if month_leaves.exists():
            by_month[calendar.month_name[i]] = month_leaves
    
    context = {
        'by_month': by_month,
        'year': year,
        'years': range(year - 2, year + 3),
    }
    
    return render(request, 'staff/leave_schedule_list.html', context)


@login_required
@director_required
def leave_schedule_create(request):
    """Добавление записи в график отпусков"""
    
    if request.method == 'POST':
        form = LeaveScheduleForm(request.POST, request.FILES)
        if form.is_valid():
            leave = form.save()
            messages.success(request, 'Запись добавлена в график отпусков!')
            return redirect('staff:leave_schedule_list')
    else:
        # Предзаполняем текущий год
        form = LeaveScheduleForm(initial={'year': date.today().year})
    
    return render(request, 'staff/leave_schedule_form.html', {
        'form': form,
        'title': 'Добавление в график отпусков'
    })


@login_required
@director_required
def leave_schedule_edit(request, schedule_id):
    """Редактирование записи в графике отпусков"""
    
    leave = get_object_or_404(LeaveSchedule, id=schedule_id)
    
    if request.method == 'POST':
        form = LeaveScheduleForm(request.POST, request.FILES, instance=leave)
        if form.is_valid():
            form.save()
            messages.success(request, 'Запись обновлена!')
            return redirect('staff:leave_schedule_list')
    else:
        form = LeaveScheduleForm(instance=leave)
    
    return render(request, 'staff/leave_schedule_form.html', {
        'form': form,
        'leave': leave,
        'title': f'Редактирование отпуска {leave.employee.full_name}'
    })


@login_required
@director_required
def leave_requests(request):
    """Список заявлений на отпуск"""
    
    requests = LeaveRequest.objects.all().select_related('employee').order_by('-request_date')
    
    return render(request, 'staff/leave_requests.html', {
        'requests': requests
    })


@login_required
def leave_request_create(request):
    """Создание заявления на отпуск (для сотрудников)"""
    
    # Для заведующей показываем выбор сотрудника
    if request.user.role == 'director':
        employees = Employee.objects.filter(is_active=True)
        if request.method == 'POST':
            employee_id = request.POST.get('employee')
            employee = get_object_or_404(Employee, id=employee_id)
            
            form = LeaveRequestForm(request.POST)
            if form.is_valid():
                leave_request = form.save(commit=False)
                leave_request.employee = employee
                leave_request.save()
                messages.success(request, 'Заявление создано!')
                return redirect('staff:leave_requests')
        else:
            form = LeaveRequestForm()
        
        return render(request, 'staff/leave_request_form.html', {
            'form': form,
            'employees': employees
        })
    else:
        # Для обычных сотрудников (если добавить такую возможность)
        messages.error(request, 'Доступ запрещен')
        return redirect('dashboard')


@login_required
@director_required
def leave_request_process(request, request_id):
    """Обработка заявления на отпуск"""
    
    leave_request = get_object_or_404(LeaveRequest, id=request_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            # Утверждаем заявление
            leave_request.status = 'approved'
            leave_request.processed_date = date.today()
            leave_request.processed_by = request.user
            leave_request.save()
            
            # Создаем запись в графике отпусков
            LeaveSchedule.objects.create(
                employee=leave_request.employee,
                year=leave_request.start_date.year,
                leave_type=leave_request.leave_type,
                start_date=leave_request.start_date,
                end_date=leave_request.end_date,
                duration=leave_request.duration,
                status='approved',
                application_date=leave_request.request_date,
                notes=f"Создано из заявления #{leave_request.id}"
            )
            
            messages.success(request, 'Заявление утверждено')
            
        elif action == 'reject':
            leave_request.status = 'rejected'
            leave_request.processed_date = date.today()
            leave_request.processed_by = request.user
            leave_request.save()
            messages.success(request, 'Заявление отклонено')
        
        elif action == 'reschedule':
            # Перенос
            new_start = request.POST.get('new_start_date')
            new_end = request.POST.get('new_end_date')
            
            if new_start and new_end:
                leave_request.status = 'rescheduled'
                leave_request.processed_date = date.today()
                leave_request.processed_by = request.user
                leave_request.comments += f"\nПеренесено на {new_start} - {new_end}"
                leave_request.save()
                
                # Создаем новую запись с измененными датами
                LeaveSchedule.objects.create(
                    employee=leave_request.employee,
                    year=leave_request.start_date.year,
                    leave_type=leave_request.leave_type,
                    start_date=new_start,
                    end_date=new_end,
                    duration=(datetime.strptime(new_end, '%Y-%m-%d').date() - datetime.strptime(new_start, '%Y-%m-%d').date()).days + 1,
                    status='planned',
                    application_date=leave_request.request_date,
                    notes=f"Перенесено из заявления #{leave_request.id}"
                )
                
                messages.success(request, 'Отпуск перенесен')
        
        return redirect('staff:leave_requests')
    
    return render(request, 'staff/leave_request_process.html', {
        'leave_request': leave_request
    })


# ==================== ДИСЦИПЛИНАРНЫЕ ВЗЫСКАНИЯ И ПООЩРЕНИЯ ====================

@login_required
@director_required
def discipline_dashboard(request):
    """Панель дисциплинарных взысканий и поощрений"""
    
    # Активные взыскания
    active_actions = DisciplinaryAction.objects.filter(is_active=True).select_related('employee').order_by('valid_until')
    
    # Истекающие взыскания (скоро снимутся)
    expiring_actions = active_actions.filter(
        valid_until__lte=date.today() + timedelta(days=30)
    )
    
    # Поощрения за последний год
    recent_encouragements = Encouragement.objects.filter(
        order_date__gte=date.today() - timedelta(days=365)
    ).select_related('employee').order_by('-order_date')
    
    # Статистика
    total_actions = DisciplinaryAction.objects.count()
    total_encouragements = Encouragement.objects.count()
    
    # Сотрудники с нарушениями
    employees_with_actions = Employee.objects.filter(
        disciplinaryaction__is_active=True
    ).distinct().count()
    
    context = {
        'active_actions': active_actions,
        'expiring_actions': expiring_actions,
        'recent_encouragements': recent_encouragements,
        'total_actions': total_actions,
        'total_encouragements': total_encouragements,
        'employees_with_actions': employees_with_actions,
    }
    
    return render(request, 'staff/discipline_dashboard.html', context)


@login_required
@director_required
def disciplinary_actions_list(request):
    """Список дисциплинарных взысканий"""
    
    actions = DisciplinaryAction.objects.all().select_related('employee').order_by('-order_date')
    
    # Фильтры
    is_active = request.GET.get('is_active', '')
    if is_active == 'active':
        actions = actions.filter(is_active=True)
    elif is_active == 'inactive':
        actions = actions.filter(is_active=False)
    
    return render(request, 'staff/disciplinary_actions_list.html', {
        'actions': actions
    })


@login_required
@director_required
def disciplinary_action_add(request, employee_id):
    """Добавление дисциплинарного взыскания"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = DisciplinaryActionForm(request.POST, request.FILES)
        if form.is_valid():
            action = form.save(commit=False)
            action.employee = employee
            action.save()
            messages.success(request, 'Взыскание добавлено!')
            return redirect('staff:employee_detail', employee_id=employee.id)
    else:
        # Предзаполняем дату окончания (через год)
        form = DisciplinaryActionForm(initial={
            'issue_date': date.today(),
            'valid_until': date.today() + timedelta(days=365)
        })
    
    return render(request, 'staff/disciplinary_action_form.html', {
        'form': form,
        'employee': employee
    })


@login_required
@director_required
def disciplinary_action_edit(request, action_id):
    """Редактирование взыскания"""
    
    action = get_object_or_404(DisciplinaryAction, id=action_id)
    
    if request.method == 'POST':
        form = DisciplinaryActionForm(request.POST, request.FILES, instance=action)
        if form.is_valid():
            form.save()
            messages.success(request, 'Взыскание обновлено!')
            return redirect('staff:employee_detail', employee_id=action.employee.id)
    else:
        form = DisciplinaryActionForm(instance=action)
    
    return render(request, 'staff/disciplinary_action_form.html', {
        'form': form,
        'action': action,
        'employee': action.employee
    })


@login_required
@director_required
def disciplinary_action_lift(request, action_id):
    """Снятие дисциплинарного взыскания досрочно"""
    
    action = get_object_or_404(DisciplinaryAction, id=action_id)
    
    if request.method == 'POST':
        action.is_active = False
        action.lifted_date = date.today()
        action.lifted_by = request.user
        action.lifting_order = request.POST.get('lifting_order', '')
        action.save()
        
        messages.success(request, 'Взыскание снято!')
        return redirect('staff:employee_detail', employee_id=action.employee.id)
    
    return render(request, 'staff/disciplinary_action_lift.html', {
        'action': action
    })


@login_required
@director_required
def encouragements_list(request):
    """Список поощрений"""
    
    encouragements = Encouragement.objects.all().select_related('employee').order_by('-order_date')
    
    return render(request, 'staff/encouragements_list.html', {
        'encouragements': encouragements
    })


@login_required
@director_required
def encouragement_add(request, employee_id):
    """Добавление поощрения"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = EncouragementForm(request.POST, request.FILES)
        if form.is_valid():
            encouragement = form.save(commit=False)
            encouragement.employee = employee
            encouragement.save()
            messages.success(request, 'Поощрение добавлено!')
            return redirect('staff:employee_detail', employee_id=employee.id)
    else:
        form = EncouragementForm()
    
    return render(request, 'staff/encouragement_form.html', {
        'form': form,
        'employee': employee
    })


@login_required
@director_required
def encouragement_edit(request, enc_id):
    """Редактирование поощрения"""
    
    encouragement = get_object_or_404(Encouragement, id=enc_id)
    
    if request.method == 'POST':
        form = EncouragementForm(request.POST, request.FILES, instance=encouragement)
        if form.is_valid():
            form.save()
            messages.success(request, 'Поощрение обновлено!')
            return redirect('staff:employee_detail', employee_id=encouragement.employee.id)
    else:
        form = EncouragementForm(instance=encouragement)
    
    return render(request, 'staff/encouragement_form.html', {
        'form': form,
        'encouragement': encouragement,
        'employee': encouragement.employee
    })


# ==================== ДИСПАНСЕРИЗАЦИЯ ====================

@login_required
@director_required
def dispensary_list(request):
    """Список записей о диспансеризации"""
    
    records = DispensaryRecord.objects.all().select_related('employee').order_by('-year')
    
    return render(request, 'staff/dispensary_list.html', {
        'records': records
    })


@login_required
@director_required
def dispensary_add(request, employee_id):
    """Добавление записи о диспансеризации"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = DispensaryRecordForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save(commit=False)
            record.employee = employee
            record.save()
            messages.success(request, 'Запись о диспансеризации добавлена!')
            return redirect('staff:employee_detail', employee_id=employee.id)
    else:
        form = DispensaryRecordForm(initial={'year': date.today().year})
    
    return render(request, 'staff/dispensary_form.html', {
        'form': form,
        'employee': employee
    })


@login_required
@director_required
def dispensary_edit(request, record_id):
    """Редактирование записи о диспансеризации"""
    
    record = get_object_or_404(DispensaryRecord, id=record_id)
    
    if request.method == 'POST':
        form = DispensaryRecordForm(request.POST, request.FILES, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, 'Запись обновлена!')
            return redirect('staff:employee_detail', employee_id=record.employee.id)
    else:
        form = DispensaryRecordForm(instance=record)
    
    return render(request, 'staff/dispensary_form.html', {
        'form': form,
        'record': record,
        'employee': record.employee
    })


# ==================== РАСЧЕТ ЗАРАБОТНОЙ ПЛАТЫ ====================

@login_required
@director_required
def salary_dashboard(request):
    """Панель расчета зарплаты"""
    
    current_month = date.today().month
    current_year = date.today().year
    
    # Получаем параметры из GET запроса
    month = request.GET.get('month', current_month)
    year = request.GET.get('year', current_year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = current_month
        year = current_year
    
    # Расчеты за выбранный месяц
    current_calculations = SalaryCalculation.objects.filter(
        month=month,
        year=year
    ).select_related('employee')
    
    # Статистика
    total_payroll = current_calculations.aggregate(total=Sum('total_payable'))['total'] or 0
    employees_count = current_calculations.count()
    
    total_accrued = current_calculations.aggregate(total=Sum('total_accrued'))['total'] or 0
    total_tax = current_calculations.aggregate(total=Sum('income_tax'))['total'] or 0
    total_payable = current_calculations.aggregate(total=Sum('total_payable'))['total'] or 0
    
    # Предыдущие месяцы для навигации
    previous_months = SalaryCalculation.objects.values('month', 'year').distinct().order_by('-year', '-month')[:6]
    
    # Добавляем названия месяцев
    months_names = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    
    for item in previous_months:
        item['month_name'] = months_names.get(item['month'], '')
    
    context = {
        'current_month': month,
        'current_year': year,
        'current_calculations': current_calculations,
        'total_payroll': total_payroll,
        'employees_count': employees_count,
        'total_accrued': total_accrued,
        'total_tax': total_tax,
        'total_payable': total_payable,
        'previous_months': previous_months,
        'month_name': months_names.get(month, ''),
    }
    
    return render(request, 'staff/salary_dashboard.html', context)


@login_required
@director_required
def salary_calculate(request):
    """Расчет зарплаты за месяц"""
    
    if request.method == 'POST':
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        
        # Получаем табель за этот месяц
        timesheet = Timesheet.objects.filter(month=month, year=year).first()
        
        if not timesheet:
            messages.error(request, f'Сначала создайте табель за {month}.{year}')
            return redirect('staff:timesheet_create')
        
        if not timesheet.is_closed:
            messages.warning(request, 'Табель еще не закрыт. Рекомендуется закрыть табель перед расчетом зарплаты')
        
        # Получаем всех активных сотрудников на этот месяц
        employees = Employee.objects.filter(
            Q(dismissal_date__isnull=True) | Q(dismissal_date__gte=date(year, month, 1))
        )
        
        calculations_created = 0
        calculations_updated = 0
        
        for employee in employees:
            # Получаем запись в табеле
            timesheet_entry = TimesheetEntry.objects.filter(
                timesheet=timesheet,
                employee=employee
            ).first()
            
            if not timesheet_entry:
                continue
            
            # Получаем штатную единицу сотрудника
            staff_unit = StaffUnit.objects.filter(employee=employee).first()
            
            if not staff_unit or not staff_unit.position:
                # Если нет штатной единицы, используем базовый оклад из должности
                base_salary = Decimal('30000.00')
            else:
                base_salary = staff_unit.calculated_salary  # Это уже Decimal
            
            # Расчет отработанных часов
            worked_hours = Decimal(str(timesheet_entry.total_hours))
            standard_hours = Decimal(str(timesheet_entry.total_days * 8))
            
            # Часовая ставка
            if standard_hours > 0:
                hourly_rate = base_salary / standard_hours
            else:
                hourly_rate = Decimal('0')
            
            # Расчет выплат
            base_payment = hourly_rate * worked_hours
            
            # Сверхурочные (коэффициент 1.5)
            overtime_hours = Decimal(str(timesheet_entry.overtime_hours))
            overtime_payment = hourly_rate * overtime_hours * Decimal('1.5')
            
            # Ночные (коэффициент 1.2)
            night_hours = Decimal(str(timesheet_entry.night_hours))
            night_payment = hourly_rate * night_hours * Decimal('1.2')
            
            # Праздничные (коэффициент 2)
            holiday_hours = Decimal(str(timesheet_entry.holiday_hours))
            holiday_payment = hourly_rate * holiday_hours * Decimal('2')
            
            # Стимулирующие выплаты (пока 0)
            stimulating_payments = Decimal('0')
            
            # Больничные и отпускные (пока 0)
            sick_leave = Decimal('0')
            vacation_pay = Decimal('0')
            
            total_accrued = (base_payment + overtime_payment + night_payment + 
                           holiday_payment + stimulating_payments + sick_leave + vacation_pay)
            
            # НДФЛ 13%
            income_tax = total_accrued * Decimal('0.13')
            total_payable = total_accrued - income_tax
            
            # Создаем или обновляем расчет
            calculation, created = SalaryCalculation.objects.update_or_create(
                employee=employee,
                month=month,
                year=year,
                defaults={
                    'timesheet': timesheet,
                    'base_salary': base_salary,
                    'worked_hours': worked_hours,
                    'standard_hours': standard_hours,
                    'overtime_payment': overtime_payment,
                    'night_payment': night_payment,
                    'holiday_payment': holiday_payment,
                    'stimulating_payments': stimulating_payments,
                    'sick_leave': sick_leave,
                    'vacation_pay': vacation_pay,
                    'total_accrued': total_accrued,
                    'income_tax': income_tax,
                    'total_payable': total_payable,
                    'status': 'calculated'
                }
            )
            
            if created:
                calculations_created += 1
            else:
                calculations_updated += 1
        
        messages.success(
            request, 
            f'Расчет зарплаты выполнен! Создано: {calculations_created}, обновлено: {calculations_updated}'
        )
        return redirect('staff:salary_dashboard')
    
    # GET запрос - показываем форму
    today = date.today()
    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    years = range(today.year - 1, today.year + 2)
    
    context = {
        'current_month': today.month,
        'current_year': today.year,
        'months': months,
        'years': years,
    }
    
    return render(request, 'staff/salary_calculate_form.html', context)


@login_required
@director_required
def salary_calculations_list(request):
    """Список расчетов зарплаты"""
    
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = date.today().month
        year = date.today().year
    
    calculations = SalaryCalculation.objects.filter(
        month=month,
        year=year
    ).select_related('employee').order_by('employee__full_name')
    
    # Итоговая сумма
    total_payroll = calculations.aggregate(total=Sum('total_payable'))['total'] or 0
    
    context = {
        'calculations': calculations,
        'month': month,
        'year': year,
        'total_payroll': total_payroll,
        'month_name': calendar.month_name[month],
    }
    
    return render(request, 'staff/salary_calculations_list.html', context)


@login_required
@director_required
def salary_detail(request, calc_id):
    """Детали расчета зарплаты"""
    
    calculation = get_object_or_404(SalaryCalculation, id=calc_id)
    components = SalaryComponent.objects.filter(salary_calculation=calculation)
    
    return render(request, 'staff/salary_detail.html', {
        'calculation': calculation,
        'components': components
    })


@login_required
@director_required
def salary_approve(request, calc_id):
    """Утверждение расчета зарплаты"""
    
    calculation = get_object_or_404(SalaryCalculation, id=calc_id)
    
    if request.method == 'POST':
        calculation.status = 'approved'
        calculation.save()
        messages.success(request, 'Расчет утвержден')
    
    return redirect('staff:salary_detail', calc_id=calc_id)


@login_required
@director_required
def payroll_register(request):
    """Реестр на выплату зарплаты"""
    
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = date.today().month
        year = date.today().year
    
    calculations = SalaryCalculation.objects.filter(
        month=month,
        year=year
    ).select_related('employee').order_by('employee__full_name')
    
    total_amount = calculations.aggregate(total=Sum('total_payable'))['total'] or 0
    
    if request.method == 'POST':
        # Отметка о выплате
        for calc in calculations:
            calc.status = 'paid'
            calc.payment_date = date.today()
            calc.save()
        
        messages.success(request, 'Выплата зарплаты зарегистрирована')
        return redirect('staff:payroll_register')
    
    context = {
        'calculations': calculations,
        'month': month,
        'year': year,
        'total_amount': total_amount,
        'month_name': calendar.month_name[month],
    }
    
    return render(request, 'staff/payroll_register.html', context)


# ==================== ОТЧЕТЫ ====================

@login_required
@director_required
def staff_list_report(request):
    """Отчет - список сотрудников"""
    
    employees = Employee.objects.filter(is_active=True).order_by('employee_type', 'full_name')
    
    return render(request, 'staff/reports/staff_list.html', {
        'employees': employees,
        'generated_at': timezone.now(),
    })


@login_required
@director_required
def expiring_documents_report(request):
    """Отчет - истекающие документы"""
    
    today = date.today()
    thirty_days = today + timedelta(days=30)
    
    # Медосмотры
    medical = MedicalExamination.objects.filter(
        valid_until__lte=thirty_days
    ).select_related('employee').order_by('valid_until')
    
    # Справки о несудимости
    criminal = CriminalRecordCheck.objects.filter(
        valid_until__lte=thirty_days
    ).select_related('employee').order_by('valid_until')
    
    # Аттестации
    attestations = Attestation.objects.filter(
        valid_until__lte=thirty_days
    ).select_related('employee').order_by('valid_until')
    
    # Договоры
    contracts = LaborContract.objects.filter(
        contract_type='fixed_term',
        end_date__lte=thirty_days,
        is_active=True
    ).select_related('employee').order_by('end_date')
    
    context = {
        'medical': medical,
        'criminal': criminal,
        'attestations': attestations,
        'contracts': contracts,
        'today': today,
        'thirty_days': thirty_days,
        'generated_at': timezone.now(),
    }
    
    return render(request, 'staff/reports/expiring_documents.html', context)


@login_required
@director_required
def attestations_report(request):
    """Отчет - аттестации педагогических работников"""
    
    year = request.GET.get('year', date.today().year)
    
    try:
        year = int(year)
    except ValueError:
        year = date.today().year
    
    # Аттестации за год
    attestations = Attestation.objects.filter(
        attestation_date__year=year
    ).select_related('employee').order_by('attestation_date')
    
    # Группировка по результатам
    by_result = {}
    for result_code, result_name in Attestation.ATTESTATION_RESULTS:
        count = attestations.filter(result=result_code).count()
        if count > 0:
            by_result[result_name] = count
    
    context = {
        'attestations': attestations,
        'year': year,
        'by_result': by_result,
        'generated_at': timezone.now(),
    }
    
    return render(request, 'staff/reports/attestations.html', context)


@login_required
@director_required
def leave_schedule_report(request):
    """Отчет - график отпусков на год"""
    
    year = request.GET.get('year', date.today().year)
    
    try:
        year = int(year)
    except ValueError:
        year = date.today().year
    
    leave_schedule = LeaveSchedule.objects.filter(
        year=year
    ).select_related('employee').order_by('start_date')
    
    # Статистика по месяцам
    by_month = {}
    for i in range(1, 13):
        month_leaves = leave_schedule.filter(start_date__month=i)
        if month_leaves.exists():
            by_month[calendar.month_name[i]] = month_leaves.count()
    
    context = {
        'leave_schedule': leave_schedule,
        'year': year,
        'by_month': by_month,
        'generated_at': timezone.now(),
    }
    
    return render(request, 'staff/reports/leave_schedule.html', context)


@login_required
@director_required
def timesheet_summary_report(request):
    """Отчет - сводка по табелю"""
    
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = date.today().month
        year = date.today().year
    
    timesheet = Timesheet.objects.filter(month=month, year=year).first()
    
    if timesheet:
        entries = TimesheetEntry.objects.filter(timesheet=timesheet).select_related('employee')
        
        # Сводка
        total_employees = entries.count()
        total_days = entries.aggregate(total=Sum('total_days'))['total'] or 0
        total_hours = entries.aggregate(total=Sum('total_hours'))['total'] or 0
        total_overtime = entries.aggregate(total=Sum('overtime_hours'))['total'] or 0
        
        context = {
            'timesheet': timesheet,
            'entries': entries,
            'total_employees': total_employees,
            'total_days': total_days,
            'total_hours': total_hours,
            'total_overtime': total_overtime,
            'month': month,
            'year': year,
            'month_name': calendar.month_name[month],
            'generated_at': timezone.now(),
        }
    else:
        context = {
            'timesheet': None,
            'month': month,
            'year': year,
            'month_name': calendar.month_name[month],
            'generated_at': timezone.now(),
        }
    
    return render(request, 'staff/reports/timesheet_summary.html', context)


# ==================== AJAX ====================

@login_required
@director_required
def check_document_expiry_ajax(request):
    """AJAX - проверка истечения документов"""
    
    today = date.today()
    
    # Медосмотры
    expiring_medical = MedicalExamination.objects.filter(
        valid_until__lte=today + timedelta(days=30),
        valid_until__gte=today
    ).count()
    
    expired_medical = MedicalExamination.objects.filter(
        valid_until__lt=today
    ).count()
    
    # Справки о несудимости
    expiring_criminal = CriminalRecordCheck.objects.filter(
        valid_until__lte=today + timedelta(days=30),
        valid_until__gte=today
    ).count()
    
    expired_criminal = CriminalRecordCheck.objects.filter(
        valid_until__lt=today
    ).count()
    
    return JsonResponse({
        'expiring_medical': expiring_medical,
        'expired_medical': expired_medical,
        'expiring_criminal': expiring_criminal,
        'expired_criminal': expired_criminal,
        'total_expiring': expiring_medical + expiring_criminal,
        'total_expired': expired_medical + expired_criminal,
    })


@login_required
@director_required
def get_employee_contracts_ajax(request):
    """AJAX - получение договоров сотрудника"""
    
    employee_id = request.GET.get('employee_id')
    
    if not employee_id:
        return JsonResponse({'error': 'No employee_id'}, status=400)
    
    contracts = LaborContract.objects.filter(
        employee_id=employee_id,
        is_active=True
    ).values('id', 'contract_number', 'contract_type', 'start_date', 'end_date')
    
    return JsonResponse({'contracts': list(contracts)})


@login_required
@director_required
def calculate_salary_ajax(request):
    """AJAX - предварительный расчет зарплаты"""
    
    employee_id = request.GET.get('employee_id')
    month = request.GET.get('month')
    year = request.GET.get('year')
    
    if not all([employee_id, month, year]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        employee = Employee.objects.get(id=employee_id)
        month = int(month)
        year = int(year)
        
        # Получаем табель
        timesheet = Timesheet.objects.filter(month=month, year=year).first()
        
        if not timesheet:
            return JsonResponse({'error': 'Timesheet not found'}, status=404)
        
        # Получаем запись в табеле
        entry = TimesheetEntry.objects.filter(
            timesheet=timesheet,
            employee=employee
        ).first()
        
        if not entry:
            return JsonResponse({'error': 'Timesheet entry not found'}, status=404)
        
        # Получаем штатную единицу
        staff_unit = StaffUnit.objects.filter(employee=employee).first()
        base_salary = staff_unit.calculated_salary if staff_unit else 30000
        
        # Расчет
        standard_hours = entry.total_days * 8
        hourly_rate = base_salary / standard_hours if standard_hours > 0 else 0
        
        base_payment = hourly_rate * entry.total_hours
        overtime_payment = entry.overtime_hours * hourly_rate * 1.5
        night_payment = entry.night_hours * hourly_rate * 1.2
        holiday_payment = entry.holiday_hours * hourly_rate * 2
        
        total_accrued = base_payment + overtime_payment + night_payment + holiday_payment
        total_payable = total_accrued * Decimal('0.87')  # После НДФЛ
        
        return JsonResponse({
            'employee_name': employee.full_name,
            'base_salary': float(base_salary),
            'worked_hours': float(entry.total_hours),
            'standard_hours': float(standard_hours),
            'base_payment': float(base_payment),
            'overtime_payment': float(overtime_payment),
            'night_payment': float(night_payment),
            'holiday_payment': float(holiday_payment),
            'total_accrued': float(total_accrued),
            'total_payable': float(total_payable),
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@director_required
def export_staff_list_excel(request):
    """Экспорт списка сотрудников в Excel"""
    
    employees = Employee.objects.filter(is_active=True).order_by('employee_type', 'full_name')
    
    # Создаем workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Сотрудники"
    
    # Заголовок
    title = ws.cell(row=1, column=1, value="Список сотрудников МБДОУ 'Рябинушка'")
    title.font = Font(size=14, bold=True)
    ws.merge_cells('A1:G1')
    
    # Дата формирования
    date_cell = ws.cell(row=2, column=1, value=f"Сформировано: {timezone.now().strftime('%d.%m.%Y %H:%M')}")
    date_cell.font = Font(size=10, italic=True)
    ws.merge_cells('A2:G2')
    
    # Заголовки столбцов
    headers = ['ФИО', 'Должность', 'Категория', 'Телефон', 'Email', 'Дата приема', 'Стаж']
    header_row = 4
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
        cell.alignment = Alignment(horizontal='center')
    
    # Данные
    row = header_row + 1
    for employee in employees:
        ws.cell(row=row, column=1, value=employee.full_name)
        ws.cell(row=row, column=2, value=employee.position)
        ws.cell(row=row, column=3, value=employee.get_employee_type_display())
        ws.cell(row=row, column=4, value=employee.phone)
        ws.cell(row=row, column=5, value=employee.email)
        ws.cell(row=row, column=6, value=employee.hire_date.strftime('%d.%m.%Y'))
        ws.cell(row=row, column=7, value=f"{employee.experience} лет")
        row += 1
    
    # Настройка ширины столбцов
    column_widths = [30, 25, 20, 15, 25, 15, 10]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    
    # Создаем response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=staff_list_{date.today()}.xlsx'
    
    wb.save(response)
    return response


@login_required
@director_required
def export_leave_schedule_pdf(request):
    """Экспорт графика отпусков в PDF"""
    
    year = request.GET.get('year', date.today().year)
    
    try:
        year = int(year)
    except ValueError:
        year = date.today().year
    
    leave_schedule = LeaveSchedule.objects.filter(
        year=year,
        status__in=['planned', 'approved']
    ).select_related('employee').order_by('start_date')
    
    # Создаем PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=leave_schedule_{year}.pdf'
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(A4))
    
    # Заголовок
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 550, f"График отпусков на {year} год")
    
    p.setFont("Helvetica", 10)
    p.drawString(50, 530, f"Сформировано: {timezone.now().strftime('%d.%m.%Y %H:%M')}")
    
    # Таблица
    data = [['№', 'ФИО сотрудника', 'Должность', 'Дата начала', 'Дата окончания', 'Дней', 'Тип отпуска']]
    
    for i, leave in enumerate(leave_schedule, 1):
        data.append([
            str(i),
            leave.employee.full_name,
            leave.employee.position,
            leave.start_date.strftime('%d.%m.%Y'),
            leave.end_date.strftime('%d.%m.%Y'),
            str(leave.duration),
            leave.get_leave_type_display()
        ])
    
    # Создаем таблицу
    table = Table(data, colWidths=[20, 80, 60, 50, 50, 30, 60])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    # Рисуем таблицу
    table.wrapOn(p, 500, 200)
    table.drawOn(p, 50, 400)
    
    p.showPage()
    p.save()
    
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response


@login_required
@director_required
def export_salary_payroll_excel(request):
    """Экспорт ведомости на выплату зарплаты в Excel"""
    
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = date.today().month
        year = date.today().year
    
    calculations = SalaryCalculation.objects.filter(
        month=month,
        year=year
    ).select_related('employee').order_by('employee__full_name')
    
    # Создаем workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Зарплата {month}.{year}"
    
    # Заголовок
    title = ws.cell(row=1, column=1, 
                   value=f"Расчетно-платежная ведомость за {calendar.month_name[month]} {year} года")
    title.font = Font(size=14, bold=True)
    ws.merge_cells('A1:K1')
    
    # Дата формирования
    date_cell = ws.cell(row=2, column=1, 
                       value=f"Сформировано: {timezone.now().strftime('%d.%m.%Y %H:%M')}")
    date_cell.font = Font(size=10, italic=True)
    ws.merge_cells('A2:K2')
    
    # Заголовки столбцов
    headers = [
        '№', 'ФИО', 'Должность', 'Оклад', 'Отработано часов',
        'Норма часов', 'Начислено', 'НДФЛ', 'К выплате', 'Подпись'
    ]
    header_row = 4
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
        cell.alignment = Alignment(horizontal='center')
    
    # Данные
    row = header_row + 1
    total_accrued = 0
    total_tax = 0
    total_payable = 0
    
    for i, calc in enumerate(calculations, 1):
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=calc.employee.full_name)
        ws.cell(row=row, column=3, value=calc.employee.position)
        ws.cell(row=row, column=4, value=float(calc.base_salary))
        ws.cell(row=row, column=5, value=float(calc.worked_hours))
        ws.cell(row=row, column=6, value=float(calc.standard_hours))
        ws.cell(row=row, column=7, value=float(calc.total_accrued))
        ws.cell(row=row, column=8, value=float(calc.total_accrued - calc.total_payable))
        ws.cell(row=row, column=9, value=float(calc.total_payable))
        ws.cell(row=row, column=10, value="")
        
        total_accrued += float(calc.total_accrued)
        total_tax += float(calc.total_accrued - calc.total_payable)
        total_payable += float(calc.total_payable)
        
        row += 1
    
    # Итоговая строка
    ws.cell(row=row, column=6, value="ИТОГО:")
    ws.cell(row=row, column=6).font = Font(bold=True)
    
    ws.cell(row=row, column=7, value=total_accrued)
    ws.cell(row=row, column=7).font = Font(bold=True)
    
    ws.cell(row=row, column=8, value=total_tax)
    ws.cell(row=row, column=8).font = Font(bold=True)
    
    ws.cell(row=row, column=9, value=total_payable)
    ws.cell(row=row, column=9).font = Font(bold=True)
    
    # Настройка ширины столбцов
    column_widths = [5, 30, 25, 12, 15, 12, 15, 12, 12, 15]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    
    # Форматирование чисел
    for col in [4, 7, 8, 9]:
        for r in range(header_row + 1, row + 1):
            cell = ws.cell(row=r, column=col)
            if isinstance(cell.value, (int, float)):
                cell.number_format = '#,##0.00'
    
    # Добавляем границы
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for r in range(header_row, row + 1):
        for c in range(1, 11):
            ws.cell(row=r, column=c).border = thin_border
    
    # Создаем response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=payroll_{month}_{year}.xlsx'
    
    wb.save(response)
    return response


# ==================== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ====================

def auto_lift_expired_disciplinary_actions():
    """
    Автоматическое снятие дисциплинарных взысканий по истечении срока
    """
    expired_actions = DisciplinaryAction.objects.filter(
        is_active=True,
        valid_until__lt=date.today()
    )
    
    count = 0
    for action in expired_actions:
        action.is_active = False
        action.lifted_date = date.today()
        action.notes += f"\nАвтоматически снято по истечении срока {date.today()}"
        action.save()
        count += 1
    
    return count


def send_document_expiry_notifications():
    """
    Отправка уведомлений об истечении срока документов
    """
    today = date.today()
    expiring_soon = today + timedelta(days=14)
    
    # Медосмотры
    expiring_medical = MedicalExamination.objects.filter(
        valid_until__lte=expiring_soon,
        valid_until__gte=today
    ).select_related('employee')
    
    # Справки о несудимости
    expiring_criminal = CriminalRecordCheck.objects.filter(
        valid_until__lte=expiring_soon,
        valid_until__gte=today
    ).select_related('employee')
    
    notifications = []
    
    for medical in expiring_medical:
        notifications.append({
            'employee': medical.employee.full_name,
            'document': 'Медицинский осмотр',
            'expiry_date': medical.valid_until,
            'days_left': (medical.valid_until - today).days
        })
    
    for criminal in expiring_criminal:
        notifications.append({
            'employee': criminal.employee.full_name,
            'document': 'Справка о несудимости',
            'expiry_date': criminal.valid_until,
            'days_left': (criminal.valid_until - today).days
        })
    
    return notifications


def get_staff_config():
    """
    Возвращает конфигурацию для кадрового учета
    """
    return {
        'employee_types': Employee.EMPLOYEE_TYPES,
        'leave_types': LeaveSchedule.LEAVE_TYPES,
        'disciplinary_types': DisciplinaryAction.ACTION_TYPES,
        'encouragement_types': Encouragement.ENCOURAGEMENT_TYPES,
        'attestation_results': Attestation.ATTESTATION_RESULTS,
        'attestation_categories': Attestation.CATEGORY_CHOICES,
        'education_levels': EducationDocument.EDUCATION_LEVELS,
        'contract_types': LaborContract.CONTRACT_TYPES,
        'schedule_types': WorkSchedule.SCHEDULE_TYPES,
        'position_categories': StaffPosition.POSITION_CATEGORIES,
    }


@login_required
@director_required
def generate_payslip(request, calc_id):
    """Генерация расчетного листка в PDF"""
    
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from datetime import date
        import io
        import os
        from django.conf import settings
        
        calculation = get_object_or_404(SalaryCalculation, id=calc_id)
        employee = calculation.employee
        
        # Получаем фамилию
        if employee.full_name:
            name_parts = employee.full_name.split()
            last_name = name_parts[0] if name_parts else "сотрудник"
        else:
            last_name = "сотрудник"
        
        # Регистрируем русский шрифт
        font_path = os.path.join(settings.BASE_DIR, 'fonts', 'DejaVuSans.ttf')
        if not os.path.exists(font_path):
            font_path = "C:\\Windows\\Fonts\\arial.ttf"
        
        try:
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path))
            use_russian_font = True
        except:
            use_russian_font = False
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        if use_russian_font:
            c.setFont("DejaVuSans", 10)
        else:
            c.setFont("Helvetica", 10)
        
        # Заголовок
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 18)
        else:
            c.setFont("Helvetica-Bold", 18)
        c.setFillColor(colors.HexColor('#4a6fa5'))
        c.drawString(50, height - 50, "МБДОУ 'Рябинушка'")
        
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 14)
        else:
            c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.black)
        c.drawString(50, height - 80, "Расчетный листок")
        
        # Линия
        c.setStrokeColor(colors.HexColor('#4a6fa5'))
        c.setLineWidth(2)
        c.line(50, height - 90, width - 50, height - 90)
        
        # Информация о сотруднике
        if use_russian_font:
            c.setFont("DejaVuSans", 10)
        else:
            c.setFont("Helvetica", 10)
        
        y = height - 120
        c.drawString(50, y, f"Сотрудник: {employee.full_name}")
        c.drawString(50, y - 20, f"Должность: {employee.position}")
        c.drawString(50, y - 40, f"Табельный номер: {employee.id:04d}")
        
        month_names = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        month_name = month_names.get(calculation.month, str(calculation.month))
        
        c.drawString(300, y, f"Период: {month_name} {calculation.year}")
        c.drawString(300, y - 20, f"Дата приема: {employee.hire_date.strftime('%d.%m.%Y')}")
        
        c.rect(45, height - 200, width - 90, 90)
        
        # Таблица начислений
        y = height - 230
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 11)
        else:
            c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor('#4a6fa5'))
        c.drawString(50, y, "НАЧИСЛЕНИЯ")
        
        y -= 20
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 10)
        else:
            c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.black)
        c.drawString(50, y, "Вид начисления")
        c.drawString(250, y, "Часы/Дни")
        c.drawString(350, y, "Сумма (руб.)")
        
        y -= 5
        c.line(50, y, width - 50, y)
        
        y -= 15
        if use_russian_font:
            c.setFont("DejaVuSans", 10)
        else:
            c.setFont("Helvetica", 10)
        
        c.drawString(55, y, "Оклад/Тарифная ставка")
        c.drawString(250, y, f"{calculation.worked_hours:.1f}/{calculation.standard_hours:.1f} ч.")
        c.drawRightString(width - 55, y, f"{calculation.base_salary:.2f}")
        
        if calculation.overtime_payment and calculation.overtime_payment > 0:
            y -= 15
            c.drawString(55, y, "Сверхурочная работа")
            c.drawString(250, y, f"{calculation.overtime_hours:.1f} ч.")
            c.drawRightString(width - 55, y, f"{calculation.overtime_payment:.2f}")
        
        if calculation.night_payment and calculation.night_payment > 0:
            y -= 15
            c.drawString(55, y, "Ночные часы")
            c.drawString(250, y, f"{calculation.night_hours:.1f} ч.")
            c.drawRightString(width - 55, y, f"{calculation.night_payment:.2f}")
        
        if calculation.holiday_payment and calculation.holiday_payment > 0:
            y -= 15
            c.drawString(55, y, "Праздничные дни")
            c.drawString(250, y, f"{calculation.holiday_hours:.1f} ч.")
            c.drawRightString(width - 55, y, f"{calculation.holiday_payment:.2f}")
        
        if calculation.stimulating_payments and calculation.stimulating_payments > 0:
            y -= 15
            c.drawString(55, y, "Стимулирующие выплаты")
            c.drawString(250, y, "-")
            c.drawRightString(width - 55, y, f"{calculation.stimulating_payments:.2f}")
        
        y -= 10
        c.line(50, y, width - 50, y)
        
        y -= 15
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 10)
        else:
            c.setFont("Helvetica-Bold", 10)
        c.drawString(55, y, "ИТОГО НАЧИСЛЕНО")
        c.drawRightString(width - 55, y, f"{calculation.total_accrued:.2f}")
        
        y -= 15
        if use_russian_font:
            c.setFont("DejaVuSans", 10)
        else:
            c.setFont("Helvetica", 10)
        c.drawString(55, y, "НДФЛ (13%)")
        c.drawRightString(width - 55, y, f"- {calculation.income_tax:.2f}")
        
        y -= 25
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 12)
        else:
            c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor('#27ae60'))
        c.drawString(55, y, "К ВЫПЛАТЕ:")
        c.drawRightString(width - 55, y, f"{calculation.total_payable:.2f} руб.")
        
        # Подписи
        c.setFillColor(colors.black)
        if use_russian_font:
            c.setFont("DejaVuSans", 9)
        else:
            c.setFont("Helvetica", 9)
        
        c.line(50, 120, 200, 120)
        c.line(50, 80, 200, 80)
        
        c.drawString(50, 100, "Главный бухгалтер")
        c.drawString(210, 100, "___________________ /Петрова Е.И./")
        
        c.drawString(50, 60, "Заведующая МБДОУ")
        c.drawString(210, 60, "___________________ /Михайлова Н.В./")
        
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor('#666666'))
        c.drawString(width - 150, 40, f"Дата формирования: {date.today().strftime('%d.%m.%Y')}")
        
        c.showPage()
        c.save()
        
        pdf = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"raschetny_listok_{last_name}_{calculation.month}_{calculation.year}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        import traceback
        error_msg = f"Ошибка при генерации PDF: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return HttpResponse(error_msg, content_type='text/plain', status=500)


@login_required
@director_required
def invite_employee(request, employee_id):
    """Отправка приглашения сотруднику"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if not employee.email:
        messages.error(request, 'У сотрудника не указан email')
        return redirect('staff:employee_detail', employee_id=employee.id)
    
    # Генерируем уникальный токен
    token = uuid.uuid4().hex
    employee.invite_token = token
    employee.invite_sent_at = timezone.now()
    employee.save()
    
    # Создаем ссылку для активации
    activation_link = request.build_absolute_uri(
        reverse('staff:accept_invite', kwargs={'token': token})
    )
    
    # Отправляем email
    subject = 'Приглашение в систему МБДОУ "Рябинушка"'
    html_message = render_to_string('staff/email/invite_email.html', {
        'employee': employee,
        'activation_link': activation_link,
        'site_name': 'МБДОУ "Рябинушка"',
    })
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [employee.email],
            html_message=html_message,
            fail_silently=False,
        )
        messages.success(
            request, 
            f'Приглашение отправлено на email {employee.email}'
        )
    except Exception as e:
        messages.error(request, f'Ошибка при отправке email: {str(e)}')
    
    return redirect('staff:employee_detail', employee_id=employee.id)


# staff/views.py - исправленная функция accept_invite

# staff/views.py

from django.contrib.auth import login as auth_login  # ДОБАВЬТЕ ЭТОТ ИМПОРТ

def accept_invite(request, token):
    """Принятие приглашения сотрудником"""
    
    employee = get_object_or_404(Employee, invite_token=token)
    
    # Проверяем, не истекло ли приглашение
    if employee.invite_sent_at:
        days_passed = (timezone.now() - employee.invite_sent_at).days
        if days_passed > 7:
            messages.error(request, 'Срок действия приглашения истек. Обратитесь к заведующей.')
            return redirect('accounts:login')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password1')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        if password != password2:
            messages.error(request, 'Пароли не совпадают')
            return render(request, 'staff/accept_invite.html', {'employee': employee, 'token': token})
        
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким логином уже существует')
            return render(request, 'staff/accept_invite.html', {'employee': employee, 'token': token})
        
        phone = employee.phone
        if phone:
            phone = ''.join(filter(str.isdigit, phone))
            phone = phone[:20]
        else:
            phone = ''
        
        role_mapping = {
            'teacher': 'teacher',
            'assistant': 'teacher',
            'music_director': 'teacher',
            'physical_instructor': 'teacher',
            'psychologist': 'teacher',
            'speech_therapist': 'teacher',
            'administrative': 'director',
        }
        role = role_mapping.get(employee.employee_type, 'teacher')
        
        try:
            # Проверяем, существует ли пользователь с таким email
            existing_user = CustomUser.objects.filter(email=employee.email).first()
            
            if existing_user:
                # Обновляем существующего пользователя
                existing_user.set_password(password)
                existing_user.first_name = first_name or existing_user.first_name
                existing_user.last_name = last_name or existing_user.last_name
                existing_user.role = role
                existing_user.phone = phone
                existing_user.email_verified = True
                existing_user.save()
                user = existing_user
            else:
                # Создаем нового пользователя
                user = CustomUser.objects.create_user(
                    username=username,
                    email=employee.email,
                    password=password,
                    first_name=first_name or '',
                    last_name=last_name or '',
                    role=role,
                    phone=phone,
                    address=employee.address[:200] if employee.address else '',
                    birth_date=employee.birth_date,
                    email_verified=True,
                )
            
            # Связываем пользователя с сотрудником
            employee.user = user
            employee.invite_accepted_at = timezone.now()
            employee.invite_token = None
            employee.save()
            
            # Авторизуем пользователя
            auth_login(request, user)  # ИСПРАВЛЕНО: используем auth_login вместо login
            
            messages.success(request, 'Аккаунт успешно создан! Добро пожаловать в систему.')
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f'Ошибка при создании аккаунта: {str(e)}')
            return render(request, 'staff/accept_invite.html', {'employee': employee, 'token': token})
    
    return render(request, 'staff/accept_invite.html', {'employee': employee, 'token': token})


@login_required
def employee_profile(request):
    """Профиль сотрудника"""
    
    try:
        employee = request.user.employee_profile
    except Employee.DoesNotExist:
        messages.error(request, 'Профиль сотрудника не найден')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = EmployeeProfileForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен')
            return redirect('staff:employee_profile')
    else:
        form = EmployeeProfileForm(instance=employee)
    
    return render(request, 'staff/employee_profile.html', {
        'employee': employee,
        'form': form,
    })


@login_required
def change_photo(request):
    """Изменение фото профиля"""
    
    try:
        employee = request.user.employee_profile
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Сотрудник не найден'})
    
    if request.method == 'POST' and request.FILES.get('photo'):
        employee.photo = request.FILES['photo']
        employee.save()
        
        return JsonResponse({
            'success': True,
            'photo_url': employee.photo.url
        })
    
    return JsonResponse({'success': False, 'error': 'Нет файла'})


@login_required
def change_password(request):
    """Смена пароля"""
    
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            user = request.user
            if user.check_password(form.cleaned_data['old_password']):
                user.set_password(form.cleaned_data['new_password'])
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Пароль успешно изменен')
                return redirect('staff:employee_profile')
            else:
                messages.error(request, 'Неверный текущий пароль')
    else:
        form = ChangePasswordForm()
    
    return render(request, 'staff/change_password.html', {'form': form})

from .models import HireOrder
from .forms import HireOrderForm


@login_required
@director_required
def hire_order_create(request, employee_id):
    """Создание приказа о приеме на работу"""
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = HireOrderForm(request.POST, employee=employee)
        if form.is_valid():
            order = form.save(commit=False)
            order.employee = employee
            order.created_by = request.user
            order.save()
            
            messages.success(request, f'Приказ №{order.order_number} успешно создан!')
            return redirect('staff:hire_order_detail', order_id=order.id)
    else:
        form = HireOrderForm(employee=employee)
    
    return render(request, 'staff/hire_order_form.html', {
        'form': form,
        'employee': employee,
        'title': f'Создание приказа о приеме: {employee.full_name}',
    })


@login_required
@director_required
def hire_order_detail(request, order_id):
    """Детальная страница приказа"""
    
    order = get_object_or_404(HireOrder, id=order_id)
    
    return render(request, 'staff/hire_order_detail.html', {
        'order': order,
    })


@login_required
@director_required
def hire_order_list(request):
    """Список всех приказов о приеме"""
    
    orders = HireOrder.objects.all().select_related('employee').order_by('-order_date', '-order_number')
    
    # Фильтры
    year = request.GET.get('year', date.today().year)
    month = request.GET.get('month', '')
    
    if year:
        orders = orders.filter(order_date__year=year)
    if month:
        orders = orders.filter(order_date__month=month)
    
    years = HireOrder.objects.dates('order_date', 'year', order='DESC')
    
    context = {
        'orders': orders,
        'years': years,
        'current_year': year,
        'current_month': month,
    }
    
    return render(request, 'staff/hire_order_list.html', context)


@login_required
@director_required
def hire_order_generate_pdf(request, order_id):
    """Генерация PDF приказа по форме Т-1"""
    
    order = get_object_or_404(HireOrder, id=order_id)
    
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import io
        import os
        from django.conf import settings
        from datetime import datetime
        
        # Разбираем ФИО из full_name
        full_name = order.employee.full_name
        name_parts = full_name.split()
        
        last_name = name_parts[0] if len(name_parts) > 0 else ''
        first_name = name_parts[1] if len(name_parts) > 1 else ''
        patronymic = name_parts[2] if len(name_parts) > 2 else ''
        
        # Функция для преобразования числа в пропись
        def number_to_words(num):
            units = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
            teens = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать',
                    'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']
            tens = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 
                   'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
            hundreds = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 
                       'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']
            
            if num == 0:
                return 'ноль'
            
            words = []
            
            # Сотни
            hundred = num // 100
            if hundred > 0:
                words.append(hundreds[hundred])
            
            # Десятки и единицы
            remainder = num % 100
            if 10 <= remainder <= 19:
                words.append(teens[remainder - 10])
            else:
                ten = remainder // 10
                if ten > 0:
                    words.append(tens[ten])
                unit = remainder % 10
                if unit > 0:
                    words.append(units[unit])
            
            return ' '.join(words)
        
        # Регистрируем русский шрифт
        font_path = os.path.join(settings.BASE_DIR, 'fonts', 'DejaVuSans.ttf')
        if not os.path.exists(font_path):
            font_path = "C:\\Windows\\Fonts\\arial.ttf"
        
        try:
            pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', font_path))
            use_russian_font = True
        except:
            use_russian_font = False
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Устанавливаем шрифт
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 14)
        else:
            c.setFont("Helvetica-Bold", 14)
        
        # Шапка документа
        c.drawString(50, height - 50, "Унифицированная форма № Т-1")
        if use_russian_font:
            c.setFont("DejaVuSans", 10)
        else:
            c.setFont("Helvetica", 10)
        c.drawString(50, height - 65, "Утверждена Постановлением Госкомстата РФ от 05.01.2004 № 1")
        
        # Линия
        c.line(50, height - 80, width - 50, height - 80)
        
        # Код формы
        c.drawString(width - 150, height - 50, "Код")
        c.drawString(width - 100, height - 50, "0301001")
        
        # Название организации
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 12)
        else:
            c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 110, "МБДОУ \"Рябинушка\"")
        
        # Номер и дата приказа
        if use_russian_font:
            c.setFont("DejaVuSans", 11)
        else:
            c.setFont("Helvetica", 11)
        c.drawString(50, height - 140, f"ПРИКАЗ")
        c.drawString(50, height - 155, f"(распоряжение)")
        
        c.drawString(200, height - 140, f"№ {order.order_number}")
        c.drawString(350, height - 140, f"от {order.order_date.strftime('%d.%m.%Y')} г.")
        
        # Заголовок
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 12)
        else:
            c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 190, "о приеме работника на работу")
        
        # Линия
        c.line(50, height - 200, width - 50, height - 200)
        
        # Дата приема
        if use_russian_font:
            c.setFont("DejaVuSans", 11)
        else:
            c.setFont("Helvetica", 11)
        c.drawString(50, height - 225, f"Принять на работу")
        
        # ФИО сотрудника (жирным)
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 12)
        else:
            c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 250, f"{last_name} {first_name} {patronymic}".strip())
        
        # Подразделение
        if use_russian_font:
            c.setFont("DejaVuSans", 11)
        else:
            c.setFont("Helvetica", 11)
        c.drawString(50, height - 275, f"в {order.department}")
        
        # Таблица
        y = height - 320
        
        # Заголовки таблицы
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 10)
        else:
            c.setFont("Helvetica-Bold", 10)
        c.drawString(60, y, "Табельный номер")
        c.drawString(200, y, "Структурное подразделение")
        c.drawString(380, y, "Должность (специальность, профессия)")
        
        y -= 15
        if use_russian_font:
            c.setFont("DejaVuSans", 10)
        else:
            c.setFont("Helvetica", 10)
        c.drawString(60, y, str(order.employee.id).zfill(6))
        c.drawString(200, y, order.department)
        c.drawString(380, y, order.position)
        
        y -= 30
        
        # Условия приема
        if use_russian_font:
            c.setFont("DejaVuSans-Bold", 11)
        else:
            c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Условия приема на работу, характер работы")
        
        y -= 20
        if use_russian_font:
            c.setFont("DejaVuSans", 10)
        else:
            c.setFont("Helvetica", 10)
        conditions = dict(order.EMPLOYMENT_CONDITIONS).get(order.employment_condition, '')
        c.drawString(50, y, conditions)
        
        y -= 20
        
        # Тарифная ставка
        c.drawString(50, y, f"с тарифной ставкой (окладом) {order.tariff_rate:.2f} руб.")
        
        y -= 20
        if order.has_bonus and order.bonus_description:
            c.drawString(50, y, f"надбавкой {order.bonus_description} {order.bonus_amount:.2f} руб.")
            y -= 20
        
        # Испытательный срок
        if order.probation_period > 0:
            probation_words = number_to_words(order.probation_period)
            month_word = "месяц" if order.probation_period == 1 else \
                        "месяца" if 2 <= order.probation_period <= 4 else \
                        "месяцев"
            c.drawString(50, y, f"с испытательным сроком {order.probation_period} ({probation_words}) {month_word}")
            y -= 20
        
        # Основание
        c.drawString(50, y, f"Основание:")
        y -= 20
        c.drawString(70, y, order.basis_documents[:60] + ("..." if len(order.basis_documents) > 60 else ""))
        
        y -= 40
        
        # Руководитель
        c.drawString(50, y, f"Руководитель организации")
        y -= 20
        c.drawString(70, y, order.director_position)
        y -= 20
        c.drawString(70, y, f"__________________ {order.director_name}")
        
        y -= 40
        
        # Сотрудник ознакомлен
        c.drawString(50, y, f"С приказом (распоряжением) работник ознакомлен")
        y -= 20
        c.drawString(70, y, f"«___» _________ 20__ г. __________________ (подпись работника)")
        
        if order.employee_acquainted and order.acquainted_date:
            y -= 30
            c.drawString(70, y, f"Ознакомлен: {order.acquainted_date.strftime('%d.%m.%Y')}")
        
        # Мотивированное мнение (для профсоюза)
        y = 100
        if use_russian_font:
            c.setFont("DejaVuSans", 8)
        else:
            c.setFont("Helvetica", 8)
        c.drawString(50, y, "Мотивированное мнение выборного профсоюзного органа в письменной форме")
        y -= 15
        c.drawString(70, y, "от «___» _________ 20__ г. № __________ рассмотрено")
        
        c.showPage()
        c.save()
        
        pdf = buffer.getvalue()
        buffer.close()
        
        # Сохраняем файл
        from django.core.files.base import ContentFile
        filename = f"prikaz_T1_{last_name}_{order.order_date.strftime('%Y%m%d')}.pdf"
        order.order_file.save(filename, ContentFile(pdf), save=True)
        
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        import traceback
        error_msg = f"Ошибка при генерации PDF: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        messages.error(request, f"Ошибка при генерации PDF: {str(e)}")
        return redirect('staff:hire_order_detail', order_id=order.id)


@login_required
@director_required
def hire_order_print(request, order_id):
    """Печатная форма приказа"""
    order = get_object_or_404(HireOrder, id=order_id)
    
    # Разбираем ФИО из full_name для передачи в шаблон
    full_name = order.employee.full_name
    name_parts = full_name.split()
    
    context = {
        'order': order,
        'last_name': name_parts[0] if len(name_parts) > 0 else '',
        'first_name': name_parts[1] if len(name_parts) > 1 else '',
        'patronymic': name_parts[2] if len(name_parts) > 2 else '',
    }
    
    return render(request, 'staff/hire_order_print.html', context)


# staff/views.py - добавьте после существующих импортов

# ==================== КОНСТРУКТОР ЗАРПЛАТЫ (ВИДЫ НАЧИСЛЕНИЙ) ====================

@login_required
@director_required
def payroll_type_list(request):
    """Список видов начислений и удержаний"""
    from .models import PayrollType
    
    # Фильтры
    type_filter = request.GET.get('type', 'all')
    search_query = request.GET.get('search', '')
    
    payroll_types = PayrollType.objects.all().order_by('code')
    
    if type_filter == 'accrual':
        payroll_types = payroll_types.filter(is_accrual=True)
    elif type_filter == 'deduction':
        payroll_types = payroll_types.filter(is_accrual=False)
    
    if search_query:
        payroll_types = payroll_types.filter(
            Q(code__icontains=search_query) | 
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    context = {
        'payroll_types': payroll_types,
        'title': 'Виды начислений и удержаний',
    }
    
    return render(request, 'staff/payroll_type_list.html', context)


@login_required
@director_required
def payroll_type_create(request):
    """Создание нового вида начисления"""
    from .models import PayrollType
    from .forms_payroll import PayrollTypeForm
    
    if request.method == 'POST':
        form = PayrollTypeForm(request.POST)
        if form.is_valid():
            payroll_type = form.save()
            messages.success(request, f'Вид начисления "{payroll_type.name}" успешно создан!')
            return redirect('staff:payroll_type_list')
    else:
        form = PayrollTypeForm()
    
    return render(request, 'staff/payroll_type_form.html', {
        'form': form,
        'title': 'Создание вида начисления',
        'submit_text': 'Создать'
    })


@login_required
@director_required
def payroll_type_edit(request, pk):
    """Редактирование вида начисления"""
    from .models import PayrollType
    from .forms_payroll import PayrollTypeForm
    import json
    
    payroll_type = get_object_or_404(PayrollType, pk=pk)
    
    if request.method == 'POST':
        form = PayrollTypeForm(request.POST, instance=payroll_type)
        if form.is_valid():
            form.save()
            messages.success(request, f'Вид начисления "{payroll_type.name}" обновлен!')
            return redirect('staff:payroll_type_list')
    else:
        # Преобразуем JSON поле seniority_scale в читаемый вид для формы
        initial_data = {}
        if payroll_type.seniority_scale:
            initial_data['seniority_scale_json'] = json.dumps(payroll_type.seniority_scale, indent=2, ensure_ascii=False)
        
        form = PayrollTypeForm(instance=payroll_type, initial=initial_data)
    
    return render(request, 'staff/payroll_type_form.html', {
        'form': form,
        'payroll_type': payroll_type,
        'title': f'Редактирование: {payroll_type.name}',
        'submit_text': 'Сохранить'
    })


@login_required
@director_required
def payroll_type_delete(request, pk):
    """Удаление вида начисления"""
    from .models import PayrollType, EmployeePayrollAssignment
    
    payroll_type = get_object_or_404(PayrollType, pk=pk)
    
    # Проверяем, используется ли этот вид в назначениях
    is_used = EmployeePayrollAssignment.objects.filter(payroll_type=payroll_type).exists()
    
    if request.method == 'POST':
        if is_used:
            # Если используется, просто деактивируем
            payroll_type.is_active = False
            payroll_type.save()
            messages.warning(request, f'Вид начисления "{payroll_type.name}" деактивирован, так как используется в назначениях.')
        else:
            payroll_type.delete()
            messages.success(request, f'Вид начисления "{payroll_type.name}" удален!')
        
        return redirect('staff:payroll_type_list')
    
    return render(request, 'staff/payroll_type_confirm_delete.html', {
        'payroll_type': payroll_type,
        'is_used': is_used
    })


# ==================== НАЗНАЧЕНИЕ НАЧИСЛЕНИЙ СОТРУДНИКАМ ====================

@login_required
@director_required
def employee_payroll_assignments(request, employee_id):
    """Список назначенных начислений сотруднику"""
    from .models import Employee, EmployeePayrollAssignment
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    # Активные назначения
    active_assignments = EmployeePayrollAssignment.objects.filter(
        employee=employee,
        is_active=True,
        end_date__isnull=True
    ).select_related('payroll_type')
    
    # Завершенные назначения (с датой окончания)
    past_assignments = EmployeePayrollAssignment.objects.filter(
        employee=employee
    ).exclude(
        end_date__isnull=True
    ).select_related('payroll_type').order_by('-end_date')
    
    context = {
        'employee': employee,
        'active_assignments': active_assignments,
        'past_assignments': past_assignments,
    }
    
    return render(request, 'staff/employee_payroll_assignments.html', context)


@login_required
@director_required
def employee_payroll_assignment_add(request, employee_id):
    """Добавление начисления сотруднику"""
    from .models import Employee, EmployeePayrollAssignment
    from .forms_payroll import EmployeePayrollAssignmentForm
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if request.method == 'POST':
        form = EmployeePayrollAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.employee = employee
            assignment.save()
            messages.success(request, f'Назначение добавлено!')
            return redirect('staff:employee_payroll_assignments', employee_id=employee.id)
    else:
        form = EmployeePayrollAssignmentForm(initial={'start_date': date.today()})
    
    return render(request, 'staff/employee_payroll_assignment_form.html', {
        'form': form,
        'employee': employee,
        'title': f'Добавление начисления для {employee.full_name}'
    })


@login_required
@director_required
def employee_payroll_assignment_edit(request, assignment_id):
    """Редактирование назначения"""
    from .models import EmployeePayrollAssignment
    from .forms_payroll import EmployeePayrollAssignmentForm
    
    assignment = get_object_or_404(EmployeePayrollAssignment, id=assignment_id)
    
    if request.method == 'POST':
        form = EmployeePayrollAssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            messages.success(request, f'Назначение обновлено!')
            return redirect('staff:employee_payroll_assignments', employee_id=assignment.employee.id)
    else:
        form = EmployeePayrollAssignmentForm(instance=assignment)
    
    return render(request, 'staff/employee_payroll_assignment_form.html', {
        'form': form,
        'assignment': assignment,
        'employee': assignment.employee,
        'title': f'Редактирование назначения'
    })


@login_required
@director_required
def employee_payroll_assignment_delete(request, assignment_id):
    """Удаление назначения"""
    from .models import EmployeePayrollAssignment
    
    assignment = get_object_or_404(EmployeePayrollAssignment, id=assignment_id)
    employee_id = assignment.employee.id
    
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, f'Назначение удалено!')
        return redirect('staff:employee_payroll_assignments', employee_id=employee_id)
    
    return render(request, 'staff/employee_payroll_assignment_confirm_delete.html', {
        'assignment': assignment
    })


@login_required
@director_required
def employee_schedule_list(request):
    """Список графиков работы сотрудников"""
    from .models import EmployeeWorkSchedule
    
    schedules = EmployeeWorkSchedule.objects.all().select_related('employee', 'schedule_template').order_by('-start_date')
    
    return render(request, 'staff/employee_schedule_list.html', {
        'schedules': schedules
    })


@login_required
@director_required
def employee_schedule_create(request):
    """Создание графика работы для сотрудника"""
    from .models import EmployeeWorkSchedule
    from .forms_payroll import EmployeeWorkScheduleForm
    
    if request.method == 'POST':
        form = EmployeeWorkScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save()
            messages.success(request, f'График работы назначен!')
            return redirect('staff:employee_schedule_list')
    else:
        form = EmployeeWorkScheduleForm()
    
    return render(request, 'staff/employee_schedule_form.html', {
        'form': form,
        'title': 'Назначение графика работы'
    })
    
    
# staff/views.py - добавьте после существующих функций

# ==================== ГРАФИКИ РАБОТЫ ====================

@login_required
@director_required
def schedule_list(request):
    """Список графиков работы"""
    from .models import WorkSchedule
    
    schedules = WorkSchedule.objects.all()
    
    return render(request, 'staff/schedule_list.html', {
        'schedules': schedules
    })


@login_required
@director_required
def schedule_create(request):
    """Создание графика работы"""
    from .models import WorkSchedule
    from .forms import WorkScheduleForm
    
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save()
            messages.success(request, f'График "{schedule.name}" создан!')
            return redirect('staff:schedule_detail', schedule_id=schedule.id)
    else:
        form = WorkScheduleForm()
    
    return render(request, 'staff/schedule_form.html', {
        'form': form,
        'title': 'Новый график работы'
    })


@login_required
@director_required
def schedule_detail(request, schedule_id):
    """Детальная страница графика"""
    from .models import WorkSchedule
    
    schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    
    # Если есть модель WorkScheduleDetail, можно добавить:
    # details = WorkScheduleDetail.objects.filter(schedule=schedule).order_by('day_of_week')
    details = []  # Пока пустой список
    
    return render(request, 'staff/schedule_detail.html', {
        'schedule': schedule,
        'details': details
    })


@login_required
@director_required
def schedule_edit(request, schedule_id):
    """Редактирование графика"""
    from .models import WorkSchedule
    from .forms import WorkScheduleForm
    
    schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            messages.success(request, 'График обновлен!')
            return redirect('staff:schedule_detail', schedule_id=schedule.id)
    else:
        form = WorkScheduleForm(instance=schedule)
    
    return render(request, 'staff/schedule_form.html', {
        'form': form,
        'schedule': schedule,
        'title': f'Редактирование: {schedule.name}'
    })


@login_required
@director_required
def schedule_entry_add(request, schedule_id):
    """Добавление элемента в график"""
    from .models import WorkSchedule
    
    schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    
    # Эта функция требует модели WorkScheduleEntry, которой у вас нет
    # Пока просто редирект на детальную страницу
    messages.warning(request, 'Функция добавления элементов графика находится в разработке')
    return redirect('staff:schedule_detail', schedule_id=schedule.id)
    
    
# staff/views.py - добавьте после существующих функций

# ==================== РАСЧЕТ ЗАРАБОТНОЙ ПЛАТЫ ====================

@login_required
@director_required
def salary_dashboard(request):
    """Панель расчета зарплаты"""
    from .models import SalaryCalculation
    import calendar
    from datetime import date
    
    current_month = date.today().month
    current_year = date.today().year
    
    # Получаем параметры из GET запроса
    month = request.GET.get('month', current_month)
    year = request.GET.get('year', current_year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = current_month
        year = current_year
    
    # Расчеты за выбранный месяц
    current_calculations = SalaryCalculation.objects.filter(
        month=month,
        year=year
    ).select_related('employee')
    
    # Статистика
    total_payroll = current_calculations.aggregate(total=Sum('total_payable'))['total'] or 0
    employees_count = current_calculations.count()
    
    total_accrued = current_calculations.aggregate(total=Sum('total_accrued'))['total'] or 0
    total_tax = current_calculations.aggregate(total=Sum('income_tax'))['total'] or 0
    total_payable = current_calculations.aggregate(total=Sum('total_payable'))['total'] or 0
    
    # Предыдущие месяцы для навигации
    previous_months = SalaryCalculation.objects.values('month', 'year').distinct().order_by('-year', '-month')[:6]
    
    # Добавляем названия месяцев
    months_names = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    
    for item in previous_months:
        item['month_name'] = months_names.get(item['month'], '')
    
    context = {
        'current_month': month,
        'current_year': year,
        'current_calculations': current_calculations,
        'total_payroll': total_payroll,
        'employees_count': employees_count,
        'total_accrued': total_accrued,
        'total_tax': total_tax,
        'total_payable': total_payable,
        'previous_months': previous_months,
        'month_name': months_names.get(month, ''),
    }
    
    return render(request, 'staff/salary_dashboard.html', context)


@login_required
@director_required
def salary_calculate(request):
    """Расчет зарплаты за месяц"""
    from .models import Timesheet, TimesheetEntry, Employee, StaffUnit, SalaryCalculation
    from datetime import date
    import calendar
    
    if request.method == 'POST':
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))
        
        # Получаем табель за этот месяц
        timesheet = Timesheet.objects.filter(month=month, year=year).first()
        
        if not timesheet:
            messages.error(request, f'Сначала создайте табель за {month}.{year}')
            return redirect('staff:timesheet_create')
        
        if not timesheet.is_closed:
            messages.warning(request, 'Табель еще не закрыт. Рекомендуется закрыть табель перед расчетом зарплаты')
        
        # Получаем всех активных сотрудников на этот месяц
        employees = Employee.objects.filter(
            Q(dismissal_date__isnull=True) | Q(dismissal_date__gte=date(year, month, 1))
        )
        
        calculations_created = 0
        calculations_updated = 0
        
        for employee in employees:
            # Получаем запись в табеле
            timesheet_entry = TimesheetEntry.objects.filter(
                timesheet=timesheet,
                employee=employee
            ).first()
            
            if not timesheet_entry:
                continue
            
            # Получаем штатную единицу сотрудника
            staff_unit = StaffUnit.objects.filter(employee=employee).first()
            
            if not staff_unit or not staff_unit.position:
                # Если нет штатной единицы, используем базовый оклад из должности
                base_salary = Decimal('30000.00')
            else:
                base_salary = staff_unit.calculated_salary  # Это уже Decimal
            
            # Расчет отработанных часов
            worked_hours = Decimal(str(timesheet_entry.total_hours))
            standard_hours = Decimal(str(timesheet_entry.total_days * 8))
            
            # Часовая ставка
            if standard_hours > 0:
                hourly_rate = base_salary / standard_hours
            else:
                hourly_rate = Decimal('0')
            
            # Расчет выплат
            base_payment = hourly_rate * worked_hours
            
            # Сверхурочные (коэффициент 1.5)
            overtime_hours = Decimal(str(timesheet_entry.overtime_hours))
            overtime_payment = hourly_rate * overtime_hours * Decimal('1.5')
            
            # Ночные (коэффициент 1.2)
            night_hours = Decimal(str(timesheet_entry.night_hours))
            night_payment = hourly_rate * night_hours * Decimal('1.2')
            
            # Праздничные (коэффициент 2)
            holiday_hours = Decimal(str(timesheet_entry.holiday_hours))
            holiday_payment = hourly_rate * holiday_hours * Decimal('2')
            
            # Стимулирующие выплаты (пока 0)
            stimulating_payments = Decimal('0')
            
            # Больничные и отпускные (пока 0)
            sick_leave = Decimal('0')
            vacation_pay = Decimal('0')
            
            total_accrued = (base_payment + overtime_payment + night_payment + 
                           holiday_payment + stimulating_payments + sick_leave + vacation_pay)
            
            # НДФЛ 13%
            income_tax = total_accrued * Decimal('0.13')
            total_payable = total_accrued - income_tax
            
            # Создаем или обновляем расчет
            calculation, created = SalaryCalculation.objects.update_or_create(
                employee=employee,
                month=month,
                year=year,
                defaults={
                    'timesheet': timesheet,
                    'base_salary': base_salary,
                    'worked_hours': worked_hours,
                    'standard_hours': standard_hours,
                    'overtime_payment': overtime_payment,
                    'night_payment': night_payment,
                    'holiday_payment': holiday_payment,
                    'stimulating_payments': stimulating_payments,
                    'sick_leave': sick_leave,
                    'vacation_pay': vacation_pay,
                    'total_accrued': total_accrued,
                    'income_tax': income_tax,
                    'total_payable': total_payable,
                    'status': 'calculated'
                }
            )
            
            if created:
                calculations_created += 1
            else:
                calculations_updated += 1
        
        messages.success(
            request, 
            f'Расчет зарплаты выполнен! Создано: {calculations_created}, обновлено: {calculations_updated}'
        )
        return redirect('staff:salary_dashboard')
    
    # GET запрос - показываем форму
    today = date.today()
    months = [(i, calendar.month_name[i]) for i in range(1, 13)]
    years = range(today.year - 1, today.year + 2)
    
    context = {
        'current_month': today.month,
        'current_year': today.year,
        'months': months,
        'years': years,
    }
    
    return render(request, 'staff/salary_calculate_form.html', context)


@login_required
@director_required
def salary_calculations_list(request):
    """Список расчетов зарплаты"""
    from .models import SalaryCalculation
    from datetime import date
    import calendar
    
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = date.today().month
        year = date.today().year
    
    calculations = SalaryCalculation.objects.filter(
        month=month,
        year=year
    ).select_related('employee').order_by('employee__full_name')
    
    # Итоговая сумма
    total_payroll = calculations.aggregate(total=Sum('total_payable'))['total'] or 0
    
    context = {
        'calculations': calculations,
        'month': month,
        'year': year,
        'total_payroll': total_payroll,
        'month_name': calendar.month_name[month],
    }
    
    return render(request, 'staff/salary_calculations_list.html', context)


@login_required
@director_required
def salary_detail(request, calc_id):
    """Детали расчета зарплаты"""
    from .models import SalaryCalculation, SalaryComponent
    
    calculation = get_object_or_404(SalaryCalculation, id=calc_id)
    components = SalaryComponent.objects.filter(salary_calculation=calculation)
    
    return render(request, 'staff/salary_detail.html', {
        'calculation': calculation,
        'components': components
    })


@login_required
@director_required
def salary_approve(request, calc_id):
    """Утверждение расчета зарплаты"""
    from .models import SalaryCalculation
    
    calculation = get_object_or_404(SalaryCalculation, id=calc_id)
    
    if request.method == 'POST':
        calculation.status = 'approved'
        calculation.save()
        messages.success(request, 'Расчет утвержден')
    
    return redirect('staff:salary_detail', calc_id=calc_id)


@login_required
@director_required
def payroll_register(request):
    """Реестр на выплату зарплаты"""
    from .models import SalaryCalculation
    from datetime import date
    import calendar
    
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = date.today().month
        year = date.today().year
    
    calculations = SalaryCalculation.objects.filter(
        month=month,
        year=year
    ).select_related('employee').order_by('employee__full_name')
    
    total_amount = calculations.aggregate(total=Sum('total_payable'))['total'] or 0
    
    if request.method == 'POST':
        # Отметка о выплате
        for calc in calculations:
            calc.status = 'paid'
            calc.payment_date = date.today()
            calc.save()
        
        messages.success(request, 'Выплата зарплаты зарегистрирована')
        return redirect('staff:payroll_register')
    
    context = {
        'calculations': calculations,
        'month': month,
        'year': year,
        'total_amount': total_amount,
        'month_name': calendar.month_name[month],
    }
    
    return render(request, 'staff/payroll_register.html', context)


@login_required
@director_required
def generate_payslip(request, calc_id):
    """Генерация расчетного листка"""
    from .models import SalaryCalculation
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    import io
    from datetime import date
    
    calculation = get_object_or_404(SalaryCalculation, id=calc_id)
    employee = calculation.employee
    
    # Создаем PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="payslip_{employee.id}_{calculation.month}_{calculation.year}.pdf"'
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Заголовок
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "МБДОУ 'Рябинушка'")
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 80, "Расчетный листок")
    
    # Информация о сотруднике
    p.setFont("Helvetica", 11)
    p.drawString(50, height - 120, f"Сотрудник: {employee.full_name}")
    p.drawString(50, height - 140, f"Должность: {employee.position}")
    
    month_names = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    
    p.drawString(300, height - 120, f"Период: {month_names[calculation.month]} {calculation.year}")
    
    # Линия
    p.line(50, height - 160, width - 50, height - 160)
    
    # Начисления
    y = height - 190
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Начислено:")
    
    y -= 25
    p.setFont("Helvetica", 11)
    p.drawString(70, y, f"Оклад: {calculation.base_salary:.2f} руб.")
    
    y -= 20
    p.drawString(70, y, f"Отработано часов: {calculation.worked_hours}")
    
    y -= 20
    p.drawString(70, y, f"Норма часов: {calculation.standard_hours}")
    
    if calculation.overtime_payment > 0:
        y -= 20
        p.drawString(70, y, f"Сверхурочные: {calculation.overtime_payment:.2f} руб.")
    
    if calculation.night_payment > 0:
        y -= 20
        p.drawString(70, y, f"Ночные: {calculation.night_payment:.2f} руб.")
    
    if calculation.holiday_payment > 0:
        y -= 20
        p.drawString(70, y, f"Праздничные: {calculation.holiday_payment:.2f} руб.")
    
    # Итоги
    y -= 30
    p.line(50, y + 10, width - 50, y + 10)
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, y, f"Всего начислено: {calculation.total_accrued:.2f} руб.")
    
    y -= 20
    p.drawString(50, y, f"НДФЛ (13%): {calculation.income_tax:.2f} руб.")
    
    y -= 25
    p.setFont("Helvetica-Bold", 14)
    p.setFillColorRGB(0, 0.5, 0)
    p.drawString(50, y, f"К ВЫПЛАТЕ: {calculation.total_payable:.2f} руб.")
    
    # Подписи
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 9)
    p.drawString(50, 100, "Главный бухгалтер")
    p.drawString(150, 100, "___________________")
    p.drawString(50, 70, "Заведующая МБДОУ")
    p.drawString(150, 70, "___________________")
    p.drawString(width - 200, 50, f"Дата: {date.today().strftime('%d.%m.%Y')}")
    
    p.showPage()
    p.save()
    
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response



def generate_contract_word(request, contract_id):
    """
    Генерация трудового договора в формате Word
    """
    from .models import LaborContract, EmployeePayrollAssignment, PayrollType, StaffUnit
    
    contract = get_object_or_404(LaborContract, id=contract_id)
    employee = contract.employee
    
    # Путь к шаблону
    template_path = os.path.join(settings.BASE_DIR, 'templates', 'staff', 'contract_template.docx')
    
    # Открываем шаблон
    doc = Document(template_path)
    
    # Получаем надбавки сотрудника
    assignments = EmployeePayrollAssignment.objects.filter(
        employee=employee,
        is_active=True
    ).select_related('payroll_type')
    
    bonus_highest = 0
    bonus_first = 0
    bonus_mentor = 0
    stimulating = 0
    
    for assignment in assignments:
        if assignment.payroll_type and assignment.payroll_type.code == 'BONUS_HIGHEST_CATEGORY':
            bonus_highest = assignment.custom_value or 20
        elif assignment.payroll_type and assignment.payroll_type.code == 'BONUS_FIRST_CATEGORY':
            bonus_first = assignment.custom_value or 15
        elif assignment.payroll_type and assignment.payroll_type.code == 'BONUS_MENTOR':
            bonus_mentor = assignment.custom_value or 10
        elif assignment.payroll_type and assignment.payroll_type.code == 'STIMULATING':
            stimulating = assignment.custom_value or 0
    
    # Получаем штатную единицу для оклада
    staff_unit = StaffUnit.objects.filter(employee=employee).first()
    base_salary = staff_unit.position.base_salary if staff_unit and staff_unit.position else 30000
    
    # Заменяем плейсхолдеры в документе
    for paragraph in doc.paragraphs:
        if '[номер]' in paragraph.text:
            paragraph.text = paragraph.text.replace('[номер]', contract.contract_number)
        
        if '[дата]' in paragraph.text:
            paragraph.text = paragraph.text.replace('[дата]', contract.start_date.strftime('%d.%m.%Y'))
        
        if '[должность]' in paragraph.text:
            paragraph.text = paragraph.text.replace('[должность]', employee.position)
        
        if '[основная / по совместительству]' in paragraph.text:
            employment_type = 'основная' if contract.contract_type == 'indefinite' else 'по совместительству'
            paragraph.text = paragraph.text.replace('[основная / по совместительству]', employment_type)
        
        if '[неопределенный срок / определенный срок]' in paragraph.text:
            if contract.contract_type == 'indefinite':
                contract_term = 'неопределенный срок'
            else:
                contract_term = f'срок до {contract.end_date.strftime("%d.%m.%Y")}'
            paragraph.text = paragraph.text.replace('[неопределенный срок / определенный срок]', contract_term)
        
        if '[дата_начала]' in paragraph.text:
            paragraph.text = paragraph.text.replace('[дата_начала]', contract.start_date.strftime('%d.%m.%Y'))
        
        if '[испытательный_срок]' in paragraph.text:
            probation = str(contract.probation_period) if contract.probation_period > 0 else '0'
            paragraph.text = paragraph.text.replace('[испытательный_срок]', probation)
        
        if '[оклад]' in paragraph.text:
            paragraph.text = paragraph.text.replace('[оклад]', f'{base_salary:.2f}')
        
        if '[надбавка_категория]' in paragraph.text:
            bonus = bonus_highest if bonus_highest > 0 else bonus_first
            paragraph.text = paragraph.text.replace('[надбавка_категория]', str(bonus))
        
        if '[стимулирующие]' in paragraph.text:
            paragraph.text = paragraph.text.replace('[стимулирующие]', f'{stimulating:.2f}')
        
        if '[ФИО]' in paragraph.text:
            paragraph.text = paragraph.text.replace('[ФИО]', employee.full_name)
        
        if '__________________ [ФИО]' in paragraph.text:
            paragraph.text = paragraph.text.replace('__________________ [ФИО]', f'__________________ {employee.full_name}')
    
    # Сохраняем документ
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="trudovoy_dogovor_{employee.full_name}_{contract.contract_number}.docx"'
    
    doc.save(response)
    return response
