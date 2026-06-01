# attendance/views.py
from shlex import quote

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import Http404, JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from datetime import datetime, time, timedelta, date
from calendar import monthrange, weekday
import json
import io
from django.conf import settings
import os
from docx import Document
from docx.shared import Pt, Inches

from .models import AbsenceDocument, AttendanceSheet, AttendanceRecord, ProductionCalendar, Meal
from .forms import AbsenceDocumentForm, AttendanceSheetForm, AttendanceRecordForm
from children.models import Child, ChildParent, Group


# ==================== ДЕКОРАТОРЫ ====================

def staff_required(view_func):
    """Проверка, что пользователь - сотрудник (воспитатель или заведующая)"""
    decorated_view_func = user_passes_test(
        lambda u: u.is_authenticated and u.role in ['teacher', 'director'],
        login_url='/accounts/login/'
    )(view_func)
    return decorated_view_func


def director_required(view_func):
    """Проверка, что пользователь - заведующая"""
    decorated_view_func = user_passes_test(
        lambda u: u.is_authenticated and u.role == 'director',
        login_url='/accounts/login/'
    )(view_func)
    return decorated_view_func


def teacher_required(view_func):
    """Проверка, что пользователь - воспитатель"""
    decorated_view_func = user_passes_test(
        lambda u: u.is_authenticated and u.role == 'teacher',
        login_url='/accounts/login/'
    )(view_func)
    return decorated_view_func


def get_teacher_group(user):
    """Получает группу воспитателя"""
    try:
        return Group.objects.filter(teacher=user).first()
    except:
        return None


def get_teacher_children(user):
    """Получает список детей для воспитателя"""
    teacher_group = get_teacher_group(user)
    if teacher_group:
        return Child.objects.filter(group=teacher_group, is_active=True)
    return Child.objects.none()


# ==================== ОСНОВНАЯ ПАНЕЛЬ ====================

@login_required
@staff_required
def attendance_dashboard(request):
    """Главная страница посещаемости для воспитателей"""
    today = timezone.now().date()
    teacher_group = get_teacher_group(request.user)
    
    if not teacher_group and request.user.role == 'teacher':
        messages.error(request, 'Вам не назначена группа.')
        return render(request, 'attendance/no_group.html')
    
    if teacher_group:
        children = Child.objects.filter(group=teacher_group, is_active=True)
        
        # Получаем данные о посещаемости за сегодня из табеля
        current_month = today.month
        current_year = today.year
        current_day = today.day
        
        attendance_data = []
        present_count = 0
        absent_count = 0
        sick_count = 0
        vacation_count = 0
        
        # Получаем текущий табель
        try:
            sheet = AttendanceSheet.objects.get(
                group=teacher_group,
                month=current_month,
                year=current_year
            )
        except AttendanceSheet.DoesNotExist:
            sheet = None
        
        # Получаем производственный календарь для определения выходных
        is_holiday = False
        try:
            cal_entry = ProductionCalendar.objects.get(date=today)
            is_holiday = cal_entry.is_holiday
        except ProductionCalendar.DoesNotExist:
            is_holiday = today.weekday() >= 5  # Суббота и воскресенье по умолчанию
        
        for child in children:
            status = 'absent'
            if sheet and not is_holiday:
                try:
                    record = AttendanceRecord.objects.get(sheet=sheet, child=child)
                    status = record.get_day_status(current_day)
                except AttendanceRecord.DoesNotExist:
                    status = 'absent'
            elif is_holiday:
                status = 'weekend'
            
            # Считаем статусы
            if status == 'present':
                present_count += 1
            elif status == 'absent':
                absent_count += 1
            elif status == 'sick':
                sick_count += 1
            elif status == 'vacation':
                vacation_count += 1
            
            # Получаем питание за сегодня
            meals_today = Meal.objects.filter(
                child=child, 
                date=today,
                eaten=True
            ).values_list('meal_type', flat=True)
            
            attendance_data.append({
                'child': child,
                'attendance': None,
                'meals_today': list(meals_today),
                'status': status
            })
        
        # Статистика
        total_children = children.count()
        attendance_percentage = round((present_count / total_children * 100), 1) if total_children > 0 else 0
        
        # Данные за неделю для графика
        weekly_data = get_weekly_attendance(teacher_group)
        weekly_labels = [f"{day['date'].strftime('%d.%m')}" for day in weekly_data]
        weekly_percentages = [day['percentage'] for day in weekly_data]
        weekly_average = round(sum(weekly_percentages) / len(weekly_percentages), 1) if weekly_percentages else 0
        
        context = {
            'today': today,
            'teacher_group': teacher_group,
            'children': attendance_data,
            'total_children': total_children,
            'present_count': present_count,
            'absent_count': absent_count,
            'sick_count': sick_count,
            'vacation_count': vacation_count,
            'attendance_percentage': attendance_percentage,
            'weekly_average': weekly_average,
            'weekly_labels': json.dumps(weekly_labels),
            'weekly_data': weekly_percentages,
            'meal_types': [
                ('breakfast', 'Завтрак'),
                ('lunch', 'Обед'),
                ('snack', 'Полдник'),
            ],
        }
        
        return render(request, 'attendance/dashboard.html', context)
    else:
        return redirect('attendance:statistics')


def get_weekly_attendance(group):
    """Получает данные о посещаемости за последние 7 дней"""
    today = timezone.now().date()
    weekly_data = []
    
    for i in range(6, -1, -1):
        date_obj = today - timedelta(days=i)
        
        total_children = Child.objects.filter(
            group=group,
            is_active=True
        ).count()
        
        # Проверяем, является ли день выходным
        try:
            cal_entry = ProductionCalendar.objects.get(date=date_obj)
            is_holiday = cal_entry.is_holiday
        except ProductionCalendar.DoesNotExist:
            is_holiday = date_obj.weekday() >= 5
        
        present_count = 0
        if not is_holiday:
            try:
                sheet = AttendanceSheet.objects.get(
                    group=group,
                    month=date_obj.month,
                    year=date_obj.year
                )
                for record in sheet.records.all():
                    status = record.get_day_status(date_obj.day)
                    if status == 'present':
                        present_count += 1
            except AttendanceSheet.DoesNotExist:
                present_count = 0
        
        percentage = round((present_count / total_children * 100), 1) if total_children > 0 else 0
        
        weekly_data.append({
            'date': date_obj,
            'percentage': percentage
        })
    
    return weekly_data


# ==================== AJAX ОБНОВЛЕНИЯ ====================

@login_required
@staff_required
def update_attendance_ajax(request):
    """AJAX обновление посещаемости"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            child_id = data.get('child_id')
            date_str = data.get('date')
            status = data.get('status')
            
            child = get_object_or_404(Child, id=child_id)
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Проверка доступа
            if request.user.role == 'teacher':
                teacher_group = get_teacher_group(request.user)
                if not teacher_group or child.group != teacher_group:
                    return JsonResponse({'success': False, 'error': 'Нет доступа'})
            
            # Проверяем, является ли день выходным
            try:
                cal_entry = ProductionCalendar.objects.get(date=date_obj)
                is_holiday = cal_entry.is_holiday
            except ProductionCalendar.DoesNotExist:
                is_holiday = date_obj.weekday() >= 5
            
            if is_holiday:
                return JsonResponse({'success': False, 'error': 'Нельзя отмечать посещаемость в выходной день'})
            
            # Получаем или создаем табель
            sheet, created = AttendanceSheet.objects.get_or_create(
                group=child.group,
                month=date_obj.month,
                year=date_obj.year,
                defaults={
                    'created_by': request.user,
                    'is_draft': True
                }
            )
            
            # Получаем или создаем запись
            record, rec_created = AttendanceRecord.objects.get_or_create(
                sheet=sheet,
                child=child
            )
            
            # Обновляем статус
            record.set_day_status(date_obj.day, status)
            record.save()
            
            return JsonResponse({'success': True, 'status': status})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


@login_required
@staff_required
def update_meal_ajax(request):
    """AJAX обновление питания"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            child_id = data.get('child_id')
            date_str = data.get('date')
            meal_type = data.get('meal_type')
            checked = data.get('checked')
            
            child = get_object_or_404(Child, id=child_id)
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Проверка доступа
            if request.user.role == 'teacher':
                teacher_group = get_teacher_group(request.user)
                if not teacher_group or child.group != teacher_group:
                    return JsonResponse({'success': False, 'error': 'Нет доступа'})
            
            if checked:
                meal, created = Meal.objects.get_or_create(
                    child=child,
                    date=date_obj,
                    meal_type=meal_type,
                    defaults={'eaten': True}
                )
                if not created:
                    meal.eaten = True
                    meal.save()
            else:
                Meal.objects.filter(
                    child=child,
                    date=date_obj,
                    meal_type=meal_type
                ).delete()
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


# ==================== ТАБЕЛИ ПОСЕЩАЕМОСТИ ====================

@login_required
def attendance_sheet_list(request):
    """Список табелей посещаемости"""
    if request.user.role == 'teacher':
        sheets = AttendanceSheet.objects.filter(
            group__teacher=request.user
        ).order_by('-year', '-month')
        
        for sheet in sheets:
            sheet.records_count = sheet.records.count()
        
        return render(request, 'attendance/sheet_list.html', {
            'sheets': sheets,
            'is_teacher': True
        })
    
    elif request.user.role == 'director':
        sheets = AttendanceSheet.objects.all().order_by('-year', '-month')
        
        for sheet in sheets:
            sheet.records_count = sheet.records.count()
        
        return render(request, 'attendance/sheet_list.html', {
            'sheets': sheets,
            'is_director': True
        })
    
    return redirect('attendance:attendance_dashboard')


