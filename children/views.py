from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, FileResponse
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import date, datetime, timedelta
import pandas as pd
from io import BytesIO
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from urllib.parse import quote
import json
from django.views.decorators.csrf import csrf_exempt

from .models import Child, Group, ChildParent, PersonalFile, DocumentCheckHistory
from .forms import (
    ChildForm, ChildParentForm, ChildCreateForm, GroupForm,
    PersonalFileForm, ChildConsentForm, DocumentCheckForm,
    ChildMedicalForm, ChildDocumentsForm
)
from accounts.models import CustomUser, ParentProfile
from applications.models import ChildApplication  # Добавьте эту строку
from contracts.models import EducationContract
from orders.models import EnrollmentOrder


@login_required
def children_list(request):
    if request.user.role == 'parent':
        # ИСПРАВЛЕНО
        child_ids = ChildParent.objects.filter(parent=request.user.parentprofile).values_list('child_id', flat=True)
        children = Child.objects.filter(id__in=child_ids)
    elif request.user.role == 'teacher':
        children = Child.objects.filter(group__teacher=request.user)
    elif request.user.role == 'director':
        children = Child.objects.all()
    else:
        children = Child.objects.none()
    
    # Вычисляем статистику
    if children:
        total_age = sum(child.get_age() for child in children)
        average_age = round(total_age / len(children), 1)
        boys_count = children.filter(gender='M').count()
        girls_count = children.filter(gender='F').count()
    else:
        average_age = 0
        boys_count = 0
        girls_count = 0
    
    # Подсчет документов
    from applications.models import ChildApplication
    
    applications_count = ChildApplication.objects.filter(
        parent__user=request.user
    ).count() if request.user.role == 'parent' else ChildApplication.objects.count()
    
    birth_certificates_count = children.exclude(birth_certificate='').count()
    policy_oms_count = children.exclude(policy_oms_number='').count()
    medical_cards_count = children.exclude(medical_card_number='').count()
    consents_count = children.filter(
        application__data_processing_consent=True
    ).count() if hasattr(children.first(), 'application') else 0
    benefits_count = children.exclude(disability_certificate='').count()
    
    # Получаем все группы для фильтра
    groups = Group.objects.all()
    
    return render(request, 'children/children_list.html', {
        'children': children,
        'average_age': average_age,
        'boys_count': boys_count,
        'girls_count': girls_count,
        'groups': groups,
        'applications_count': applications_count,
        'birth_certificates_count': birth_certificates_count,
        'policy_oms_count': policy_oms_count,
        'medical_cards_count': medical_cards_count,
        'consents_count': consents_count,
        'benefits_count': benefits_count,
    })