# attendance/views.py
@login_required
def mark_all_workdays_present(request, sheet_id):
    """Отметить все рабочие дни (кроме выходных) как присутствие (Я) для всех детей"""
    from calendar import weekday
    
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    if request.user.role != 'teacher':
        messages.error(request, 'Только воспитатель может отмечать присутствие.')
        return redirect('attendance:attendance_sheet_list')
    
    if sheet.group.teacher != request.user:
        messages.error(request, 'У вас нет доступа к этому табелю.')
        return redirect('attendance:attendance_sheet_list')
    
    if sheet.is_approved:
        messages.error(request, 'Этот табель уже утвержден и не может быть изменен.')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    # Получаем производственный календарь для определения выходных
    calendar_entries = {}
    for day in range(1, sheet.get_total_days() + 1):
        current_date = date(sheet.year, sheet.month, day)
        try:
            entry = ProductionCalendar.objects.get(date=current_date)
            is_holiday = entry.is_holiday
        except ProductionCalendar.DoesNotExist:
            is_holiday = weekday(sheet.year, sheet.month, day) >= 5
        
        calendar_entries[day] = is_holiday
    
    records = sheet.records.all()
    days_in_month = sheet.get_total_days()
    updated_count = 0
    marked_days = 0
    
    for record in records:
        changes = 0
        for day in range(1, days_in_month + 1):
            # Пропускаем выходные и праздничные дни
            if calendar_entries[day]:
                continue
            
            field_name = f'day_{day}'
            old_status = getattr(record, field_name, '')
            if old_status != 'present':
                setattr(record, field_name, 'present')
                changes += 1
                marked_days += 1
        
        if changes > 0:
            record.save()
            updated_count += 1
    
    messages.success(request, 
        f'Все рабочие дни отмечены как "Присутствует"! '
        f'Обновлено {updated_count} записей, отмечено {marked_days} дней.')
    return redirect('attendance:attendance_sheet_edit', sheet_id=sheet.id)


# attendance/views.py
@login_required
def mark_all_present(request, sheet_id):
    """Отметить все дни (включая выходные) как присутствие (Я) для всех детей"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    if request.user.role != 'teacher':
        messages.error(request, 'Только воспитатель может отмечать присутствие.')
        return redirect('attendance:attendance_sheet_list')
    
    if sheet.group.teacher != request.user:
        messages.error(request, 'У вас нет доступа к этому табелю.')
        return redirect('attendance:attendance_sheet_list')
    
    if sheet.is_approved:
        messages.error(request, 'Этот табель уже утвержден и не может быть изменен.')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    records = sheet.records.all()
    days_in_month = sheet.get_total_days()
    updated_count = 0
    marked_days = 0
    
    for record in records:
        changes = 0
        for day in range(1, days_in_month + 1):
            field_name = f'day_{day}'
            old_status = getattr(record, field_name, '')
            if old_status != 'present':
                setattr(record, field_name, 'present')
                changes += 1
                marked_days += 1
        
        if changes > 0:
            record.save()
            updated_count += 1
    
    messages.success(request, 
        f'Все дни отмечены как "Присутствует"! '
        f'Обновлено {updated_count} записей, отмечено {marked_days} дней.')
    return redirect('attendance:attendance_sheet_edit', sheet_id=sheet.id)


@login_required
@teacher_required
def attendance_sheet_create(request):
    """Создание нового табеля на месяц"""
    teacher_group = Group.objects.filter(teacher=request.user).first()
    
    if not teacher_group:
        messages.error(request, 'Вам не назначена группа.')
        return redirect('attendance:attendance_sheet_list')
    
    if request.method == 'POST':
        form = AttendanceSheetForm(request.POST)
        if form.is_valid():
            group = form.cleaned_data['group']
            month = form.cleaned_data['month']
            year = form.cleaned_data['year']
            
            if group.teacher != request.user:
                messages.error(request, 'У вас нет доступа к этой группе.')
                return redirect('attendance:attendance_sheet_create')
            
            sheet, created = AttendanceSheet.objects.get_or_create(
                group=group,
                month=month,
                year=year,
                defaults={
                    'created_by': request.user,
                    'is_draft': True
                }
            )
            
            if not created:
                messages.warning(request, f'Табель за {sheet.get_month_name()} {year} уже существует.')
                return redirect('attendance:attendance_sheet_edit', sheet_id=sheet.id)
            
            # Создаем записи для всех детей в группе
            children = Child.objects.filter(group=group, is_active=True)
            created_count = 0
            
            for child in children:
                record, record_created = AttendanceRecord.objects.get_or_create(
                    sheet=sheet,
                    child=child
                )
                if record_created:
                    created_count += 1
            
            messages.success(request, 
                f'Табель за {sheet.get_month_name()} {year} успешно создан! '
                f'Добавлено {created_count} записей для детей.')
            
            return redirect('attendance:attendance_sheet_edit', sheet_id=sheet.id)
    else:
        form = AttendanceSheetForm(initial={'group': teacher_group})
    
    children_in_group = Child.objects.filter(group=teacher_group, is_active=True)
    
    return render(request, 'attendance/sheet_create.html', {
        'form': form,
        'teacher_group': teacher_group,
        'children_count': children_in_group.count()
    })



def test_save_attendance(request, sheet_id):
    """Тестовая функция для сохранения"""
    from django.http import JsonResponse
    
    sheet = AttendanceSheet.objects.get(id=sheet_id)
    record = sheet.records.first()
    
    # Сохраняем тестовые данные
    record.day_1 = 'present'
    record.day_2 = 'present'
    record.day_3 = 'present'
    record.day_4 = 'present'
    record.day_5 = 'present'
    record.save()
    
    return JsonResponse({
        'success': True,
        'child': record.child.full_name,
        'day_1': record.day_1,
        'day_2': record.day_2,
        'day_3': record.day_3,
        'day_4': record.day_4,
        'day_5': record.day_5,
    })


@login_required
def attendance_sheet_view(request, sheet_id):
    """Просмотр табеля"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    records = sheet.records.select_related('child').order_by('child__full_name')
    
    # Проверка прав
    if request.user.role == 'teacher' and sheet.group.teacher != request.user:
        messages.error(request, 'У вас нет доступа к этому табелю.')
        return redirect('attendance:attendance_sheet_list')
    
    days_in_month = sheet.get_total_days()
    
    # Подсчет статистики
    children_stats = []
    total_present = 0
    total_absent = 0
    total_sick = 0
    total_vacation = 0
    
    for record in records:
        present_count = 0
        absent_count = 0
        sick_count = 0
        vacation_count = 0
        
        # Подсчитываем статусы по дням
        for day in range(1, days_in_month + 1):
            status = getattr(record, f'day_{day}', '')
            if status == 'present':
                present_count += 1
            elif status == 'absent':
                absent_count += 1
            elif status == 'sick':
                sick_count += 1
            elif status == 'vacation':
                vacation_count += 1
        
        # Рассчитываем процент посещаемости
        if days_in_month > 0:
            attendance_percent = round((present_count / days_in_month) * 100, 1)
        else:
            attendance_percent = 0.0
        
        children_stats.append({
            'child': record.child,
            'present': present_count,
            'absent': absent_count,
            'sick': sick_count,
            'vacation': vacation_count,
            'attendance_percent': attendance_percent
        })
        
        total_present += present_count
        total_absent += absent_count
        total_sick += sick_count
        total_vacation += vacation_count
    
    # Общая статистика по группе
    total_possible = records.count() * days_in_month
    if total_possible > 0:
        avg_attendance = round((total_present / total_possible) * 100, 1)
    else:
        avg_attendance = 0.0
    
    group_stats = {
        'total_children': records.count(),
        'total_present': total_present,
        'total_absent': total_absent,
        'total_sick': total_sick,
        'total_vacation': total_vacation,
        'avg_attendance': avg_attendance
    }
    
    return render(request, 'attendance/sheet_view.html', {
        'sheet': sheet,
        'children_stats': children_stats,
        'group_stats': group_stats,
        'days_in_month': days_in_month,
        'month_name': sheet.get_month_name(),
        'can_edit': request.user.role == 'teacher' and not sheet.is_approved,
        'can_approve': request.user.role == 'director' and not sheet.is_approved
    })


# attendance/views.py
@login_required
def attendance_sheet_reset(request, sheet_id):
    """Сброс всех статусов табеля"""
    if request.user.role != 'teacher':
        messages.error(request, 'Только воспитатель может сбрасывать статусы.')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet_id)
    
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    # Проверка прав
    if sheet.group.teacher != request.user:
        messages.error(request, 'У вас нет доступа к этому табелю.')
        return redirect('attendance:attendance_sheet_list')
    
    if sheet.is_approved:
        messages.error(request, 'Этот табель уже утвержден и не может быть изменен.')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    if request.method == 'POST':
        records = sheet.records.all()
        days_in_month = sheet.get_total_days()
        
        for record in records:
            for day in range(1, days_in_month + 1):
                setattr(record, f'day_{day}', '')
            record.save()
        
        messages.success(request, f'Все статусы табеля за {sheet.get_month_name()} {sheet.year} сброшены!')
        return redirect('attendance:attendance_sheet_edit', sheet_id=sheet.id)
    
    return render(request, 'attendance/sheet_reset.html', {'sheet': sheet, 'month_name': sheet.get_month_name()})


@login_required
@director_required
def attendance_sheet_approve(request, sheet_id):
    """Утверждение табеля заведующей"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    if sheet.is_approved:
        messages.warning(request, 'Этот табель уже утвержден.')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    if request.method == 'POST':
        sheet.is_approved = True
        sheet.is_draft = False
        sheet.approved_by = request.user
        sheet.approved_at = timezone.now()
        sheet.save()
        
        messages.success(request, f'Табель за {sheet.get_month_name()} {sheet.year} успешно утвержден!')
        return redirect('attendance:attendance_sheet_list')
    
    return render(request, 'attendance/sheet_approve.html', {
        'sheet': sheet,
        'month_name': sheet.get_month_name()
    })


@login_required
@director_required
def attendance_sheet_return(request, sheet_id):
    """Вернуть табель на доработку"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        sheet.is_approved = False
        sheet.is_draft = True
        sheet.approved_by = None
        sheet.approved_at = None
        sheet.notes = reason
        sheet.save()
        
        messages.warning(request, f'Табель возвращен на доработку. Причина: {reason}')
        return redirect('attendance:attendance_sheet_list')
    
    return render(request, 'attendance/sheet_return.html', {
        'sheet': sheet,
        'month_name': sheet.get_month_name()
    })


@login_required
@director_required
def attendance_sheet_export_word(request, sheet_id):
    """Экспорт табеля в Word (форма 0504608)"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    records = sheet.records.select_related('child').order_by('child__full_name')
    
    # Создаем документ
    document = Document()
    
    # Заголовок
    title = document.add_heading('Табель учета посещаемости детей', 0)
    title.alignment = 1
    
    # Информация о табеле
    document.add_paragraph(f'Группа: {sheet.group.name}')
    document.add_paragraph(f'Месяц: {sheet.get_month_name()} {sheet.year}')
    document.add_paragraph(f'Дата заполнения: {timezone.now().strftime("%d.%m.%Y")}')
    
    if sheet.is_approved:
        document.add_paragraph(f'Утвержден: {sheet.approved_by.get_full_name()} {sheet.approved_at.strftime("%d.%m.%Y")}')
    else:
        document.add_paragraph('Статус: ЧЕРНОВИК')
    
    document.add_paragraph()
    
    # Таблица посещаемости
    days_in_month = sheet.get_total_days()
    table = document.add_table(rows=len(records) + 2, cols=days_in_month + 2)
    table.style = 'Table Grid'
    
    # Заголовок с днями
    header_row = table.rows[0]
    header_row.cells[0].text = '№'
    header_row.cells[1].text = 'ФИО ребенка'
    
    for day in range(1, days_in_month + 1):
        header_row.cells[day + 1].text = str(day)
    
    # Вторая строка с отметками о выходных
    weekend_row = table.rows[1]
    weekend_row.cells[0].text = ''
    weekend_row.cells[1].text = 'Дни недели'
    
    day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    for day in range(1, days_in_month + 1):
        week_day = weekday(sheet.year, sheet.month, day)
        weekend_row.cells[day + 1].text = day_names[week_day]
    
    # Данные по детям - используем правильные коды
    status_display = {
        'present': 'Я',
        'absent': 'Н',
        'sick': 'НБ',
        'vacation': 'НУ',
        'weekend': 'В',
        '': '-'
    }
    
    for idx, record in enumerate(records, start=1):
        row = table.rows[idx + 1]
        row.cells[0].text = str(idx)
        row.cells[1].text = record.child.full_name
        
        for day in range(1, days_in_month + 1):
            status = record.get_day_status(day)
            # Проверяем, является ли день выходным
            try:
                cal_entry = ProductionCalendar.objects.get(date=date(sheet.year, sheet.month, day))
                is_holiday = cal_entry.is_holiday
            except ProductionCalendar.DoesNotExist:
                is_holiday = weekday(sheet.year, sheet.month, day) >= 5
            
            if is_holiday:
                display = 'В'
            else:
                display = status_display.get(status, '-')
            row.cells[day + 1].text = display
    
    # Сохраняем документ
    file_stream = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    
    filename = f'Табель_{sheet.group.name}_{sheet.year}_{sheet.month}.docx'
    response = HttpResponse(
        file_stream.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


# ==================== СТАТИСТИКА И АНАЛИТИКА ====================

@login_required
@director_required
def attendance_statistics(request):
    """Статистика посещаемости для заведующей"""
    period = request.GET.get('period', 'month')
    group_id = request.GET.get('group', '')
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    
    end_date = timezone.now().date()
    if period == 'week':
        start_date = end_date - timedelta(days=7)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    elif period == 'quarter':
        start_date = end_date - timedelta(days=90)
    elif period == 'year':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=30)
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    groups = Group.objects.all()
    selected_group = None
    if group_id:
        selected_group = get_object_or_404(Group, id=group_id)
        children = Child.objects.filter(group=selected_group, is_active=True)
    else:
        children = Child.objects.filter(is_active=True)
    
    total_days = (end_date - start_date).days + 1
    total_children = children.count()
    
    daily_stats = []
    current_date = start_date
    while current_date <= end_date:
        present_count = 0
        
        # Проверяем, является ли день выходным
        try:
            cal_entry = ProductionCalendar.objects.get(date=current_date)
            is_holiday = cal_entry.is_holiday
        except ProductionCalendar.DoesNotExist:
            is_holiday = current_date.weekday() >= 5
        
        if not is_holiday:
            try:
                sheet = AttendanceSheet.objects.get(
                    group=selected_group if selected_group else groups.first(),
                    month=current_date.month,
                    year=current_date.year
                )
                for record in sheet.records.all():
                    status = record.get_day_status(current_date.day)
                    if status == 'present':
                        present_count += 1
            except:
                present_count = 0
        
        percentage = round((present_count / total_children) * 100, 1) if total_children > 0 else 0
        
        daily_stats.append({
            'date': current_date,
            'present': present_count,
            'absent': total_children - present_count,
            'total': total_children,
            'percentage': percentage
        })
        current_date += timedelta(days=1)
    
    context = {
        'daily_stats': daily_stats,
        'start_date': start_date,
        'end_date': end_date,
        'total_children': total_children,
        'total_days': total_days,
        'groups': groups,
        'selected_group': selected_group,
        'period': period,
        'daily_labels': json.dumps([stat['date'].strftime('%d.%m') for stat in daily_stats]),
        'daily_percentages': json.dumps([stat['percentage'] for stat in daily_stats]),
    }
    
    return render(request, 'attendance/statistics.html', context)


@login_required
@director_required
def attendance_analytics(request):
    """Аналитика посещаемости"""
    period = request.GET.get('period', '6months')
    group_id = request.GET.get('group', '')
    
    end_date = timezone.now().date()
    if period == '3months':
        start_date = end_date - timedelta(days=90)
    elif period == 'year':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=180)
    
    groups = Group.objects.all()
    selected_group = None
    if group_id:
        selected_group = get_object_or_404(Group, id=group_id)
        children = Child.objects.filter(group=selected_group, is_active=True)
    else:
        children = Child.objects.filter(is_active=True)
    
    monthly_stats = []
    current_date = start_date.replace(day=1)
    
    while current_date <= end_date:
        if current_date.month == 12:
            next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            next_month = current_date.replace(month=current_date.month + 1, day=1)
        
        month_end = next_month - timedelta(days=1)
        if month_end > end_date:
            month_end = end_date
        
        total_days_in_month = (month_end - current_date).days + 1
        total_possible = children.count() * total_days_in_month
        actual_attendance = 0
        
        # Получаем данные из табелей
        sheets = AttendanceSheet.objects.filter(
            group__in=[g for g in groups] if not selected_group else [selected_group],
            month=current_date.month,
            year=current_date.year
        )
        
        for sheet in sheets:
            for record in sheet.records.all():
                for day in range(1, total_days_in_month + 1):
                    if record.get_day_status(day) == 'present':
                        actual_attendance += 1
        
        percentage = round((actual_attendance / total_possible) * 100, 1) if total_possible > 0 else 0
        
        monthly_stats.append({
            'month': current_date.strftime('%Y-%m'),
            'month_name': current_date.strftime('%B %Y'),
            'percentage': percentage,
            'total_children': children.count(),
            'actual_attendance': actual_attendance,
            'total_days': total_days_in_month
        })
        
        current_date = next_month
    
    context = {
        'monthly_stats': monthly_stats,
        'start_date': start_date,
        'end_date': end_date,
        'groups': groups,
        'selected_group': selected_group,
        'period': period,
        'monthly_labels': json.dumps([stat['month_name'] for stat in monthly_stats]),
        'monthly_percentages': json.dumps([stat['percentage'] for stat in monthly_stats]),
    }
    
    return render(request, 'attendance/analytics.html', context)


@login_required
@director_required
def generate_attendance_report(request):
    """Генерация отчета по посещаемости в Word"""
    period = request.GET.get('period', 'month')
    group_id = request.GET.get('group', '')
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    
    end_date = timezone.now().date()
    if period == 'week':
        start_date = end_date - timedelta(days=7)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    elif period == 'quarter':
        start_date = end_date - timedelta(days=90)
    elif period == 'year':
        start_date = end_date - timedelta(days=365)
    else:
        start_date = end_date - timedelta(days=30)
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    selected_group = None
    if group_id:
        selected_group = get_object_or_404(Group, id=group_id)
        children = Child.objects.filter(group=selected_group, is_active=True)
        group_name = selected_group.name
    else:
        children = Child.objects.filter(is_active=True)
        group_name = "Все группы"
    
    document = Document()
    
    title = document.add_heading('Отчет по посещаемости', 0)
    title.alignment = 1
    
    document.add_paragraph(f'Период: с {start_date.strftime("%d.%m.%Y")} по {end_date.strftime("%d.%m.%Y")}')
    document.add_paragraph(f'Группа: {group_name}')
    document.add_paragraph(f'Сформировано: {timezone.now().strftime("%d.%m.%Y %H:%M")}')
    document.add_paragraph(f'Заведующая: {request.user.get_full_name()}')
    document.add_paragraph()
    
    total_days = (end_date - start_date).days + 1
    total_children = children.count()
    total_possible_attendance = total_children * total_days
    actual_attendance = 0
    
    # Подсчет посещаемости
    current_date = start_date
    while current_date <= end_date:
        # Проверяем, является ли день выходным
        try:
            cal_entry = ProductionCalendar.objects.get(date=current_date)
            is_holiday = cal_entry.is_holiday
        except ProductionCalendar.DoesNotExist:
            is_holiday = current_date.weekday() >= 5
        
        if not is_holiday:
            try:
                if selected_group:
                    sheet = AttendanceSheet.objects.get(
                        group=selected_group,
                        month=current_date.month,
                        year=current_date.year
                    )
                    for record in sheet.records.all():
                        if record.get_day_status(current_date.day) == 'present':
                            actual_attendance += 1
                else:
                    sheets = AttendanceSheet.objects.filter(
                        month=current_date.month,
                        year=current_date.year
                    )
                    for sheet in sheets:
                        for record in sheet.records.all():
                            if record.get_day_status(current_date.day) == 'present':
                                actual_attendance += 1
            except AttendanceSheet.DoesNotExist:
                pass
            except Exception as e:
                print(f"Ошибка при подсчете: {e}")
        
        current_date += timedelta(days=1)
    
    overall_percentage = round((actual_attendance / total_possible_attendance) * 100, 1) if total_possible_attendance > 0 else 0
    
    stats_heading = document.add_heading('Общая статистика', level=2)
    stats_table = document.add_table(rows=4, cols=2)
    stats_table.style = 'Table Grid'
    
    stats_data = [
        ['Общее количество детей', str(total_children)],
        ['Период отчета', f'{total_days} дней'],
        ['Всего возможных посещений', str(total_possible_attendance)],
        ['Фактических посещений', f'{actual_attendance} ({overall_percentage}%)']
    ]
    
    for i, (label, value) in enumerate(stats_data):
        stats_table.rows[i].cells[0].text = label
        stats_table.rows[i].cells[1].text = value
    
    file_stream = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)
    
    filename = f'attendance_report_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.docx'
    response = HttpResponse(
        file_stream.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response

@login_required
def attendance_sheet_edit(request, sheet_id):
    """Редактирование табеля с учетом производственного календаря"""
    from calendar import weekday
    from datetime import date
    
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    # Проверка прав
    if request.user.role == 'teacher':
        if sheet.group.teacher != request.user:
            messages.error(request, 'У вас нет доступа к этому табелю.')
            return redirect('attendance:attendance_sheet_list')
        
        if sheet.is_approved:
            messages.error(request, 'Этот табель уже утвержден и не может быть изменен.')
            return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    # Получаем производственный календарь на месяц
    calendar_entries = {}
    for day in range(1, sheet.get_total_days() + 1):
        current_date = date(sheet.year, sheet.month, day)
        try:
            entry = ProductionCalendar.objects.get(date=current_date)
            calendar_entries[day] = {
                'is_holiday': entry.is_holiday,
                'is_working_saturday': entry.is_working_saturday,
                'holiday_name': entry.holiday_name
            }
        except ProductionCalendar.DoesNotExist:
            is_weekend = weekday(sheet.year, sheet.month, day) >= 5
            calendar_entries[day] = {
                'is_holiday': is_weekend,
                'is_working_saturday': False,
                'holiday_name': 'Выходной' if is_weekend else ''
            }
    
    # Получаем записи
    records = list(sheet.records.select_related('child').order_by('child__full_name'))
    
    # Восстанавливаем записи при необходимости
    children_in_group = Child.objects.filter(group=sheet.group, is_active=True)
    if len(records) != children_in_group.count():
        for child in children_in_group:
            record, created = AttendanceRecord.objects.get_or_create(sheet=sheet, child=child)
            if created:
                records.append(record)
        records = list(sheet.records.select_related('child').order_by('child__full_name'))
    
    # Обработка POST запроса (сохранение)
    if request.method == 'POST':
        print("\n" + "="*70)
        print("🔵 СОХРАНЕНИЕ ТАБЕЛЯ")
        print("="*70)
        
        saved_count = 0
        
        for idx, record in enumerate(records):
            changes = 0
            
            # Сохраняем статусы для каждого дня
            for day in range(1, sheet.get_total_days() + 1):
                field_name = f'day_{day}'
                if field_name in request.POST and not calendar_entries[day]['is_holiday']:
                    # Получаем массив значений для этого дня
                    day_values = request.POST.getlist(field_name)
                    
                    # Берем значение для текущего ребенка по индексу
                    if idx < len(day_values):
                        new_status = day_values[idx]
                        old_status = getattr(record, field_name, '')
                        
                        if old_status != new_status:
                            setattr(record, field_name, new_status)
                            changes += 1
                            print(f"  {record.child.full_name} день {day}: {old_status} -> {new_status}")
            
            # Сохраняем примечания
            notes_key = f'notes_{record.id}'
            if notes_key in request.POST:
                new_notes = request.POST[notes_key]
                if record.notes != new_notes:
                    record.notes = new_notes
                    changes += 1
            
            if changes > 0:
                record.save()
                saved_count += 1
                print(f"  ✅ Сохранено {changes} изменений для {record.child.full_name}")
            else:
                print(f"  ⏭️ Нет изменений для {record.child.full_name}")
        
        if saved_count > 0:
            messages.success(request, f'Табель сохранен! Обновлено {saved_count} записей.')
        else:
            messages.info(request, 'Изменений не обнаружено.')
        
        # Перенаправление на страницу просмотра
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    # GET запрос - отображение формы
    days_in_month = sheet.get_total_days()
    
    # Данные о днях (выходные)
    calendar_data = []
    for day in range(1, days_in_month + 1):
        calendar_data.append({
            'day': day,
            'is_holiday': calendar_entries[day]['is_holiday'],
            'holiday_name': calendar_entries[day]['holiday_name'],
            'is_weekend': weekday(sheet.year, sheet.month, day) >= 5
        })
    
    # Подсчет общей статистики для легенды
    total_stats = {
        'present': 0,
        'absent': 0,
        'sick': 0,
        'vacation': 0,
        'weekend': 0,
        'empty': 0
    }
    
    # Подсчет выходных дней
    for day in range(1, days_in_month + 1):
        if calendar_entries[day]['is_holiday']:
            total_stats['weekend'] += 1
    
    # Данные о детях и их статусах
    children_data = []
    for record in records:
        child_statuses = []
        present_count = 0
        
        for day in range(1, days_in_month + 1):
            is_holiday = calendar_entries[day]['is_holiday']
            if is_holiday:
                status = 'weekend'
            else:
                status = getattr(record, f'day_{day}', '')
            
            # Подсчет общей статистики
            if not is_holiday:
                if status == 'present':
                    total_stats['present'] += 1
                elif status == 'absent':
                    total_stats['absent'] += 1
                elif status == 'sick':
                    total_stats['sick'] += 1
                elif status == 'vacation':
                    total_stats['vacation'] += 1
                elif status == '':
                    total_stats['empty'] += 1
            
            child_statuses.append({
                'day': day,
                'status': status,
                'is_holiday': is_holiday
            })
            if status == 'present':
                present_count += 1
        
        print(f"📊 {record.child.full_name}: присутствует {present_count} дней из {days_in_month}")
        
        children_data.append({
            'record_id': record.id,
            'child': record.child,
            'statuses': child_statuses,
            'notes': record.notes,
            'present_count': present_count
        })
    
    return render(request, 'attendance/sheet_edit.html', {
        'sheet': sheet,
        'children_data': children_data,
        'calendar_data': calendar_data,
        'days_in_month': days_in_month,
        'month_name': sheet.get_month_name(),
        'total_stats': total_stats,
        'total_children': len(records),
    })

@login_required
def restore_attendance_records(request, sheet_id):
    """Восстановление записей для всех детей в группе"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    if request.user.role != 'teacher':
        messages.error(request, 'Только воспитатель может восстанавливать записи.')
        return redirect('attendance:attendance_sheet_list')
    
    if sheet.group.teacher != request.user:
        messages.error(request, 'У вас нет доступа к этому табелю.')
        return redirect('attendance:attendance_sheet_list')
    
    if sheet.is_approved:
        messages.error(request, 'Этот табель уже утвержден и не может быть изменен.')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    # Получаем всех активных детей в группе
    children = Child.objects.filter(group=sheet.group, is_active=True)
    created_count = 0
    
    for child in children:
        record, created = AttendanceRecord.objects.get_or_create(sheet=sheet, child=child)
        if created:
            created_count += 1
            print(f"Создана запись для {child.full_name}")
    
    if created_count > 0:
        messages.success(request, f'Восстановлено {created_count} записей для детей')
    else:
        messages.info(request, 'Все записи уже существуют')
    
    return redirect('attendance:attendance_sheet_edit', sheet_id=sheet.id)