@login_required
def child_detail(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    
    # Проверка прав доступа - ИСПРАВЛЕНО
    if request.user.role == 'parent':
        is_authorized = ChildParent.objects.filter(
            child=child,
            parent=request.user.parentprofile
        ).exists()
        if not is_authorized:
            messages.error(request, 'У вас нет доступа к информации об этом ребенке.')
            return redirect('dashboard')
    elif request.user.role == 'teacher':
        if not child.group or child.group.teacher != request.user:
            messages.error(request, 'У вас нет доступа к информации об этом ребенке.')
            return redirect('dashboard')
    
    # Получаем связанное заявление
    application = child.application
    
    # Статусы документов (проверяем наличие данных в БД)
    document_statuses = {
        'application_signed': application.is_signed if application and hasattr(application, 'is_signed') else False,
        'application_exists': application is not None,
        'application_number': application.application_number if application else None,
        'birth_certificate': bool(child.birth_certificate),
        'birth_certificate_value': child.birth_certificate or '',
        'registration_address': bool(child.registration_address),
        'snils': bool(child.snils),
        'snils_value': child.snils or '',
        'data_processing_consent': application.data_processing_consent if application else False,
        'policy_oms': bool(child.policy_oms_number),
        'policy_oms_value': child.policy_oms_number or '',
        'benefits': bool(child.disability_certificate),
        'benefits_value': child.disability_certificate or '',
        'medical_card': bool(child.medical_card_number),
        'medical_card_value': child.medical_card_number or '',
        'medical_card_issued': bool(child.medical_card_number),
    }
    
    return render(request, 'children/child_detail.html', {
        'child': child,
        'application': application,
        'document_statuses': document_statuses,
    })

@login_required
def child_create(request):
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может добавлять детей.')
        return redirect('children:children_list')
    
    if request.method == 'POST':
        form = ChildCreateForm(request.POST)
        if form.is_valid():
            child = form.save()
            messages.success(request, f'Ребенок {child.full_name} успешно добавлен!')
            return redirect('children:child_detail', child_id=child.id)
    else:
        form = ChildCreateForm()
    
    return render(request, 'children/child_form.html', {
        'form': form,
        'title': 'Добавление ребенка',
        'submit_text': 'Добавить ребенка'
    })

@login_required
def child_edit(request, child_id):
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может редактировать данные детей.')
        return redirect('children:children_list')
    
    child = get_object_or_404(Child, id=child_id)
    
    if request.method == 'POST':
        form = ChildForm(request.POST, instance=child)
        if form.is_valid():
            form.save()
            messages.success(request, f'Данные ребенка {child.full_name} успешно обновлены!')
            return redirect('children:child_detail', child_id=child.id)
    else:
        form = ChildForm(instance=child)
    
    return render(request, 'children/child_form.html', {
        'form': form,
        'child': child,
        'title': f'Редактирование ребенка: {child.full_name}',
        'submit_text': 'Сохранить изменения'
    })

@login_required
def child_delete(request, child_id):
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может удалять детей.')
        return redirect('children:children_list')
    
    child = get_object_or_404(Child, id=child_id)
    
    if request.method == 'POST':
        child_name = child.full_name
        child.delete()
        messages.success(request, f'Ребенок {child_name} успешно удален!')
        return redirect('children:children_list')
    
    return redirect('children:children_list')

@login_required
def add_parent(request, child_id):
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может добавлять родителей.')
        return redirect('children:children_list')
    
    child = get_object_or_404(Child, id=child_id)
    
    if request.method == 'POST':
        form = ChildParentForm(request.POST)
        if form.is_valid():
            child_parent = form.save(commit=False)
            child_parent.child = child
            child_parent.save()
            messages.success(request, f'Родитель успешно добавлен к ребенку {child.full_name}!')
            return redirect('children:child_detail', child_id=child.id)
    else:
        form = ChildParentForm()
    
    return render(request, 'children/add_parent.html', {
        'form': form,
        'child': child
    })
    
    
    
@login_required
def group_children(request, group_id):
    """Просмотр детей конкретной группы с сортировкой, поиском и экспортом"""
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может просматривать список детей группы.')
        return redirect('dashboard')
    
    group = get_object_or_404(Group, id=group_id)
    children = group.child_set.all()
    
    # Параметры сортировки
    sort_by = request.GET.get('sort', 'full_name')
    order = request.GET.get('order', 'asc')
    
    # Допустимые поля для сортировки
    valid_sort_fields = ['full_name', 'birth_date', 'gender', 'enrollment_date']
    if sort_by not in valid_sort_fields:
        sort_by = 'full_name'
    
    # Применяем сортировку
    if order == 'desc':
        sort_by = f'-{sort_by}'
    children = children.order_by(sort_by)
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        children = children.filter(
            Q(full_name__icontains=search_query) |
            Q(parents__full_name__icontains=search_query) |
            Q(birth_certificate__icontains=search_query)
        ).distinct()
    
    # Фильтрация по полу
    gender_filter = request.GET.get('gender', '')
    if gender_filter:
        children = children.filter(gender=gender_filter)
    
    # Фильтрация по возрасту
    age_filter = request.GET.get('age', '')
    if age_filter:
        today = date.today()
        if age_filter == '3-4':
            children = [c for c in children if 3 <= c.get_age() <= 4]
        elif age_filter == '5-6':
            children = [c for c in children if 5 <= c.get_age() <= 6]
        elif age_filter == '7+':
            children = [c for c in children if c.get_age() >= 7]
    
    # Пагинация
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(children, 20)
    page = request.GET.get('page', 1)
    
    try:
        children_page = paginator.page(page)
    except PageNotAnInteger:
        children_page = paginator.page(1)
    except EmptyPage:
        children_page = paginator.page(paginator.num_pages)
    
    # Статистика
    boys_count = group.child_set.filter(gender='M').count()
    girls_count = group.child_set.filter(gender='F').count()
    
    # Средний возраст
    if children:
        total_age = sum(child.get_age() for child in children)
        avg_age = round(total_age / len(children), 1)
    else:
        avg_age = 0
    
    # Для фильтрации
    current_filters = {
        'sort': sort_by,
        'order': order,
        'search': search_query,
        'gender': gender_filter,
        'age': age_filter,
    }
    
    return render(request, 'children/group_children.html', {
        'group': group,
        'children': children_page,
        'boys_count': boys_count,
        'girls_count': girls_count,
        'avg_age': avg_age,
        'total_children': group.child_set.count(),
        'search_query': search_query,
        'current_sort': sort_by.lstrip('-'),
        'current_order': order,
        'current_gender': gender_filter,
        'current_age': age_filter,
        'current_filters': current_filters,
    })


from urllib.parse import quote

@login_required
def export_group_children_excel(request, group_id):
    """Экспорт списка детей группы в Excel"""
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может экспортировать данные.')
        return redirect('dashboard')
    
    group = get_object_or_404(Group, id=group_id)
    children = group.child_set.all().order_by('full_name')
    
    # Создаем DataFrame
    data = []
    for child in children:
        parents = ', '.join([p.full_name for p in child.parents.all()])
        data.append({
            'ФИО ребенка': child.full_name,
            'Дата рождения': child.birth_date.strftime('%d.%m.%Y') if child.birth_date else '',
            'Возраст': child.get_age(),
            'Пол': child.get_gender_display(),
            'Родители': parents,
            'Свидетельство о рождении': child.birth_certificate,
            'Группа крови': child.blood_type or 'Не указана',
            'Аллергии': child.allergies or 'Нет',
            'Хронические заболевания': child.chronic_diseases or 'Нет',
            'Адрес регистрации': child.registration_address,
            'Фактический адрес': child.actual_address,
            'Дата зачисления': child.enrollment_date.strftime('%d.%m.%Y') if child.enrollment_date else '',
            'Статус': 'Активен' if child.is_active else 'Неактивен',
        })
    
    df = pd.DataFrame(data)
    
    # Создаем Excel файл
    output = BytesIO()
    # Очищаем имя листа от недопустимых символов
    sheet_name = f'Группа_{group.name}'[:31]  # Excel ограничение в 31 символ
    # Удаляем символы, которые нельзя использовать в именах листов: \ / * ? : [ ]
    sheet_name = ''.join(c for c in sheet_name if c not in '\\/*?:[]')
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Настраиваем стили
        worksheet = writer.sheets[sheet_name]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    # Формируем безопасное имя файла
    safe_group_name = group.name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
    filename = f'Список_детей_{safe_group_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    # Кодируем имя файла для корректной работы с русскими символами
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
    
    messages.success(request, f'Данные группы "{group.name}" успешно выгружены в Excel')
    return response


@login_required
def export_group_children_word(request, group_id):
    """Экспорт списка детей группы в Word"""
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может экспортировать данные.')
        return redirect('dashboard')
    
    group = get_object_or_404(Group, id=group_id)
    children = group.child_set.all().order_by('full_name')
    
    # Создаем документ Word
    document = Document()
    
    # Заголовок
    title = document.add_heading(f'Список детей группы "{group.name}"', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Информация о группе
    document.add_heading('Информация о группе', level=1)
    info_table = document.add_table(rows=5, cols=2)
    info_table.style = 'Table Grid'
    
    info_data = [
        ('Название группы:', group.name),
        ('Возрастная категория:', group.get_age_category_display()),
        ('Воспитатель:', group.teacher.get_full_name() if group.teacher else 'Не назначен'),
        ('Номер комнаты:', group.room_number),
        ('Всего детей:', str(children.count())),
    ]
    
    for i, (label, value) in enumerate(info_data):
        info_table.rows[i].cells[0].text = label
        info_table.rows[i].cells[1].text = value
    
    document.add_paragraph()
    
    # Список детей
    document.add_heading('Список детей', level=1)
    
    # Таблица с детьми
    table = document.add_table(rows=1, cols=7)
    table.style = 'Table Grid'
    
    # Заголовки
    headers = ['№', 'ФИО ребенка', 'Дата рождения', 'Возраст', 'Пол', 'Родители', 'Статус']
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = header
        # Делаем заголовки жирными
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.bold = True
    
    # Заполняем данными
    for idx, child in enumerate(children, 1):
        row = table.add_row()
        parents = ', '.join([p.full_name for p in child.parents.all()])
        
        row.cells[0].text = str(idx)
        row.cells[1].text = child.full_name
        row.cells[2].text = child.birth_date.strftime('%d.%m.%Y') if child.birth_date else ''
        row.cells[3].text = str(child.get_age())
        row.cells[4].text = child.get_gender_display()
        row.cells[5].text = parents
        row.cells[6].text = 'Активен' if child.is_active else 'Неактивен'
    
    # Добавляем подпись
    document.add_paragraph()
    document.add_paragraph(f'Дата формирования: {datetime.now().strftime("%d.%m.%Y %H:%M")}')
    document.add_paragraph('_________________________ /Заведующая/')
    
    # Сохраняем в response
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    
    # Формируем безопасное имя файла
    safe_group_name = group.name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
    filename = f'Список_детей_{safe_group_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.docx'
    
    # Кодируем имя файла для корректной работы с русскими символами
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
    
    document.save(response)
    
    messages.success(request, f'Данные группы "{group.name}" успешно выгружены в Word')
    return response


@login_required
def personal_file_from_application(request, application_id):
    """
    Просмотр личного дела ребенка из заявления
    """
    from applications.models import ChildApplication, ApplicationStatus
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    # Проверка прав
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile'):
            from accounts.models import ParentProfile
            ParentProfile.objects.create(user=request.user)
        
        if application.parent != request.user.parentprofile:
            messages.error(request, 'У вас нет доступа к этому личному делу.')
            return redirect('dashboard')
    elif request.user.role == 'teacher':
        # Для воспитателя - проверяем, что ребенок в его группе
        if hasattr(application, 'child_record') and application.child_record:
            if not application.child_record.group or application.child_record.group.teacher != request.user:
                messages.error(request, 'У вас нет доступа к этому личному делу.')
                return redirect('dashboard')
    elif request.user.role != 'director':
        messages.error(request, 'У вас нет доступа к этому личному делу.')
        return redirect('dashboard')
    
    # Получаем или создаем личное дело
    from .models import Child
    
    # Формируем номер свидетельства о рождении
    birth_certificate = ""
    if application.birth_certificate_series and application.birth_certificate_number:
        birth_certificate = f"{application.birth_certificate_series} {application.birth_certificate_number}"
    
    child, created = Child.objects.get_or_create(
        application=application,
        defaults={
            'full_name': application.child_full_name,
            'birth_date': application.child_birth_date,
            'gender': application.child_gender,
            'registration_address': application.registration_address,
            'actual_address': application.actual_address or application.registration_address,
            'birth_certificate': birth_certificate,
            'birth_certificate_issued_by': application.birth_certificate_issued_by or '',
            'birth_certificate_issue_date': application.birth_certificate_issue_date,
            'allergies': application.allergies or '',
            'chronic_diseases': application.chronic_diseases or '',
            'special_needs': application.special_needs or '',
            'blood_type': application.blood_type or '',
            'is_active': application.status == ApplicationStatus.QUEUE,
        }
    )
    
    # Если ребенок уже существует, но не связан с заявлением
    if not created and not child.application:
        child.application = application
        child.save()
    
    return render(request, 'children/child_detail.html', {
        'child': child,
        'from_application': True
    })
    
    
@login_required
def personal_files_list(request):
    """Список личных дел с умной фильтрацией"""
    
    # Базовый queryset
    children = Child.objects.select_related('group', 'personal_file').all()
    
    # Фильтрация по роли
    if request.user.role == 'parent':
        try:
            parent_profile = request.user.parentprofile
            # ИСПРАВЛЕНО: используем parent_relations (related_name из ChildParent)
            child_ids = ChildParent.objects.filter(parent=parent_profile).values_list('child_id', flat=True)
            children = children.filter(id__in=child_ids)
        except Exception as e:
            print(f"Error filtering children for parent: {e}")
            children = Child.objects.none()
    elif request.user.role == 'teacher':
        children = children.filter(group__teacher=request.user)
    elif request.user.role != 'director':
        children = Child.objects.none()
    
    # Поиск
    search_query = request.GET.get('search', '')
    if search_query:
        # Получаем ID детей, у которых родитель содержит поисковый запрос
        parent_child_ids = ChildParent.objects.filter(
            parent__full_name__icontains=search_query
        ).values_list('child_id', flat=True)
        
        children = children.filter(
            Q(full_name__icontains=search_query) |
            Q(id__in=parent_child_ids)
        ).distinct()
    
    # Фильтр по статусу
    status_filter = request.GET.get('status', '')
    today_date = date.today()
    
    if status_filter == 'expiring':
        children = children.filter(
            Q(personal_file__registration_expiry_date__gte=today_date, 
              personal_file__registration_expiry_date__lte=today_date + timedelta(days=30)) |
            Q(personal_file__medical_card_expiry_date__gte=today_date,
              personal_file__medical_card_expiry_date__lte=today_date + timedelta(days=30))
        )
    elif status_filter == 'expired':
        children = children.filter(
            Q(personal_file__registration_expiry_date__lt=today_date) |
            Q(personal_file__medical_card_expiry_date__lt=today_date)
        )
    elif status_filter == 'graduated':
        children = children.filter(personal_file__status='graduated')
    elif status_filter == 'active':
        children = children.filter(personal_file__status='active')
    
    # Фильтр по группе
    group_filter = request.GET.get('group', '')
    if group_filter:
        children = children.filter(group_id=group_filter)
    
    # Пагинация
    paginator = Paginator(children, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Подготовка данных для отображения
    children_data = []
    expiring_count = 0
    expired_count = 0
    
    for child in page_obj:
        # ИСПРАВЛЕНО: получаем родителей через ChildParent с правильным related_name
        parents_list = []
        for rel in ChildParent.objects.filter(child=child).select_related('parent__user'):
            parent = rel.parent
            parents_list.append({
                'full_name': parent.full_name if parent.full_name else parent.user.get_full_name(),
                'relation': rel.get_relation_display(),
                'is_primary': rel.is_primary,
                'phone': parent.user.phone or '',
                'email': parent.user.email or '',
            })
        
        # Статус регистрации
        registration_status = 'valid'
        registration_days_left = 0
        if child.personal_file and child.personal_file.registration_expiry_date:
            days_left = (child.personal_file.registration_expiry_date - today_date).days
            if days_left < 0:
                registration_status = 'expired'
                expired_count += 1
            elif days_left <= 30:
                registration_status = 'warning'
                expiring_count += 1
                registration_days_left = days_left
        
        # Статус медкарты
        medical_status = 'valid'
        medical_days_left = 0
        if child.personal_file and child.personal_file.medical_card_expiry_date:
            days_left = (child.personal_file.medical_card_expiry_date - today_date).days
            if days_left < 0:
                medical_status = 'expired'
                expired_count += 1
            elif days_left <= 30:
                medical_status = 'warning'
                expiring_count += 1
                medical_days_left = days_left
        
        # Определение общего статуса
        if registration_status == 'expired' or medical_status == 'expired':
            expiry_status = 'expired'
        elif registration_status == 'warning' or medical_status == 'warning':
            expiry_status = 'warning'
        else:
            expiry_status = 'valid'
        
        children_data.append({
            'child': child,
            'parents': parents_list,
            'completion_percentage': child.get_documents_completion_percentage(),
            'registration_status': registration_status,
            'medical_status': medical_status,
            'registration_days_left': registration_days_left,
            'medical_days_left': medical_days_left,
            'expiry_status': expiry_status,
        })
    
    # Статистика
    total_children = children.count()
    active_files = children.filter(personal_file__status='active').count()
    avg_completion = sum(c['completion_percentage'] for c in children_data) / len(children_data) if children_data else 0
    
    context = {
        'children': page_obj,
        'children_data': children_data,
        'total_children': total_children,
        'active_files': active_files,
        'expiring_count': expiring_count,
        'expired_count': expired_count,
        'avg_completion': round(avg_completion, 1),
        'search_query': search_query,
        'status_filter': status_filter,
        'group_filter': group_filter,
        'groups': Group.objects.all(),
    }
    
    return render(request, 'children/personal_files_list.html', context)


# children/views.py - функция personal_file_detail

# children/views.py - добавьте отладку в функцию personal_file_detail

@login_required
def personal_file_detail(request, child_id):
    """Детальная страница личного дела ребенка"""
    child = get_object_or_404(Child, id=child_id)
    
    # Проверка прав доступа
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile'):
            messages.error(request, 'Профиль не найден')
            return redirect('dashboard')
        
        is_parent = ChildParent.objects.filter(
            child=child, 
            parent=request.user.parentprofile
        ).exists()
        
        if not is_parent:
            messages.error(request, 'У вас нет доступа к личному делу этого ребенка')
            return redirect('dashboard')
    
    # ОТЛАДКА
    print("\n" + "="*60)
    print(f"DEBUG: personal_file_detail для ребенка ID={child.id}, {child.full_name}")
    print("="*60)
    
    # ===== ПОЛУЧАЕМ ДАННЫЕ О РОДИТЕЛЯХ =====
    parents = []
    child_parents = ChildParent.objects.filter(child=child).select_related('parent__user')
    print(f"ChildParent записей: {child_parents.count()}")
    
    for rel in child_parents:
        parent = rel.parent
        print(f"  - Родитель: {parent.user.get_full_name()}, отношение: {rel.relation}")
        parents.append({
            'full_name': parent.full_name if parent.full_name else parent.user.get_full_name(),
            'relation': rel.get_relation_display(),
            'is_primary': rel.is_primary,
            'phone': parent.user.phone or parent.mobile_phone or '',
            'email': parent.user.email or '',
            'passport_series': getattr(parent, 'passport_series', ''),
            'passport_number': getattr(parent, 'passport_number', ''),
        })
    
    # ===== ПОЛУЧАЕМ ЗАЯВЛЕНИЯ =====
    applications = ChildApplication.objects.filter(child_record=child).order_by('-created_at')
    print(f"Заявлений: {applications.count()}")
    
    # ===== ПОЛУЧАЕМ ПРИКАЗЫ =====
    orders = EnrollmentOrder.objects.filter(child=child).order_by('-order_date')
    print(f"Приказов (EnrollmentOrder.filter(child=child)): {orders.count()}")
    
    # Пробуем найти приказы другим способом
    orders_by_name = EnrollmentOrder.objects.filter(
        Q(child__full_name=child.full_name) | 
        Q(application__child_record=child)
    ).order_by('-order_date')
    print(f"Приказов по имени: {orders_by_name.count()}")
    
    # ===== ПОЛУЧАЕМ ДОГОВОРЫ =====
    contracts = EducationContract.objects.filter(
        Q(child=child) | Q(child_full_name=child.full_name)
    ).order_by('-created_at')
    print(f"Договоров: {contracts.count()}")
    
    # ===== СОГЛАСИЯ =====
    print(f"Согласия: consent_data_processing={child.consent_data_processing}, "
          f"consent_photo_video={child.consent_photo_video}, "
          f"consent_medical_intervention={child.consent_medical_intervention}")
    
    print("="*60 + "\n")
    
    # ===== ФОТО РЕБЕНКА =====
    child_photo = None
    if child.photo:
        child_photo = child.photo
    elif child.application and child.application.child_photo:
        child_photo = child.application.child_photo
    
    # ===== ПРОЦЕНТ ЗАПОЛНЕНИЯ =====
    completion_percentage = child.get_documents_completion_percentage()
    
    context = {
        'child': child,
        'parents': parents,
        'applications': applications,
        'orders': orders,
        'contracts': contracts,
        'child_photo': child_photo,
        'completion_percentage': completion_percentage,
        'title': f'Личное дело: {child.full_name}',
    }
    
    return render(request, 'children/personal_file_detail.html', context)


@login_required
def personal_file_edit(request, child_id):
    """Редактирование личного дела (только для заведующей)"""
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может редактировать личное дело.')
        return redirect('children:personal_file_detail', child_id=child_id)
    
    child = get_object_or_404(Child, id=child_id)
    
    # Получаем или создаем PersonalFile
    try:
        personal_file = PersonalFile.objects.get(child=child)
    except PersonalFile.DoesNotExist:
        personal_file = PersonalFile(child=child)
    
    if request.method == 'POST':
        form = ChildForm(request.POST, request.FILES, instance=child)
        personal_form = PersonalFileForm(request.POST, instance=personal_file)
        
        if form.is_valid() and personal_form.is_valid():
            form.save()
            personal_form.save()
            messages.success(request, f'Личное дело ребенка {child.full_name} успешно обновлено!')
            return redirect('children:personal_file_detail', child_id=child.id)
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ChildForm(instance=child)
        personal_form = PersonalFileForm(instance=personal_file)
    
    return render(request, 'children/personal_file_edit.html', {
        'form': form,
        'personal_form': personal_form,
        'child': child,
        'title': f'Редактирование личного дела: {child.full_name}',
    })


@login_required
@csrf_exempt
def upload_child_document(request, child_id):
    """Загрузка документа в личное дело (только для заведующей)"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Доступ запрещен'})
    
    child = get_object_or_404(Child, id=child_id)
    
    if request.method == 'POST':
        doc_type = request.POST.get('document_type')
        doc_file = request.FILES.get('document_file')
        expiry_date = request.POST.get('expiry_date')
        
        if not doc_file:
            return JsonResponse({'success': False, 'error': 'Файл не выбран'})
        
        # Проверка типа файла
        if not doc_file.name.lower().endswith(('.pdf', '.jpg', '.jpeg', '.png')):
            return JsonResponse({'success': False, 'error': 'Разрешены только PDF, JPG, PNG'})
        
        # Сохраняем в соответствующее поле
        if doc_type == 'registration_certificate':
            child.registration_certificate = doc_file
            if expiry_date:
                child.registration_issued_date = expiry_date
        elif doc_type == 'medical_card':
            child.medical_card_file = doc_file
            if expiry_date and hasattr(child, 'personal_file'):
                child.personal_file.medical_card_expiry_date = expiry_date
                child.personal_file.save()
        elif doc_type == 'vaccination_card':
            child.vaccination_card = doc_file
        elif doc_type == 'birth_certificate':
            child.birth_certificate_file = doc_file
        else:
            return JsonResponse({'success': False, 'error': 'Неизвестный тип документа'})
        
        child.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Документ загружен',
            'file_url': doc_file.url,
            'file_name': doc_file.name,
        })
    
    return JsonResponse({'success': False, 'error': 'Метод не разрешен'})


@login_required
@csrf_exempt
def delete_child_document(request, child_id):
    """Удаление документа (только для заведующей)"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Доступ запрещен'})
    
    child = get_object_or_404(Child, id=child_id)
    data = json.loads(request.body)
    doc_type = data.get('document_type')
    
    if doc_type == 'registration_certificate':
        if child.registration_certificate:
            child.registration_certificate.delete()
            child.registration_certificate = None
    elif doc_type == 'medical_card':
        if child.medical_card_file:
            child.medical_card_file.delete()
            child.medical_card_file = None
    elif doc_type == 'vaccination_card':
        if child.vaccination_card:
            child.vaccination_card.delete()
            child.vaccination_card = None
    elif doc_type == 'birth_certificate':
        if child.birth_certificate_file:
            child.birth_certificate_file.delete()
            child.birth_certificate_file = None
    else:
        return JsonResponse({'success': False, 'error': 'Неизвестный тип документа'})
    
    child.save()
    
    return JsonResponse({'success': True, 'message': 'Документ удален'})


@login_required
@csrf_exempt
def update_consent(request, child_id):
    """Обновление согласия (только для заведующей)"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Доступ запрещен'})
    
    child = get_object_or_404(Child, id=child_id)
    data = json.loads(request.body)
    
    consent_type = data.get('consent_type')
    value = data.get('value')
    
    today = date.today()
    
    if consent_type == 'data_processing':
        child.consent_data_processing = value
        if value:
            child.consent_data_processing_date = today
    elif consent_type == 'photo_video':
        child.consent_photo_video = value
        if value:
            child.consent_photo_video_date = today
    elif consent_type == 'medical_intervention':
        child.consent_medical_intervention = value
        if value:
            child.consent_medical_intervention_date = today
    else:
        return JsonResponse({'success': False, 'error': 'Неизвестный тип согласия'})
    
    child.save()
    
    return JsonResponse({'success': True, 'message': 'Согласие обновлено'})


@login_required
def document_stats_api(request):
    """API для получения статистики документов"""
    if request.user.role != 'director':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    today = date.today()
    expiring_date = today + timedelta(days=30)
    
    expiring_count = PersonalFile.objects.filter(
        Q(registration_expiry_date__gte=today, registration_expiry_date__lte=expiring_date) |
        Q(medical_card_expiry_date__gte=today, medical_card_expiry_date__lte=expiring_date)
    ).count()
    
    expired_count = PersonalFile.objects.filter(
        Q(registration_expiry_date__lt=today) |
        Q(medical_card_expiry_date__lt=today)
    ).count()
    
    return JsonResponse({
        'expiring_count': expiring_count,
        'expired_count': expired_count
    })
    
    
from django.views.decorators.clickjacking import xframe_options_exempt    
import os
import mimetypes
from django.http import FileResponse, Http404
from django.conf import settings
    
@xframe_options_exempt
def view_file_modal(request, file_path):
    """
    Просмотр файла в модальном окне (отключена защита X-Frame-Options)
    """
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    if not os.path.exists(full_path):
        raise Http404("Файл не найден")
    
    # Определяем MIME тип
    mime_type, encoding = mimetypes.guess_type(full_path)
    if not mime_type:
        mime_type = 'application/octet-stream'
    
    response = FileResponse(open(full_path, 'rb'), content_type=mime_type)
    
    # Разрешаем встраивание в iframe
    response['X-Frame-Options'] = 'SAMEORIGIN'
    
    # Для PDF - открываем в браузере
    if mime_type == 'application/pdf':
        response['Content-Disposition'] = 'inline'
    
    return response


@xframe_options_exempt
def view_pdf(request, file_path):
    """Просмотр PDF файла без X-Frame-Options"""
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    if not os.path.exists(full_path):
        return HttpResponse('Файл не найден', status=404)
    
    with open(full_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type='application/pdf')
    
    # Разрешаем встраивание
    response['X-Frame-Options'] = 'SAMEORIGIN'
    response['Content-Disposition'] = 'inline'
    return response


@xframe_options_exempt
def view_media_file(request, file_path):
    """
    Просмотр медиа-файлов (изображения, PDF, документы) без ограничений iframe
    """
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    if not os.path.exists(full_path):
        raise Http404("Файл не найден")
    
    # Определяем MIME тип
    mime_type, encoding = mimetypes.guess_type(full_path)
    if not mime_type:
        mime_type = 'application/octet-stream'
    
    # Читаем файл
    with open(full_path, 'rb') as f:
        file_content = f.read()
    
    response = HttpResponse(file_content, content_type=mime_type)
    
    # Разрешаем встраивание в iframe
    response['X-Frame-Options'] = 'SAMEORIGIN'
    
    # Для изображений и PDF - показываем в браузере
    if mime_type in ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf']:
        response['Content-Disposition'] = 'inline'
    else:
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(full_path)}"'
    
    return response


from django.views.decorators.http import require_http_methods

@login_required
@require_http_methods(["POST"])
def upload_child_photo(request, child_id):
    """Загрузка фото ребенка через AJAX"""
    
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Нет прав для загрузки фото'}, status=403)
    
    child = get_object_or_404(Child, id=child_id)
    
    if 'photo' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'Файл не выбран'})
    
    photo = request.FILES['photo']
    
    # Проверка типа файла
    if not photo.content_type.startswith('image/'):
        return JsonResponse({'success': False, 'error': 'Можно загружать только изображения'})
    
    # Проверка размера (максимум 5MB)
    if photo.size > 5 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'Размер файла не должен превышать 5MB'})
    
    # Сохраняем фото
    child.photo = photo
    child.save()
    
    return JsonResponse({
        'success': True,
        'photo_url': child.photo.url,
        'child_name': child.full_name
    })
    
    
@login_required
@require_http_methods(["POST"])
def delete_child_photo(request, child_id):
    """Удаление фото ребенка"""
    
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Нет прав для удаления фото'}, status=403)
    
    child = get_object_or_404(Child, id=child_id)
    
    if child.photo:
        # Удаляем файл
        child.photo.delete()
        child.save()
        return JsonResponse({'success': True, 'message': 'Фото удалено'})
    
    return JsonResponse({'success': False, 'error': 'Фото не найдено'})