# ==================== ПРОИЗВОДСТВЕННЫЙ КАЛЕНДАРЬ ====================

# attendance/views.py
@login_required
@director_required
def production_calendar_list(request):
    """Список производственного календаря (AJAX версия)"""
    from calendar import monthrange, weekday
    
    year = date.today().year
    month = date.today().month
    
    return render(request, 'attendance/production_calendar_ajax.html', {
        'current_year': year,
        'current_month': month,
        'month_name': get_month_name_ru(month),
    })


def get_month_name_ru(month):
    month_names = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    return month_names.get(month, '')

@login_required
@director_required
def production_calendar_update(request):
    """Обновление производственного календаря"""
    if request.method == 'POST':
        date_str = request.POST.get('date')
        is_holiday = request.POST.get('is_holiday') == 'on'
        is_working_saturday = request.POST.get('is_working_saturday') == 'on'
        holiday_name = request.POST.get('holiday_name', '')
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            calendar_entry, created = ProductionCalendar.objects.get_or_create(
                year=date_obj.year,
                date=date_obj,
                defaults={
                    'is_holiday': is_holiday,
                    'is_working_saturday': is_working_saturday,
                    'holiday_name': holiday_name
                }
            )
            if not created:
                calendar_entry.is_holiday = is_holiday
                calendar_entry.is_working_saturday = is_working_saturday
                calendar_entry.holiday_name = holiday_name
                calendar_entry.save()
            
            messages.success(request, f'Календарь обновлен для {date_obj.strftime("%d.%m.%Y")}')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
        
        return redirect('attendance:production_calendar_list')
    
    return redirect('attendance:production_calendar_list')


@login_required
@director_required
def production_calendar_generate(request):
    """Автоматическая генерация производственного календаря на год"""
    if request.method == 'POST':
        year = int(request.POST.get('year'))
        
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        created_count = 0
        updated_count = 0
        
        current_date = start_date
        while current_date <= end_date:
            is_weekend = current_date.weekday() >= 5
            
            entry, created = ProductionCalendar.objects.update_or_create(
                year=year,
                date=current_date,
                defaults={
                    'is_holiday': is_weekend,
                    'is_working_saturday': False,
                    'holiday_name': ''
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
            
            current_date += timedelta(days=1)
        
        messages.success(request, f'Календарь на {year} год сгенерирован! Создано: {created_count}, обновлено: {updated_count}')
        return redirect('attendance:production_calendar_list')
    
    return redirect('attendance:production_calendar_list')


# ==================== РОДИТЕЛЬСКАЯ ПАНЕЛЬ ====================

@login_required
def parent_attendance(request):
    """Посещаемость детей для родителя"""
    if request.user.role != 'parent':
        messages.error(request, 'Доступ только для родителей.')
        return redirect('dashboard')
    
    try:
        parent_profile = request.user.parentprofile
        children = Child.objects.filter(
            parents_relations__parent=parent_profile,
            is_active=True
        ).distinct()
    except:
        children = Child.objects.none()
    
    period = request.GET.get('period', 'month')
    child_id = request.GET.get('child', '')
    
    end_date = timezone.now().date()
    if period == 'week':
        start_date = end_date - timedelta(days=7)
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
    elif period == 'quarter':
        start_date = end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=30)
    
    selected_child = None
    if child_id and children.filter(id=child_id).exists():
        selected_child = get_object_or_404(Child, id=child_id)
        children_to_show = children.filter(id=child_id)
    else:
        children_to_show = children
    
    children_stats = []
    for child in children_to_show:
        total_days = (end_date - start_date).days + 1
        present_count = 0
        
        current_date = start_date
        while current_date <= end_date:
            # Проверяем, является ли день выходным
            try:
                cal_entry = ProductionCalendar.objects.get(date=current_date)
                is_holiday = cal_entry.is_holiday
            except ProductionCalendar.DoesNotExist:
                is_holiday = current_date.weekday() >= 5
            
            if not is_holiday:
                try:
                    sheet = AttendanceSheet.objects.get(
                        group=child.group,
                        month=current_date.month,
                        year=current_date.year
                    )
                    record = AttendanceRecord.objects.get(sheet=sheet, child=child)
                    if record.get_day_status(current_date.day) == 'present':
                        present_count += 1
                except:
                    pass
            current_date += timedelta(days=1)
        
        attendance_percentage = round((present_count / total_days) * 100, 1) if total_days > 0 else 0
        
        children_stats.append({
            'child': child,
            'present_count': present_count,
            'absent_count': total_days - present_count,
            'total_days': total_days,
            'attendance_percentage': attendance_percentage,
        })
    
    context = {
        'children': children,
        'children_stats': children_stats,
        'selected_child': selected_child,
        'start_date': start_date,
        'end_date': end_date,
        'period': period,
    }
    
    return render(request, 'attendance/parent_dashboard.html', context)


@login_required
def parent_attendance_detail(request, child_id):
    """Детальная страница посещаемости конкретного ребенка"""
    if request.user.role != 'parent':
        messages.error(request, 'Доступ только для родителей.')
        return redirect('dashboard')
    
    try:
        child = get_object_or_404(Child, id=child_id)
        if not ChildParent.objects.filter(child=child, parent=request.user.parentprofile).exists():
            messages.error(request, 'Доступ запрещен.')
            return redirect('attendance:parent_dashboard')
    except:
        messages.error(request, 'Ребенок не найден.')
        return redirect('attendance:parent_dashboard')
    
    month = request.GET.get('month', timezone.now().month)
    year = request.GET.get('year', timezone.now().year)
    
    try:
        month = int(month)
        year = int(year)
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
    except:
        start_date = timezone.now().date().replace(day=1)
        end_date = timezone.now().date()
    
    calendar_data = []
    current_date = start_date
    
    try:
        sheet = AttendanceSheet.objects.get(
            group=child.group,
            month=month,
            year=year
        )
        record = AttendanceRecord.objects.get(sheet=sheet, child=child)
    except:
        record = None
    
    status_display = {
        'present': 'Я',
        'absent': 'Н',
        'sick': 'НБ',
        'vacation': 'НУ',
        'weekend': 'В',
        '': '-'
    }
    
    while current_date <= end_date:
        # Проверяем, является ли день выходным
        try:
            cal_entry = ProductionCalendar.objects.get(date=current_date)
            is_holiday = cal_entry.is_holiday
        except ProductionCalendar.DoesNotExist:
            is_holiday = current_date.weekday() >= 5
        
        if is_holiday:
            display = 'В'
        else:
            status = getattr(record, f'day_{current_date.day}', '') if record else ''
            display = status_display.get(status, '-')
        
        calendar_data.append({
            'date': current_date,
            'status': display,
            'is_weekend': current_date.weekday() >= 5,
            'is_today': current_date == timezone.now().date(),
        })
        current_date += timedelta(days=1)
    
    present_count = sum(1 for day in calendar_data if day['status'] == 'Я')
    total_days = len(calendar_data)
    
    context = {
        'child': child,
        'calendar_data': calendar_data,
        'start_date': start_date,
        'end_date': end_date,
        'present_count': present_count,
        'absent_count': total_days - present_count,
        'total_days': total_days,
        'attendance_percentage': round((present_count / total_days) * 100, 1) if total_days > 0 else 0,
    }
    
    return render(request, 'attendance/parent_detail.html', context)




def get_month_name_ru(month_number):
    """Получить название месяца в родительном падеже"""
    month_names = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    return month_names.get(month_number, '')


def debug_template(request):
    """Отладочная функция для проверки шаблона"""
    import os
    from docx import Document
    from django.conf import settings
    from django.http import HttpResponse
    
    template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель_посещаемости.docx')
    
    if not os.path.exists(template_path):
        return HttpResponse(f"Шаблон не найден: {template_path}")
    
    try:
        doc = Document(template_path)
        
        output = []
        output.append("<html><body>")
        output.append("<h2>📄 ПАРАГРАФЫ:</h2>")
        output.append("<pre>")
        for i, para in enumerate(doc.paragraphs):
            if para.text.strip():
                output.append(f"{i}: {para.text[:200]}")
        
        output.append("\n</pre><h2>📊 ТАБЛИЦЫ:</h2><pre>")
        for t_idx, table in enumerate(doc.tables):
            output.append(f"\n=== Таблица {t_idx} ===")
            for r_idx, row in enumerate(table.rows):
                row_texts = []
                for c_idx, cell in enumerate(row.cells):
                    if cell.text.strip():
                        row_texts.append(f"[{c_idx}]{cell.text.strip()[:100]}")
                if row_texts:
                    output.append(f"  Строка {r_idx}: {' | '.join(row_texts)}")
        
        output.append("\n</pre></body></html>")
        
        return HttpResponse(''.join(output), content_type='text/html')
        
    except Exception as e:
        return HttpResponse(f"Ошибка при чтении шаблона: {str(e)}")
    
    
from django.http import JsonResponse
from datetime import date

@login_required
@director_required
def api_calendar_data(request):
    """API для получения данных календаря"""
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))
    
    from calendar import monthrange, weekday
    
    days_in_month = monthrange(year, month)[1]
    days = []
    
    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)
        try:
            entry = ProductionCalendar.objects.get(date=current_date)
            is_holiday = entry.is_holiday
            holiday_name = entry.holiday_name
            is_working_saturday = entry.is_working_saturday
        except ProductionCalendar.DoesNotExist:
            is_holiday = weekday(year, month, day) >= 5
            holiday_name = ''
            is_working_saturday = False
        
        days.append({
            'day': day,
            'date': current_date.isoformat(),
            'is_holiday': is_holiday,
            'is_weekend': weekday(year, month, day) >= 5,
            'holiday_name': holiday_name,
            'is_working_saturday': is_working_saturday,
            'weekday': weekday(year, month, day)
        })
    
    return JsonResponse({
        'year': year,
        'month': month,
        'days': days
    })


@login_required
@director_required
def api_generate_year(request):
    """API для генерации календаря на год"""
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        year = data.get('year', date.today().year)
        
        from calendar import monthrange, weekday
        
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        current_date = start_date
        while current_date <= end_date:
            is_weekend = weekday(current_date.year, current_date.month, current_date.day) >= 5
            
            ProductionCalendar.objects.update_or_create(
                year=year,
                date=current_date,
                defaults={
                    'is_holiday': is_weekend,
                    'is_working_saturday': False,
                    'holiday_name': ''
                }
            )
            current_date += timedelta(days=1)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})


# attendance/views.py - добавьте в конец файла

from django.http import JsonResponse
from datetime import date, timedelta
from calendar import monthrange, weekday

@login_required
@director_required
def api_calendar_data(request):
    """API для получения данных календаря"""
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))
    
    days_in_month = monthrange(year, month)[1]
    days = []
    
    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)
        try:
            entry = ProductionCalendar.objects.get(date=current_date)
            is_holiday = entry.is_holiday
            holiday_name = entry.holiday_name
            is_working_saturday = entry.is_working_saturday
        except ProductionCalendar.DoesNotExist:
            is_holiday = weekday(year, month, day) >= 5
            holiday_name = ''
            is_working_saturday = False
        
        days.append({
            'day': day,
            'date': current_date.isoformat(),
            'is_holiday': is_holiday,
            'is_weekend': weekday(year, month, day) >= 5,
            'holiday_name': holiday_name,
            'is_working_saturday': is_working_saturday,
            'weekday': weekday(year, month, day)
        })
    
    return JsonResponse({
        'year': year,
        'month': month,
        'days': days
    })


@login_required
@director_required
def api_generate_year(request):
    """API для генерации календаря на год"""
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        year = data.get('year', date.today().year)
        
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        current_date = start_date
        while current_date <= end_date:
            is_weekend = weekday(current_date.year, current_date.month, current_date.day) >= 5
            
            ProductionCalendar.objects.update_or_create(
                year=year,
                date=current_date,
                defaults={
                    'is_holiday': is_weekend,
                    'is_working_saturday': False,
                    'holiday_name': ''
                }
            )
            current_date += timedelta(days=1)
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT

# Словарь ставок по группам
GROUP_RATES = {
    'Первая младшая': '1684,00',
    'Вторая младшая': '1357,00',
    'Средняя': '1357,00',
    'Подготовительная': '1357,00',
}

# Цвет для выходных дней (красный)
HOLIDAY_COLOR = RGBColor(255, 0, 0)  # Красный


def get_group_rate(group_name):
    """Получить ставку по названию группы"""
    for key, value in GROUP_RATES.items():
        if key in group_name:
            return value
    return '1357,00'

# Добавьте в начало файла импорты:
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import tempfile

@login_required
@require_http_methods(["POST"])
def attendance_sheet_print_ajax(request, sheet_id):
    """Печать табеля с анимацией"""
    try:
        sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
        template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель посещаемости детей.docx')
        
        if not os.path.exists(template_path):
            return JsonResponse({'success': False, 'error': 'Шаблон не найден'}, status=500)
        
        doc = Document(template_path)
        fill_attendance_document(doc, sheet)
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        
        month_names = {1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
                       7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'}
        filename = quote(f'Табель_{sheet.group.name}_{month_names[sheet.month]}_{sheet.year}.docx')
        
        response = FileResponse(file_stream, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    
def fill_attendance_document(doc, sheet):
    """Заполнение документа данными"""
    from calendar import weekday
    from datetime import date
    
    records = list(sheet.records.select_related('child').order_by('child__full_name'))
    days_in_month = sheet.get_total_days()
    now = timezone.now()
    
    month_names_gen = {1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
                       7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'}
    month_names_nom = {1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
                       7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'}
    
    # Замена текстовых плейсхолдеров
    replacements = {
        '{{ month_year }}': f'{month_names_nom[sheet.month]} {sheet.year}',
        '{{ okud_code }}': '0504608',
        '{{ institution_name }}': 'Муниципальное бюджетное дошкольное образовательное учреждение Карабашский детский сад общеразвивающего вида №1 «Рябинушка»',
        '{{ structural_unit }}': sheet.group.name,
        '{{ date }}': now.strftime('%d.%m.%Y'),
        '{{ calculation_type }}': 'Родительская плата',
        '{{ work_mode }}': '5-дневная рабочая неделя',
        '{{ approval_date_day }}': f'{now.day:02d}',
        '{{ approval_date_month }}': month_names_gen[now.month],
        '{{ approval_date_year }}': str(now.year)[-2:],
        '{{ director_name }}': sheet.approved_by.get_full_name() if sheet.approved_by else '_________________',
        '{{ teacher_name }}': sheet.created_by.get_full_name() if sheet.created_by else '_________________',
    }
    
    for paragraph in doc.paragraphs:
        for key, value in replacements.items():
            if key in paragraph.text:
                paragraph.text = paragraph.text.replace(key, value)
    
    # Заполнение таблиц
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for key, value in replacements.items():
                    if key in cell.text:
                        cell.text = cell.text.replace(key, value)
        
        fill_attendance_table(table, records, days_in_month, sheet)
        
        
HOLIDAY_COLOR = RGBColor(255, 0, 0)


def set_cell_text(cell, text, color=None, bold=False, align=None):
    """Установка текста в ячейку"""
    cell.text = ''
    paragraph = cell.paragraphs[0]
    if align:
        paragraph.alignment = align
    run = paragraph.add_run(str(text))
    if color:
        run.font.color.rgb = color
    if bold:
        run.font.bold = True
    run.font.size = Pt(11)
       
       
       
@login_required
@teacher_required
def add_absence_document(request, record_id):
    """Добавление документа к записи посещаемости"""
    record = get_object_or_404(AttendanceRecord, id=record_id)
    
    # Проверка прав доступа
    if record.sheet.group.teacher != request.user and request.user.role != 'director':
        messages.error(request, 'У вас нет прав для добавления документов к этому табелю.')
        return redirect('attendance:attendance_sheet_edit', sheet_id=record.sheet.id)
    
    if request.method == 'POST':
        form = AbsenceDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                doc = form.save(commit=False)
                doc.record = record
                doc.uploaded_by = request.user
                doc.save()
                
                # Отмечаем дни болезни/отпуска в табеле
                current_date = doc.start_date
                while current_date <= doc.end_date:
                    day = current_date.day
                    if day <= record.sheet.get_total_days():
                        # Проверяем, не выходной ли день
                        from calendar import weekday
                        from datetime import date
                        current_date_obj = date(current_date.year, current_date.month, day)
                        is_weekend = weekday(current_date_obj.year, current_date_obj.month, current_date_obj.day) >= 5
                        
                        if not is_weekend:
                            if doc.document_type in ['sick_leave', 'medical_certificate']:
                                setattr(record, f'day_{day}', 'absent_sick')
                            elif doc.document_type in ['parent_statement', 'sanatorium_voucher', 'other']:
                                setattr(record, f'day_{day}', 'absent_vacation')
                    
                    current_date += timedelta(days=1)
                
                record.save()
                messages.success(request, f'Документ "{doc.get_document_type_display()}" успешно загружен! Дни отмечены в табеле.')
                return redirect('attendance:attendance_sheet_edit', sheet_id=record.sheet.id)
            except Exception as e:
                messages.error(request, f'Ошибка при сохранении документа: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Ошибка в поле {field}: {error}')
    else:
        form = AbsenceDocumentForm()
    
    # Получаем уже загруженные документы
    existing_documents = record.documents.all()
    
    return render(request, 'attendance/add_document.html', {
        'form': form,
        'record': record,
        'existing_documents': existing_documents,
        'sheet': record.sheet,
    })


@login_required
def delete_absence_document(request, doc_id):
    """Удаление документа"""
    doc = get_object_or_404(AbsenceDocument, id=doc_id)
    record = doc.record
    sheet_id = record.sheet.id
    
    # Проверка прав
    if record.sheet.group.teacher != request.user and request.user.role != 'director':
        messages.error(request, 'У вас нет прав для удаления этого документа.')
        return redirect('attendance:attendance_sheet_edit', sheet_id=sheet_id)
    
    # Удаляем отметки из табеля за период документа
    current_date = doc.start_date
    while current_date <= doc.end_date:
        day = current_date.day
        if day <= record.sheet.get_total_days():
            from calendar import weekday
            current_date_obj = date(current_date.year, current_date.month, day)
            is_weekend = weekday(current_date_obj.year, current_date_obj.month, current_date_obj.day) >= 5
            
            if not is_weekend:
                # Если статус был установлен этим документом, очищаем его
                current_status = getattr(record, f'day_{day}', '')
                if current_status in ['absent_sick', 'absent_vacation']:
                    setattr(record, f'day_{day}', '')
        current_date += timedelta(days=1)
    
    record.save()
    
    # Удаляем файл
    if doc.document_file:
        doc.document_file.delete(save=False)
    
    doc.delete()
    messages.success(request, 'Документ удален, отметки в табеле очищены.')
    return redirect('attendance:attendance_sheet_edit', sheet_id=sheet_id)


@login_required
def download_absence_document(request, doc_id):
    """Скачивание документа"""
    doc = get_object_or_404(AbsenceDocument, id=doc_id)
    
    # Проверка прав
    if doc.record.sheet.group.teacher != request.user and request.user.role != 'director':
        raise Http404("Документ не найден")
    
    if doc.document_file:
        file_path = doc.document_file.path
        if os.path.exists(file_path):
            response = FileResponse(
                open(file_path, 'rb'),
                content_type='application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
    
    messages.error(request, 'Файл не найден.')
    return redirect('attendance:attendance_sheet_edit', sheet_id=doc.record.sheet.id)     
        
        
def fill_attendance_table(table, records, days_in_month, sheet):
    """Заполнение таблицы с данными"""
    from calendar import weekday
    from datetime import date
    
    status_display = {
        'present': 'Я', 'absent': 'Н', 'absent_sick': 'НБ',
        'absent_vacation': 'НУ', 'absent_unexcused': 'НЯ', 'weekend': 'В', '': ''
    }
    
    # Подсчет данных
    children_data = []
    daily_absent = {day: 0 for day in range(1, days_in_month + 1)}
    total_paid = 0
    total_charged = 0
    
    for record in records:
        paid = 0
        charged = 0
        for day in range(1, days_in_month + 1):
            current_date = date(sheet.year, sheet.month, day)
            try:
                from attendance.models import ProductionCalendar
                cal = ProductionCalendar.objects.get(date=current_date)
                is_holiday = cal.is_holiday
            except:
                is_holiday = weekday(sheet.year, sheet.month, day) >= 5
            
            if is_holiday:
                status = 'weekend'
            else:
                status = getattr(record, f'day_{day}', '')
            
            if status and status != 'present' and not is_holiday:
                daily_absent[day] += 1
            
            if status in ['present', 'absent', 'absent_unexcused']:
                paid += 1
            elif status in ['absent_sick', 'absent_vacation']:
                charged += 1
        
        children_data.append({'record': record, 'paid': paid, 'charged': charged})
        total_paid += paid
        total_charged += charged
    
    # Поиск строки-шаблона
    template_row = None
    for row in table.rows:
        for cell in row.cells:
            if '{{ child_full_name }}' in cell.text:
                template_row = row
                break
        if template_row:
            break
    
    if not template_row:
        return
    
    template_cells = [cell.text for cell in template_row.cells]
    tbl = table._element
    tbl.remove(template_row._element)
    
    # Добавление строк для детей
    for idx, data in enumerate(children_data, 1):
        new_row = table.add_row()
        for cell_idx, cell in enumerate(new_row.cells):
            if cell_idx >= len(template_cells):
                continue
            cell_text = template_cells[cell_idx]
            
            if '{{ child_number }}' in cell_text:
                cell.text = str(idx)
            elif '{{ child_full_name }}' in cell_text:
                cell.text = data['record'].child.full_name
            elif '{{ child_account_number }}' in cell_text:
                cell.text = str(data['record'].child.id)
            elif '{{ child_rate }}' in cell_text:
                cell.text = '1357,00'
            elif 4 <= cell_idx <= 34:
                day = cell_idx - 3
                if day <= days_in_month:
                    current_date = date(sheet.year, sheet.month, day)
                    try:
                        from attendance.models import ProductionCalendar
                        cal = ProductionCalendar.objects.get(date=current_date)
                        is_holiday = cal.is_holiday
                    except:
                        is_holiday = weekday(sheet.year, sheet.month, day) >= 5
                    
                    if is_holiday:
                        status = 'weekend'
                    else:
                        status = getattr(data['record'], f'day_{day}', '')
                    
                    text = status_display.get(status, '')
                    color = HOLIDAY_COLOR if status == 'weekend' else None
                    set_cell_text(cell, text, color=color)
            elif '{{ total_absent }}' in cell_text:
                total_absent = 0
                for day in range(1, days_in_month + 1):
                    current_date = date(sheet.year, sheet.month, day)
                    try:
                        from attendance.models import ProductionCalendar
                        cal = ProductionCalendar.objects.get(date=current_date)
                        is_holiday = cal.is_holiday
                    except:
                        is_holiday = weekday(sheet.year, sheet.month, day) >= 5
                    if not is_holiday:
                        status = getattr(data['record'], f'day_{day}', '')
                        if status and status != 'present':
                            total_absent += 1
                cell.text = str(total_absent) if total_absent > 0 else ''
            elif '{{ total_charged_absent }}' in cell_text:
                cell.text = str(data['charged']) if data['charged'] > 0 else ''
            elif '{{ days_to_pay }}' in cell_text or '{{ total_days_to_pay }}' in cell_text:
                cell.text = str(data['paid']) if data['paid'] > 0 else ''
            elif '{{ absence_reason }}' in cell_text:
                reasons = []
                if data['record'].get_sick_days() > 0:
                    reasons.append(f'Болезнь: {data["record"].get_sick_days()} дн.')
                if data['record'].get_vacation_days() > 0:
                    reasons.append(f'Уважительная: {data["record"].get_vacation_days()} дн.')
                cell.text = '; '.join(reasons) if reasons else ''
            else:
                cell.text = '' if '{{' in cell_text else cell_text
    
    # Добавление итоговой строки
    total_row = table.add_row()
    if len(total_row.cells) >= 4:
        total_row.cells[0].merge(total_row.cells[3])
        set_cell_text(total_row.cells[0], 'Всего отсутствует детей', bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)
    
    for cell_idx, cell in enumerate(total_row.cells):
        if cell_idx == 0:
            continue
        elif 4 <= cell_idx <= 34:
            day = cell_idx - 3
            if day <= days_in_month:
                cell.text = str(daily_absent[day]) if daily_absent[day] > 0 else ''
        elif cell_idx == 35:
            cell.text = str(sum(daily_absent.values()))
        elif cell_idx == 36:
            cell.text = str(total_charged)
        elif cell_idx == 37:
            cell.text = str(total_paid)
        
def generate_filename(sheet):
    """Генерирует корректное имя файла на русском"""
    # Получаем название месяца в родительном падеже
    month_names = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    month_name = month_names.get(sheet.month, '')
    
    # Очищаем название группы от недопустимых символов
    group_name = sheet.group.name.replace('/', '-').replace('\\', '-').replace(':', '-')
    
    # Формируем имя файла
    filename = f'Табель_посещаемости_{group_name}_{month_name}_{sheet.year}.docx'
    
    # Кодируем для HTTP заголовка
    from urllib.parse import quote
    encoded_filename = quote(filename)
    
    return encoded_filename

def get_initials(full_name):
    """Получить инициалы из ФИО"""
    if not full_name:
        return ''
    parts = full_name.split()
    if len(parts) >= 1:
        surname = parts[0]
        initials = ''
        for part in parts[1:]:
            if part:
                initials += part[0].upper() + '.'
        return f'{surname} {initials}'
    return full_name


@login_required
def attendance_sheet_download_temp(request, sheet_id):
    """Скачивание временного файла"""
    file_path = request.GET.get('file', '')
    filename = request.GET.get('name', f'tabell_{sheet_id}.docx')
    
    if file_path and os.path.exists(file_path):
        try:
            response = FileResponse(
                open(file_path, 'rb'),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Удаляем файл после отправки
            import threading
            def cleanup():
                try:
                    time.sleep(2)
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                except:
                    pass
            threading.Thread(target=cleanup).start()
            
            return response
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'File not found'}, status=404)


def fill_attendance_template_full(doc, sheet):
    """Полное заполнение шаблона Word данными"""
    records = list(sheet.records.select_related('child').order_by('child__full_name'))
    days_in_month = sheet.get_total_days()
    
    month_names_genitive = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    
    month_names_nominative = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабря'
    }
    
    now = timezone.now()
    group_rate = get_group_rate(sheet.group.name)
    
    institution_full_name = 'Муниципальное бюджетное дошкольное образовательное учреждение Карабашский детский сад общеразвивающего вида №1 «Рябинушка»'
    
    director_name = ''
    if sheet.approved_by:
        director_name = get_initials(sheet.approved_by.get_full_name() or sheet.approved_by.username)
    else:
        director_name = '_________________'
    
    teacher_name = ''
    if sheet.created_by:
        teacher_name = get_initials(sheet.created_by.get_full_name() or sheet.created_by.username)
    else:
        teacher_name = '_________________'
    
    replacements = {
        '{{ month_year }}': f'{month_names_nominative.get(sheet.month, "")} {sheet.year}',
        '{{ okud_code }}': '0504608',
        '{{ institution_name }}': institution_full_name,
        '{{ structural_unit }}': sheet.group.name,
        '{{ date }}': now.strftime('%d.%m.%Y'),
        '{{ calculation_type }}': 'Родительская плата',
        '{{ work_mode }}': '5-дневная рабочая неделя',
        '{{ approval_date_day }}': f'{now.day:02d}',
        '{{ approval_date_month }}': month_names_genitive.get(now.month, ''),
        '{{ approval_date_year }}': str(now.year)[-2:],
        '{{ director_name }}': director_name,
        '{{ teacher_name }}': teacher_name,
    }
    
    # Замена в параграфах
    for paragraph in doc.paragraphs:
        for key, value in replacements.items():
            if key in paragraph.text:
                paragraph.text = paragraph.text.replace(key, value)
    
    # Замена в таблицах
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for key, value in replacements.items():
                        if key in paragraph.text:
                            paragraph.text = paragraph.text.replace(key, value)
        
        fill_children_table_correct(table, records, days_in_month, sheet, group_rate)


def set_cell_text_with_color(cell, text, color=None, bold=False, alignment=None):
    """Установка текста в ячейку с форматированием"""
    cell.text = ''
    paragraph = cell.paragraphs[0]
    if alignment:
        paragraph.alignment = alignment
    run = paragraph.add_run(str(text))
    if color:
        run.font.color.rgb = color
    if bold:
        run.font.bold = True
    run.font.size = Pt(11)


def fill_children_table_correct(table, records, days_in_month, sheet, group_rate):
    """Правильное заполнение таблицы с детьми - ОБНОВЛЕННАЯ ЛОГИКА"""
    from calendar import weekday
    from datetime import date
    
    status_display = {
        'present': {'text': 'Я', 'color': None, 'paid': True, 'reason': 'Присутствие'},
        'absent': {'text': 'Н', 'color': None, 'paid': True, 'reason': 'Без уважительной причины'},
        'absent_sick': {'text': 'НБ', 'color': None, 'paid': False, 'reason': 'Болезнь (справка)'},
        'absent_vacation': {'text': 'НУ', 'color': None, 'paid': False, 'reason': 'Уважительная причина'},
        'absent_unexcused': {'text': 'НЯ', 'color': None, 'paid': True, 'reason': 'Без уважительной причины'},
        'weekend': {'text': 'В', 'color': HOLIDAY_COLOR, 'paid': False, 'reason': 'Выходной'},
        '': {'text': '', 'color': None, 'paid': False, 'reason': ''}
    }
    
    # Подсчет статистики для каждого ребенка
    children_data = []
    for record in records:
        paid_days = 0           # Дни к оплате
        unpaid_days = 0         # Дни НЕ к оплате (перерасчет)
        valid_absent = 0        # Уважительные причины (НБ, НУ)
        invalid_absent = 0      # Неуважительные причины (Н, НЯ)
        present_days = 0        # Дни присутствия
        
        for day in range(1, days_in_month + 1):
            current_date = date(sheet.year, sheet.month, day)
            try:
                from attendance.models import ProductionCalendar
                cal_entry = ProductionCalendar.objects.get(date=current_date)
                is_holiday = cal_entry.is_holiday
            except:
                is_holiday = weekday(sheet.year, sheet.month, day) >= 5
            
            if is_holiday:
                status = 'weekend'
            else:
                status = getattr(record, f'day_{day}', '')
            
            status_info = status_display.get(status, status_display[''])
            
            # Подсчет по типам
            if status == 'present':
                present_days += 1
                paid_days += 1
            elif status == 'absent_sick' or status == 'absent_vacation':
                valid_absent += 1
                # НЕ оплачивается (перерасчет)
            elif status == 'absent' or status == 'absent_unexcused':
                invalid_absent += 1
                paid_days += 1  # ОПЛАЧИВАЕТСЯ
            elif status == 'weekend':
                unpaid_days += 1
        
        # Проверка наличия документов
        has_documents = record.documents.exists() if hasattr(record, 'documents') else False
        
        children_data.append({
            'record': record,
            'present_days': present_days,
            'paid_days': paid_days,
            'unpaid_days': unpaid_days,
            'valid_absent': valid_absent,
            'invalid_absent': invalid_absent,
            'has_documents': has_documents,
        })
    
    # Подсчет отсутствующих по дням (для строки "Всего отсутствует детей")
    daily_absent_counts = {}
    for day in range(1, days_in_month + 1):
        absent_count = 0
        current_date = date(sheet.year, sheet.month, day)
        try:
            from attendance.models import ProductionCalendar
            cal_entry = ProductionCalendar.objects.get(date=current_date)
            is_holiday = cal_entry.is_holiday
        except:
            is_holiday = weekday(sheet.year, sheet.month, day) >= 5
        
        if not is_holiday:
            for record in records:
                status = getattr(record, f'day_{day}', '')
                # Отсутствующие - все, кроме присутствующих и выходных
                if status and status != 'present':
                    absent_count += 1
        daily_absent_counts[day] = absent_count
    
    # Итоговые суммы
    total_absent_all_days = sum(daily_absent_counts.values())
    total_paid_days_all = sum(d['paid_days'] for d in children_data)
    total_valid_absent_all = sum(d['valid_absent'] for d in children_data)
    total_invalid_absent_all = sum(d['invalid_absent'] for d in children_data)
    
    # Находим строку-шаблон
    template_row = None
    header_rows_count = 0
    
    for i, row in enumerate(table.rows):
        row_text = ' '.join(cell.text for cell in row.cells)
        if '{{ child_full_name }}' in row_text:
            template_row = row
            header_rows_count = i
            break
    
    if not template_row:
        for i, row in enumerate(table.rows):
            row_text = ' '.join(cell.text for cell in row.cells)
            if '{{' in row_text and '}}' in row_text:
                template_row = row
                header_rows_count = i
                break
    
    if not template_row:
        return
    
    template_cells = [cell.text for cell in template_row.cells]
    
    # Удаляем строки с данными, сохраняя заголовки
    rows_to_remove = []
    for i, row in enumerate(table.rows):
        if i >= header_rows_count:
            rows_to_remove.append(row)
    
    for row in rows_to_remove:
        tbl = table._element
        tbl.remove(row._element)
    
    # Добавляем строки для детей
    for idx, data in enumerate(children_data, start=1):
        new_row = table.add_row()
        for cell_idx, cell in enumerate(new_row.cells):
            if cell_idx >= len(template_cells):
                continue
            cell_text = template_cells[cell_idx]
            
            if '{{ child_number }}' in cell_text:
                set_cell_text_with_color(cell, str(idx))
            elif '{{ child_full_name }}' in cell_text:
                set_cell_text_with_color(cell, data['record'].child.full_name)
            elif '{{ child_account_number }}' in cell_text:
                set_cell_text_with_color(cell, str(data['record'].child.id) if data['record'].child.id else '')
            elif '{{ child_rate }}' in cell_text:
                set_cell_text_with_color(cell, group_rate)
            elif 4 <= cell_idx <= 34:
                day = cell_idx - 3
                if day <= days_in_month:
                    current_date = date(sheet.year, sheet.month, day)
                    try:
                        from attendance.models import ProductionCalendar
                        cal_entry = ProductionCalendar.objects.get(date=current_date)
                        is_holiday = cal_entry.is_holiday
                    except:
                        is_holiday = weekday(sheet.year, sheet.month, day) >= 5
                    
                    if is_holiday:
                        status = 'weekend'
                    else:
                        status = getattr(data['record'], f'day_{day}', '')
                    
                    status_info = status_display.get(status, {'text': '', 'color': None})
                    set_cell_text_with_color(cell, status_info['text'], color=status_info['color'])
            elif '{{ total_absent }}' in cell_text:
                # Всего пропущено = уважительные + неуважительные
                total_absent = data['valid_absent'] + data['invalid_absent']
                set_cell_text_with_color(cell, str(total_absent) if total_absent > 0 else '')
            elif '{{ total_charged_absent }}' in cell_text:
                # Засчитываемые пропуски = уважительные причины (НБ, НУ)
                # Это дни для перерасчета
                set_cell_text_with_color(cell, str(data['valid_absent']) if data['valid_absent'] > 0 else '')
            elif '{{ days_to_pay }}' in cell_text or '{{ total_days_to_pay }}' in cell_text:
                # Дни к оплате = присутствие + неуважительные причины (Н, НЯ)
                set_cell_text_with_color(cell, str(data['paid_days']) if data['paid_days'] > 0 else '')
            elif '{{ absence_reason }}' in cell_text:
                # Формируем причину отсутствия
                reasons = []
                if data['valid_absent'] > 0:
                    reasons.append(f"Уважительные: {data['valid_absent']} дн.")
                if data['invalid_absent'] > 0:
                    reasons.append(f"Неуважительные: {data['invalid_absent']} дн.")
                if data['has_documents']:
                    reasons.append("(документы приложены)")
                reason_text = ', '.join(reasons) if reasons else ''
                set_cell_text_with_color(cell, reason_text)
            else:
                if '{{' in cell_text and '}}' in cell_text:
                    set_cell_text_with_color(cell, '')
                else:
                    set_cell_text_with_color(cell, cell_text)
    
    # Добавляем строку "Всего отсутствует детей"
    total_row = table.add_row()
    
    if len(total_row.cells) >= 4:
        start_cell = total_row.cells[0]
        end_cell = total_row.cells[3]
        start_cell.merge(end_cell)
        set_cell_text_with_color(
            start_cell, 
            'Всего отсутствует детей', 
            bold=True, 
            alignment=WD_ALIGN_PARAGRAPH.RIGHT
        )
    
    for cell_idx, cell in enumerate(total_row.cells):
        if cell_idx == 0:
            continue
        elif 4 <= cell_idx <= 34:
            day = cell_idx - 3
            if day <= days_in_month:
                value = daily_absent_counts.get(day, 0)
                set_cell_text_with_color(cell, str(value) if value > 0 else '')
        elif cell_idx == 35:
            set_cell_text_with_color(cell, str(total_absent_all_days) if total_absent_all_days > 0 else '')
        elif cell_idx == 36:
            set_cell_text_with_color(cell, str(total_valid_absent_all) if total_valid_absent_all > 0 else '')
        elif cell_idx == 37:
            set_cell_text_with_color(cell, str(total_paid_days_all) if total_paid_days_all > 0 else '')


@login_required
def attendance_sheet_print_word(request, sheet_id):
    """Обычная печать табеля (без AJAX)"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель посещаемости детей.docx')
    
    if not os.path.exists(template_path):
        messages.error(request, f'Шаблон не найден: {template_path}')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    doc = Document(template_path)
    fill_attendance_template_full(doc, sheet)
    
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    
    filename = generate_filename(sheet)
    from urllib.parse import unquote
    
    response = HttpResponse(
        file_stream.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="{unquote(filename)}"'
    
    return response



@login_required
def attendance_sheet_print_direct(request, sheet_id):
    """Прямая печать документа с использованием шаблона"""
    try:
        sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
        
        # Путь к шаблону
        template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель_посещаемости.docx')
        
        if os.path.exists(template_path):
            doc = Document(template_path)
        else:
            doc = Document()
            doc.add_heading('Табель учета посещаемости детей', 0)
        
        # Заполняем документ
        fill_attendance_template(doc, sheet)
        
        # Сохраняем в BytesIO
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        
        # Формируем имя файла
        filename = generate_filename(sheet)
        
        response = FileResponse(
            file_stream,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Ошибка при формировании документа: {str(e)}')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet_id)
    
    
    
def fill_attendance_template(doc, sheet):
    """Заполнение шаблона Word данными"""
    records = sheet.records.select_related('child').order_by('child__full_name')
    days_in_month = sheet.get_total_days()
    
    # Подготовка данных для замены
    month_names = {
        1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
        5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
        9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
    }
    
    # Данные для замены в шаблоне
    replacements = {
        '{{ group_name }}': sheet.group.name,
        '{{ month_name }}': month_names.get(sheet.month, ''),
        '{{ year }}': str(sheet.year),
        '{{ institution_name }}': 'МБДОУ Карабашский детский сад №1 "Рябинушка"',
        '{{ total_days }}': str(days_in_month),
    }
    
    # Замена текста во всех параграфах
    for paragraph in doc.paragraphs:
        for key, value in replacements.items():
            if key in paragraph.text:
                paragraph.text = paragraph.text.replace(key, value)
                # Сохраняем форматирование
                for run in paragraph.runs:
                    run.text = run.text.replace(key, value)
    
    # Замена в таблицах
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for key, value in replacements.items():
                        if key in paragraph.text:
                            paragraph.text = paragraph.text.replace(key, value)
        
        # Заполнение таблицы с детьми
        fill_children_table(table, records, days_in_month, sheet)


def fill_children_table(table, records, days_in_month, sheet):
    """Заполнение таблицы с детьми"""
    from calendar import weekday
    from datetime import date
    
    status_display = {
        'present': 'Я',
        'absent': 'Н',
        'sick': 'НБ',
        'vacation': 'НУ',
        'absent_unexcused': 'НЯ',
        'weekend': 'В',
        '': '-'
    }
    
    # Ищем строку-шаблон для ребенка
    template_row = None
    for row in table.rows:
        for cell in row.cells:
            if '{{ child_full_name }}' in cell.text:
                template_row = row
                break
        if template_row:
            break
    
    if template_row:
        # Сохраняем индекс строки-шаблона
        template_index = None
        for i, row in enumerate(table.rows):
            if row == template_row:
                template_index = i
                break
        
        # Удаляем строку-шаблон
        tbl = table._element
        tbl.remove(template_row._element)
        
        # Добавляем строки для каждого ребенка
        for idx, record in enumerate(records, start=1):
            new_row = table.add_row()
            
            # Заполняем ячейки
            for cell_idx, cell in enumerate(new_row.cells):
                if cell_idx == 0:
                    cell.text = str(idx)
                elif cell_idx == 1:
                    cell.text = record.child.full_name
                elif cell_idx >= 2:
                    day = cell_idx - 1
                    if day <= days_in_month:
                        # Проверяем выходной
                        current_date = date(sheet.year, sheet.month, day)
                        try:
                            cal_entry = ProductionCalendar.objects.get(date=current_date)
                            is_holiday = cal_entry.is_holiday
                        except ProductionCalendar.DoesNotExist:
                            is_holiday = weekday(sheet.year, sheet.month, day) >= 5
                        
                        if is_holiday:
                            status = 'weekend'
                        else:
                            status = record.get_day_status(day)
                        
                        cell.text = status_display.get(status, '-')


@login_required
def attendance_sheet_view_temp(request, sheet_id):
    """Просмотр временного документа в браузере"""
    temp_file = request.GET.get('file', '')
    # Найдите последний временный файл
    temp_dir = tempfile.gettempdir()
    files = [f for f in os.listdir(temp_dir) if f.startswith('tmp') and f.endswith('.docx')]
    if files:
        latest_file = max([os.path.join(temp_dir, f) for f in files], key=os.path.getctime)
        response = FileResponse(
            open(latest_file, 'rb'),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = 'inline; filename="document.docx"'
        return response
    
    return JsonResponse({'error': 'File not found'}, status=404)
