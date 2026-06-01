# attendance/views.py
import calendar
import os
import io
import json
import tempfile
import threading
import time
from shlex import quote
from calendar import monthrange, weekday
from datetime import datetime, time, timedelta, date

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import Http404, JsonResponse, HttpResponse, FileResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT

from .models import AbsenceDocument, AttendanceSheet, AttendanceRecord, ProductionCalendar, Meal
from .forms import AbsenceDocumentForm, AttendanceSheetForm, AttendanceRecordForm
from children.models import Child, ChildParent, Group


# ==================== КОНСТАНТЫ ====================

# Словарь статусов с их описаниями для примечаний
# Словарь примечаний для статусов
def get_status_note(status):
    """Получить текст примечания для статуса"""
    status_notes = {
        'absent_sick': 'НБ — неявка по болезни',
        'absent_vacation': 'НУ — неявка по уважительной причине',
        'absent_unexcused': 'НЯ — неявка без уважительной причины',
    }
    return status_notes.get(status, '')

STATUS_NOTES = {
    'present': '',
    'absent': '',
    'absent_sick': 'НБ — неявка по болезни',
    'absent_vacation': 'НУ — неявка по уважительной причине',
    'absent_unexcused': 'НЯ — неявка без уважительной причины',
    'weekend': '',
}

# Отображение статусов для печатной формы
# Словарь для отображения статусов в печатной форме
STATUS_DISPLAY = {
    'present': 'Я',
    'absent': 'Н',
    'absent_sick': 'НБ',
    'absent_vacation': 'НУ',
    'absent_unexcused': 'НЯ',
    'weekend': 'В',
    '': '',
}

# Цвет для выходных дней
HOLIDAY_COLOR = RGBColor(255, 0, 0)

# Ставки по группам
GROUP_RATES = {
    'Первая младшая': '1684,00',
    'Вторая младшая': '1357,00',
    'Средняя': '1357,00',
    'Подготовительная': '1357,00',
}


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


def get_month_name_ru(month_number, genitive=False):
    """Получить название месяца"""
    if genitive:
        month_names = {
            1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля',
            5: 'мая', 6: 'июня', 7: 'июля', 8: 'августа',
            9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'
        }
    else:
        month_names = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
    return month_names.get(month_number, '')


def get_group_rate(group_name):
    """Получить ставку по названию группы"""
    for key, value in GROUP_RATES.items():
        if key in group_name:
            return value
    return '1357,00'


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


def is_holiday_date(date_obj):
    """Проверка, является ли дата выходным/праздничным днем"""
    try:
        entry = ProductionCalendar.objects.get(date=date_obj)
        return entry.is_holiday
    except ProductionCalendar.DoesNotExist:
        return date_obj.weekday() >= 5


def get_status_note(status):
    """Получить текст примечания для статуса"""
    return STATUS_NOTES.get(status, '')


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
        
        current_month = today.month
        current_year = today.year
        current_day = today.day
        
        attendance_data = []
        present_count = 0
        absent_count = 0
        sick_count = 0
        vacation_count = 0
        
        try:
            sheet = AttendanceSheet.objects.get(
                group=teacher_group,
                month=current_month,
                year=current_year
            )
        except AttendanceSheet.DoesNotExist:
            sheet = None
        
        is_holiday = is_holiday_date(today)
        
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
            
            if status == 'present':
                present_count += 1
            elif status == 'absent':
                absent_count += 1
            elif status == 'sick':
                sick_count += 1
            elif status == 'vacation':
                vacation_count += 1
            
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
        
        total_children = children.count()
        attendance_percentage = round((present_count / total_children * 100), 1) if total_children > 0 else 0
        
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
    
@login_required
@director_required
def attendance_statistics(request):
    """Статистика посещаемости для заведующей"""
    from datetime import datetime, timedelta
    import json
    
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
    
    total_children = children.count()
    total_days = (end_date - start_date).days + 1
    
    # Статистика по дням
    daily_stats = []
    current_date = start_date
    while current_date <= end_date:
        present_count = 0
        is_holiday = is_holiday_date(current_date)
        
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
        
        is_holiday = is_holiday_date(date_obj)
        
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

# attendance/views.py - исправленная функция

@login_required
@staff_required
def update_attendance_ajax(request):
    """AJAX обновление посещаемости с автоматическим заполнением примечания"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            child_id = data.get('child_id')
            date_str = data.get('date')
            status = data.get('status')
            
            print(f"📝 Получены данные: child_id={child_id}, date={date_str}, status={status}")
            
            child = get_object_or_404(Child, id=child_id)
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Проверка доступа для воспитателя
            if request.user.role == 'teacher':
                teacher_group = get_teacher_group(request.user)
                if not teacher_group or child.group != teacher_group:
                    return JsonResponse({'success': False, 'error': 'Нет доступа'})
            
            # Проверка на выходной день
            if is_holiday_date(date_obj):
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
            
            # МАППИНГ СТАТУСОВ из формы в модель
            status_mapping = {
                'present': 'present',
                'absent': 'absent_unexcused',  # НЯ - неявка без уважительной причины
                'sick': 'absent_sick',         # НБ - болезнь
                'vacation': 'absent_vacation', # НУ - отпуск/уважительная причина
            }
            
            # Получаем статус для сохранения в модель
            new_status = status_mapping.get(status, '')
            print(f"🔄 Преобразование статуса: {status} -> {new_status}")
            
            if not new_status:
                return JsonResponse({'success': False, 'error': 'Неверный статус'})
            
            # Сохраняем старый статус
            old_status = getattr(record, f'day_{date_obj.day}', '')
            
            # Устанавливаем новый статус
            setattr(record, f'day_{date_obj.day}', new_status)
            
            # Обновляем примечания
            if new_status in ['absent_sick', 'absent_vacation', 'absent_unexcused']:
                note = get_status_note(new_status)
                if record.notes:
                    if note not in record.notes:
                        record.notes = f"{record.notes}\n{note} (день {date_obj.day})"
                else:
                    record.notes = f"{note} (день {date_obj.day})"
            
            record.save()
            
            # Для отладки
            print(f"✅ Статус сохранен: day_{date_obj.day} = {new_status}")
            
            # Формируем текст для ответа
            status_display_map = {
                'present': 'Присутствует',
                'absent_unexcused': 'Отсутствует',
                'absent_sick': 'Болеет',
                'absent_vacation': 'В отпуске',
            }
            
            return JsonResponse({
                'success': True, 
                'status': status,
                'status_display': status_display_map.get(new_status, 'Не отмечен'),
                'note': record.notes,
                'day': date_obj.day
            })
            
        except Exception as e:
            print(f"❌ Ошибка: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Неверный запрос'})


# Добавьте эту функцию для получения статуса ребенка на сегодня

@login_required
def get_child_today_status(request):
    """AJAX получение статуса ребенка на сегодня"""
    if request.method == 'GET':
        child_id = request.GET.get('child_id')
        
        if not child_id:
            return JsonResponse({'success': False, 'error': 'Не указан ребенок'})
        
        try:
            child = get_object_or_404(Child, id=child_id)
            today = timezone.now().date()
            
            # Получаем табель
            sheet = AttendanceSheet.objects.filter(
                group=child.group,
                month=today.month,
                year=today.year
            ).first()
            
            status_display = 'Не отмечен'
            status_code = 'unknown'
            
            if sheet:
                record = AttendanceRecord.objects.filter(sheet=sheet, child=child).first()
                if record:
                    raw_status = getattr(record, f'day_{today.day}', '')
                    
                    status_map_display = {
                        'present': 'Присутствует',
                        'absent_unexcused': 'Отсутствует',
                        'absent_sick': 'Болеет',
                        'absent_vacation': 'В отпуске',
                    }
                    
                    status_map_code = {
                        'present': 'present',
                        'absent_unexcused': 'absent',
                        'absent_sick': 'sick',
                        'absent_vacation': 'vacation',
                    }
                    
                    status_display = status_map_display.get(raw_status, 'Не отмечен')
                    status_code = status_map_code.get(raw_status, 'unknown')
            
            return JsonResponse({
                'success': True,
                'status_display': status_display,
                'status_code': status_code,
                'child_name': child.full_name
            })
            
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


@login_required
def mark_all_workdays_present(request, sheet_id):
    """Отметить все рабочие дни как присутствие для всех детей"""
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
            current_date = date(sheet.year, sheet.month, day)
            if is_holiday_date(current_date):
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


@login_required
def mark_all_present(request, sheet_id):
    """Отметить все дни как присутствие для всех детей"""
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


@login_required
def attendance_sheet_edit(request, sheet_id):
    """Редактирование табеля с учетом производственного календаря"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    if request.user.role == 'teacher':
        if sheet.group.teacher != request.user:
            messages.error(request, 'У вас нет доступа к этому табелю.')
            return redirect('attendance:attendance_sheet_list')
        
        if sheet.is_approved:
            messages.error(request, 'Этот табель уже утвержден и не может быть изменен.')
            return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
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
    
    records = list(sheet.records.select_related('child').order_by('child__full_name'))
    
    children_in_group = Child.objects.filter(group=sheet.group, is_active=True)
    if len(records) != children_in_group.count():
        for child in children_in_group:
            record, created = AttendanceRecord.objects.get_or_create(sheet=sheet, child=child)
            if created:
                records.append(record)
        records = list(sheet.records.select_related('child').order_by('child__full_name'))
    
    if request.method == 'POST':
        updated_records = 0
        
        # Проходим по каждому ребенку
        for record in records:
            changes = False
            
            # Проходим по каждому дню месяца
            for day in range(1, sheet.get_total_days() + 1):
                # Пропускаем праздничные и выходные дни
                if calendar_entries[day]['is_holiday']:
                    continue
                
                # Имя поля в форме: day_{record_id}_{day} (например day_123_15)
                field_name = f'day_{record.id}_{day}'
                
                if field_name in request.POST:
                    new_status = request.POST.get(field_name)
                    old_status = getattr(record, f'day_{day}', '')
                    
                    if old_status != new_status:
                        setattr(record, f'day_{day}', new_status)
                        changes = True
                        
                        # Автоматическое добавление примечания
                        if new_status in ['absent_sick', 'absent_vacation', 'absent_unexcused']:
                            note = get_status_note(new_status)
                            if record.notes:
                                if note not in record.notes:
                                    record.notes = f"{record.notes}\n{note}"
                            else:
                                record.notes = note
            
            # Сохраняем примечания из текстового поля
            notes_key = f'notes_{record.id}'
            if notes_key in request.POST:
                new_notes = request.POST[notes_key]
                if record.notes != new_notes:
                    record.notes = new_notes
                    changes = True
            
            if changes:
                record.save()
                updated_records += 1
        
        if updated_records > 0:
            messages.success(request, f'Табель сохранен! Обновлено {updated_records} записей.')
        else:
            messages.info(request, 'Изменений не обнаружено.')
        
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    days_in_month = sheet.get_total_days()
    
    calendar_data = []
    for day in range(1, days_in_month + 1):
        weekday_num = weekday(sheet.year, sheet.month, day)
        weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        calendar_data.append({
            'day': day,
            'is_holiday': calendar_entries[day]['is_holiday'],
            'holiday_name': calendar_entries[day]['holiday_name'],
            'is_weekend': weekday_num >= 5,
            'weekday_short': weekday_names[weekday_num]
        })
    
    # Собираем данные для детей с документами
    from django.core.files.storage import default_storage
    
    children_data = []
    for record in records:
        child_statuses = []
        present_count = 0
        
        # Получаем документы ребенка
        documents = []
        if hasattr(record, 'absence_documents'):
            documents = list(record.absence_documents.all())
        elif hasattr(record, 'documents'):
            documents = list(record.documents.all())
        
        for day in range(1, days_in_month + 1):
            is_holiday = calendar_entries[day]['is_holiday']
            if is_holiday:
                status = 'weekend'
                has_document = False
            else:
                status = getattr(record, f'day_{day}', '')
                # Проверяем, есть ли документ на эту дату
                has_document = any(
                    doc.start_date <= date(sheet.year, sheet.month, day) <= doc.end_date
                    for doc in documents
                )
            
            if status == 'present' and not is_holiday:
                present_count += 1
            
            child_statuses.append({
                'day': day,
                'status': status,
                'is_holiday': is_holiday,
                'has_document': has_document
            })
        
        children_data.append({
            'record_id': record.id,
            'child': record.child,
            'statuses': child_statuses,
            'notes': record.notes or '',
            'present_count': present_count,
            'documents': documents
        })
    
    # Подсчет статистики для отображения
    total_stats = {
        'present': 0,
        'absent_unexcused': 0,
        'absent_sick': 0,
        'absent_vacation': 0,
        'weekend': 0,
    }
    
    for day in range(1, days_in_month + 1):
        if calendar_entries[day]['is_holiday']:
            total_stats['weekend'] += 1
    
    return render(request, 'attendance/sheet_edit.html', {
        'sheet': sheet,
        'children_data': children_data,
        'calendar_data': calendar_data,
        'days_in_month': days_in_month,
        'month_name': sheet.get_month_name(),
        'total_stats': total_stats,
        'total_children': len(records),
        'status_notes': STATUS_NOTES,
    })

import calendar as cal

@login_required
def attendance_sheet_view(request, sheet_id):
    """Просмотр табеля посещаемости"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    # Проверка доступа
    if sheet.group.teacher != request.user and request.user.role != 'director':
        messages.error(request, 'У вас нет доступа к этому табелю')
        return redirect('attendance:attendance_sheet_list')
    
    # Получаем записи детей - ИСПРАВЛЕНО: используем full_name вместо last_name
    records = AttendanceRecord.objects.filter(sheet=sheet).select_related('child').order_by('child__full_name')
    
    # Количество дней в месяце
    days_in_month = calendar.monthrange(sheet.year, sheet.month)[1]
    
    # Формируем календарь
    calendar_data = []
    workdays_count = 0
    weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    
    for day in range(1, days_in_month + 1):
        day_date = date(sheet.year, sheet.month, day)
        weekday = day_date.weekday()
        is_holiday = weekday >= 5  # Сб и Вс
        
        # Проверяем праздники если есть такой метод
        if hasattr(sheet, 'is_holiday_date'):
            is_holiday = is_holiday or sheet.is_holiday_date(day_date)
        
        if not is_holiday:
            workdays_count += 1
        
        # Считаем присутствующих за день
        total_present = 0
        for record in records:
            status = getattr(record, f'day_{day}', '')
            if status == 'present':
                total_present += 1
        
        calendar_data.append({
            'day': day,
            'weekday_short': weekday_names[weekday],
            'is_holiday': is_holiday,
            'total_present': total_present
        })
    
    # Формируем данные по детям
    children_data = []
    group_totals = {
        'present': 0,
        'absent': 0,
        'sick': 0,
        'vacation': 0,
        'possible': 0
    }
    
    for record in records:
        statuses = []
        totals = {'present': 0, 'absent': 0, 'sick': 0, 'vacation': 0}
        
        for day in range(1, days_in_month + 1):
            day_date = date(sheet.year, sheet.month, day)
            weekday = day_date.weekday()
            is_holiday = weekday >= 5
            
            if hasattr(sheet, 'is_holiday_date'):
                is_holiday = is_holiday or sheet.is_holiday_date(day_date)
            
            status = getattr(record, f'day_{day}', '') or ''
            
            # Определяем наличие документа
            has_document = False
            if hasattr(record, 'absence_documents'):
                has_document = record.absence_documents.filter(
                    start_date__lte=day_date,
                    end_date__gte=day_date
                ).exists()
            elif hasattr(record, 'documents'):
                has_document = record.documents.filter(
                    start_date__lte=day_date,
                    end_date__gte=day_date
                ).exists()
            
            statuses.append({
                'day': day,
                'status': status,
                'is_holiday': is_holiday,
                'has_document': has_document
            })
            
            # Подсчёт статистики (только для рабочих дней)
            if not is_holiday:
                if status == 'present':
                    totals['present'] += 1
                elif status == 'absent_unexcused':
                    totals['absent'] += 1
                elif status == 'absent_sick':
                    totals['sick'] += 1
                elif status == 'absent_vacation':
                    totals['vacation'] += 1
        
        # Получаем документы для ребёнка
        documents = []
        if hasattr(record, 'absence_documents'):
            documents = list(record.absence_documents.all())
        elif hasattr(record, 'documents'):
            documents = list(record.documents.all())
        
        children_data.append({
            'record_id': record.id,
            'child': record.child,
            'statuses': statuses,
            'totals': totals,
            'notes': record.notes or '',
            'documents': documents
        })
        
        # Групповые итоги
        group_totals['present'] += totals['present']
        group_totals['absent'] += totals['absent']
        group_totals['sick'] += totals['sick']
        group_totals['vacation'] += totals['vacation']
        group_totals['possible'] += workdays_count
    
    # Средняя посещаемость
    avg_attendance = 0
    if group_totals['possible'] > 0:
        avg_attendance = round(group_totals['present'] / group_totals['possible'] * 100, 1)
    
    # Статистика по детям (для совместимости со старым шаблоном)
    children_stats = []
    for child_data in children_data:
        total_days = workdays_count
        present = child_data['totals']['present']
        attendance_percent = round(present / total_days * 100) if total_days > 0 else 0
        
        children_stats.append({
            'child': child_data['child'],
            'present': present,
            'absent': child_data['totals']['absent'],
            'sick': child_data['totals']['sick'],
            'vacation': child_data['totals']['vacation'],
            'attendance_percent': attendance_percent
        })
    
    # Название месяца
    month_names = [
        '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ]
    month_name = month_names[sheet.month]
    
    context = {
        'sheet': sheet,
        'month_name': month_name,
        'calendar_data': calendar_data,
        'children_data': children_data,
        'children_stats': children_stats,
        'workdays_count': workdays_count,
        'days_in_month': days_in_month,
        'group_stats': {
            'total_children': len(records),
            'total_present': group_totals['present'],
            'total_absent': group_totals['absent'],
            'total_sick': group_totals['sick'],
            'total_vacation': group_totals['vacation'],
            'total_possible': group_totals['possible'],
            'avg_attendance': avg_attendance
        },
        'can_edit': not sheet.is_approved or request.user.role == 'director',
        'can_approve': request.user.role == 'director' and not sheet.is_approved,
    }
    
    return render(request, 'attendance/sheet_view.html', context)

@login_required
def attendance_sheet_reset(request, sheet_id):
    """Сброс всех статусов табеля"""
    if request.user.role != 'teacher':
        messages.error(request, 'Только воспитатель может сбрасывать статусы.')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet_id)
    
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
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
            record.notes = ''
            record.save()
        
        messages.success(request, f'Все статусы табеля за {sheet.get_month_name()} {sheet.year} сброшены!')
        return redirect('attendance:attendance_sheet_edit', sheet_id=sheet.id)
    
    return render(request, 'attendance/sheet_reset.html', {'sheet': sheet, 'month_name': sheet.get_month_name()})


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
    
    children = Child.objects.filter(group=sheet.group, is_active=True)
    created_count = 0
    
    for child in children:
        record, created = AttendanceRecord.objects.get_or_create(sheet=sheet, child=child)
        if created:
            created_count += 1
    
    if created_count > 0:
        messages.success(request, f'Восстановлено {created_count} записей для детей')
    else:
        messages.info(request, 'Все записи уже существуют')
    
    return redirect('attendance:attendance_sheet_edit', sheet_id=sheet.id)


# ==================== УТВЕРЖДЕНИЕ ТАБЕЛЕЙ ====================

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


# ==================== ПЕЧАТЬ ТАБЕЛЯ ====================

@login_required
def attendance_sheet_print_word(request, sheet_id):
    """Печать табеля в Word с корректным отображением статусов"""
    sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
    
    # Путь к шаблону
    template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель посещаемости детей.docx')
    
    # Если шаблон не найден, пробуем альтернативный путь
    if not os.path.exists(template_path):
        template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель_посещаемости.docx')
    
    if not os.path.exists(template_path):
        messages.error(request, f'Шаблон не найден: {template_path}')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)
    
    try:
        doc = Document(template_path)
        fill_attendance_template_full(doc, sheet)
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        
        filename = generate_filename(sheet)
        
        response = HttpResponse(
            file_stream.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    except Exception as e:
        messages.error(request, f'Ошибка при формировании документа: {str(e)}')
        return redirect('attendance:attendance_sheet_view', sheet_id=sheet.id)


@login_required
@require_http_methods(["POST"])
def attendance_sheet_print_ajax(request, sheet_id):
    """Печать табеля с анимацией (AJAX)"""
    try:
        sheet = get_object_or_404(AttendanceSheet, id=sheet_id)
        template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель посещаемости детей.docx')
        
        if not os.path.exists(template_path):
            return JsonResponse({'success': False, 'error': 'Шаблон не найден'}, status=500)
        
        doc = Document(template_path)
        fill_attendance_template_full(doc, sheet)
        
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)
        
        filename = generate_filename(sheet)
        
        response = FileResponse(
            file_stream, 
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



def fill_attendance_template_full(doc, sheet):
    """Полное заполнение шаблона Word данными"""
    records = list(sheet.records.select_related('child').order_by('child__full_name'))
    days_in_month = sheet.get_total_days()
    now = timezone.now()
    
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
        '{{ month_year }}': f'{get_month_name_ru(sheet.month, genitive=False)} {sheet.year}',
        '{{ okud_code }}': '0504608',
        '{{ institution_name }}': institution_full_name,
        '{{ structural_unit }}': sheet.group.name,
        '{{ date }}': now.strftime('%d.%m.%Y'),
        '{{ calculation_type }}': 'Родительская плата',
        '{{ work_mode }}': '5-дневная рабочая неделя',
        '{{ approval_date_day }}': f'{now.day:02d}',
        '{{ approval_date_month }}': get_month_name_ru(now.month, genitive=True),
        '{{ approval_date_year }}': str(now.year)[-2:],
        '{{ director_name }}': director_name,
        '{{ teacher_name }}': teacher_name,
    }
    
    for paragraph in doc.paragraphs:
        for key, value in replacements.items():
            if key in paragraph.text:
                paragraph.text = paragraph.text.replace(key, value)
    
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for key, value in replacements.items():
                        if key in paragraph.text:
                            paragraph.text = paragraph.text.replace(key, value)
        
        fill_children_table_correct(table, records, days_in_month, sheet)


def fill_children_table_correct(table, records, days_in_month, sheet):
    """Правильное заполнение таблицы с детьми для печатной формы"""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.shared import Pt
    
    group_rate = get_group_rate(sheet.group.name)
    
    # Словарь для отображения статусов
    status_display = {
        'present': 'Я',
        'absent_sick': 'НБ',
        'absent_vacation': 'НУ',
        'absent_unexcused': 'НЯ',
        'weekend': 'В',
        '': '',
    }
    
    # Собираем данные по каждому ребенку
    children_data = []
    for record in records:
        day_statuses = {}
        sick_days = 0      # НБ - НЕ ОПЛАЧИВАЕТСЯ
        vacation_days = 0  # НУ - НЕ ОПЛАЧИВАЕТСЯ
        unexcused_days = 0 # НЯ - ОПЛАЧИВАЕТСЯ (засчитываемые)
        present_days = 0   # Я - ОПЛАЧИВАЕТСЯ
        
        for day in range(1, days_in_month + 1):
            current_date = date(sheet.year, sheet.month, day)
            is_holiday = sheet.is_holiday_date(current_date)
            
            if is_holiday:
                day_statuses[day] = 'weekend'
                continue
            
            status = getattr(record, f'day_{day}', '')
            day_statuses[day] = status
            
            if status == 'present':
                present_days += 1
            elif status == 'absent_sick':
                sick_days += 1
            elif status == 'absent_vacation':
                vacation_days += 1
            elif status == 'absent_unexcused':
                unexcused_days += 1
        
        # Расчет итогов
        total_absent = sick_days + vacation_days + unexcused_days
        counted_absent = unexcused_days  # Засчитываемые = только НЯ
        paid_days = present_days + unexcused_days  # Дни к оплате = Я + НЯ
        
        # Причины отсутствия
        reasons = []
        if sick_days > 0:
            reasons.append(f"«НБ» — неявка по болезни: {sick_days} дн.")
        if vacation_days > 0:
            reasons.append(f"«НУ» — неявка по уважительной причине: {vacation_days} дн.")
        if unexcused_days > 0:
            reasons.append(f"«НЯ» — неявка без уважительной причины: {unexcused_days} дн.")
        
        reason_text = '; '.join(reasons) if reasons else ''
        
        children_data.append({
            'record': record,
            'day_statuses': day_statuses,
            'total_absent': total_absent,
            'counted_absent': counted_absent,
            'paid_days': paid_days,
            'reason_text': reason_text,
        })
    
    # Подсчет отсутствующих по дням
    daily_absent_counts = {}
    for day in range(1, days_in_month + 1):
        absent_count = 0
        current_date = date(sheet.year, sheet.month, day)
        if not sheet.is_holiday_date(current_date):
            for record in records:
                status = getattr(record, f'day_{day}', '')
                if status in ['absent_sick', 'absent_vacation', 'absent_unexcused']:
                    absent_count += 1
        daily_absent_counts[day] = absent_count
    
    # Итоги по группе
    total_absent_all = sum(d['total_absent'] for d in children_data)
    total_counted_all = sum(d['counted_absent'] for d in children_data)
    total_paid_all = sum(d['paid_days'] for d in children_data)
    
    # Находим строку-шаблон
    template_row = None
    template_index = None
    
    for i, row in enumerate(table.rows):
        row_text = ' '.join(cell.text for cell in row.cells)
        if '{{ day_1 }}' in row_text and '{{ child_full_name }}' in row_text:
            template_row = row
            template_index = i
            break
    
    if not template_row:
        for i, row in enumerate(table.rows):
            row_text = ' '.join(cell.text for cell in row.cells)
            if '{{ child_number }}' in row_text and '{{ day_1 }}' in row_text:
                template_row = row
                template_index = i
                break
    
    if not template_row:
        print("❌ Шаблон строки не найден!")
        return
    
    # Удаляем строки начиная с шаблона
    rows_to_remove = []
    for i, row in enumerate(table.rows):
        if i >= template_index:
            rows_to_remove.append(row)
    for row in rows_to_remove:
        tbl = table._element
        tbl.remove(row._element)
    
    # Добавляем строки для каждого ребенка
    for idx, data in enumerate(children_data, 1):
        new_row = table.add_row()
        
        # ВЕРТИКАЛЬНОЕ ЦЕНТРИРОВАНИЕ для всей строки
        for cell in new_row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        
        for cell_idx, cell in enumerate(new_row.cells):
            # 0: Номер п/п (центр)
            if cell_idx == 0:
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = paragraph.add_run(str(idx))
                run.font.bold = True
                run.font.size = Pt(11)
            
            # 1: ФИО ребенка (влево)
            elif cell_idx == 1:
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                run = paragraph.add_run(data['record'].child.full_name)
                run.font.bold = True
                run.font.size = Pt(11)
            
            # 2: Номер счета (центр)
            elif cell_idx == 2:
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = paragraph.add_run(str(data['record'].child.id))
                run.font.size = Pt(11)
            
            # 3: Плата по ставке (центр)
            elif cell_idx == 3:
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = paragraph.add_run(group_rate)
                run.font.size = Pt(11)
            
            # 4-34: Дни месяца (центр)
            elif 4 <= cell_idx <= 34:
                day_num = cell_idx - 3
                if 1 <= day_num <= days_in_month:
                    status = data['day_statuses'].get(day_num, '')
                    display = status_display.get(status, '')
                    
                    cell.text = ''
                    paragraph = cell.paragraphs[0]
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = paragraph.add_run(display)
                    run.font.size = Pt(11)
                    
                    if status == 'weekend':
                        run.font.color.rgb = HOLIDAY_COLOR
                else:
                    cell.text = ''
                    paragraph = cell.paragraphs[0]
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # 35: Пропущено дней (центр)
            elif cell_idx == 35:
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if data['total_absent'] > 0:
                    run = paragraph.add_run(str(data['total_absent']))
                    run.font.size = Pt(11)
            
            # 36: в том числе засчитываемых (центр)
            elif cell_idx == 36:
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if data['counted_absent'] > 0:
                    run = paragraph.add_run(str(data['counted_absent']))
                    run.font.size = Pt(11)
            
            # 37: Дни подлежащие оплате (центр)
            elif cell_idx == 37:
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if data['paid_days'] > 0:
                    run = paragraph.add_run(str(data['paid_days']))
                    run.font.size = Pt(11)
            
            # 38: Причины непосещения (влево)
            elif cell_idx == 38:
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                if data['reason_text']:
                    run = paragraph.add_run(data['reason_text'])
                    run.font.size = Pt(9)
    
    # Добавляем итоговую строку
    total_row = table.add_row()
    
    # ВЕРТИКАЛЬНОЕ ЦЕНТРИРОВАНИЕ для итоговой строки
    for cell in total_row.cells:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    
    # Заполняем итоговую строку
    for cell_idx, cell in enumerate(total_row.cells):
        # Объединяем первые 4 ячейки
        if cell_idx == 0:
            if len(total_row.cells) >= 4:
                end_cell = total_row.cells[3]
                cell.merge(end_cell)
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                run = paragraph.add_run('Всего отсутствует детей')
                run.font.bold = True
                run.font.size = Pt(11)
        
        # 4-34: Дни месяца (центр)
        elif 4 <= cell_idx <= 34:
            day = cell_idx - 3
            if 1 <= day <= days_in_month:
                value = daily_absent_counts.get(day, 0)
                cell.text = ''
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if value > 0:
                    run = paragraph.add_run(str(value))
                    run.font.size = Pt(11)
        
        # 35: Всего пропущено (центр)
        elif cell_idx == 35:
            cell.text = ''
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if total_absent_all > 0:
                run = paragraph.add_run(str(total_absent_all))
                run.font.size = Pt(11)
        
        # 36: Засчитываемых (центр)
        elif cell_idx == 36:
            cell.text = ''
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if total_counted_all > 0:
                run = paragraph.add_run(str(total_counted_all))
                run.font.size = Pt(11)
        
        # 37: Дни к оплате (центр)
        elif cell_idx == 37:
            cell.text = ''
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if total_paid_all > 0:
                run = paragraph.add_run(str(total_paid_all))
                run.font.size = Pt(11)
        
        # 38: Причины (влево)
        elif cell_idx == 38:
            cell.text = ''
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT


def set_cell_text(cell, text, color=None, bold=False, alignment=None, size=11, vertical_center=True):
    """Установка текста в ячейку с форматированием (с вертикальным центрированием)"""
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    
    # Очищаем ячейку
    cell.text = ''
    
    # ВЕРТИКАЛЬНОЕ центрирование
    if vertical_center:
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    
    # Горизонтальное выравнивание
    paragraph = cell.paragraphs[0]
    if alignment is not None:
        paragraph.alignment = alignment
    else:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Добавляем текст
    if text:
        run = paragraph.add_run(str(text))
        if color:
            run.font.color.rgb = color
        if bold:
            run.font.bold = True
        run.font.size = Pt(size)



def generate_filename(sheet):
    """Генерирует корректное имя файла на русском"""
    month_name = get_month_name_ru(sheet.month, genitive=False)
    group_name = sheet.group.name.replace('/', '-').replace('\\', '-').replace(':', '-')
    filename = f'Табель_посещаемости_{group_name}_{month_name}_{sheet.year}.docx'
    from urllib.parse import quote
    return quote(filename)


# ==================== СТАТИСТИКА И АНАЛИТИКА ====================

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
        
        working_days_in_month = 0
        actual_attendance = 0
        
        sheets = AttendanceSheet.objects.filter(
            group__in=[g for g in groups] if not selected_group else [selected_group],
            month=current_date.month,
            year=current_date.year
        )
        
        for sheet in sheets:
            for record in sheet.records.all():
                for day in range(1, month_end.day + 1):
                    current_day = date(current_date.year, current_date.month, day)
                    if is_holiday_date(current_day):
                        continue
                    working_days_in_month += 1
                    if record.get_day_status(day) == 'present':
                        actual_attendance += 1
        
        percentage = round((actual_attendance / working_days_in_month) * 100, 1) if working_days_in_month > 0 else 0
        
        monthly_stats.append({
            'month': current_date.strftime('%Y-%m'),
            'month_name': current_date.strftime('%B %Y'),
            'percentage': percentage,
            'total_children': children.count(),
            'actual_attendance': actual_attendance,
            'total_days': working_days_in_month
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
    
    total_days = 0
    total_children = children.count()
    actual_attendance = 0
    
    current_date = start_date
    while current_date <= end_date:
        is_holiday = is_holiday_date(current_date)
        
        if not is_holiday:
            total_days += 1
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
        
        current_date += timedelta(days=1)
    
    total_possible_attendance = total_children * total_days
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


# ==================== ПРОИЗВОДСТВЕННЫЙ КАЛЕНДАРЬ ====================

@login_required
@director_required
def production_calendar_list(request):
    """Список производственного календаря"""
    year = request.GET.get('year', date.today().year)
    month = request.GET.get('month', date.today().month)
    
    try:
        year = int(year)
        month = int(month)
    except ValueError:
        year = date.today().year
        month = date.today().month
    
    # Проверяем, есть ли записи за текущий год
    calendar_exists = ProductionCalendar.objects.filter(year=year).exists()
    
    # Если нет записей, автоматически генерируем календарь на год
    if not calendar_exists:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        current_date = start_date
        while current_date <= end_date:
            is_weekend = current_date.weekday() >= 5
            
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
    
    return render(request, 'attendance/production_calendar_ajax.html', {
        'current_year': year,
        'current_month': month,
        'month_name': get_month_name_ru(month, genitive=False),
    })


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


# ==================== РОДИТЕЛЬСКАЯ ПАНЕЛЬ ====================

# attendance/views.py - ОПТИМИЗИРОВАННАЯ ВЕРСИЯ

@login_required
def parent_attendance(request):
    """Посещаемость детей для родителя - ОПТИМИЗИРОВАННАЯ"""
    import json
    from datetime import timedelta
    from django.utils import timezone
    from django.db.models import Q, Prefetch
    from django.core.cache import cache
    
    if request.user.role != 'parent':
        messages.error(request, 'Доступ только для родителей.')
        return redirect('dashboard')
    
    # Получаем детей родителя одним запросом
    try:
        parent_profile = request.user.parentprofile
        
        # ОПТИМИЗАЦИЯ: один запрос с join'ами
        children = Child.objects.filter(
            parent_relations__parent=parent_profile,
            is_active=True
        ).select_related('group').distinct()
        
        # Кешируем список детей на 5 минут
        children_list = list(children)
        
    except Exception as e:
        print(f"Ошибка получения детей: {e}")
        children_list = []
    
    if not children_list:
        return render(request, 'attendance/parent_dashboard.html', {
            'children': [],
            'children_stats': [],
            'selected_child': None,
            'start_date': None,
            'end_date': None,
            'period': 'month',
            'total_days': 0,
            'daily_labels': '[]',
            'daily_status': '[]',
        })
    
    # Параметры фильтрации
    period = request.GET.get('period', 'month')
    child_id = request.GET.get('child', '')
    
    end_date = timezone.now().date()
    if period == 'week':
        start_date = end_date - timedelta(days=6)
    elif period == 'month':
        start_date = end_date - timedelta(days=29)
    elif period == 'quarter':
        start_date = end_date - timedelta(days=89)
    else:
        start_date = end_date - timedelta(days=29)
    
    total_days = (end_date - start_date).days + 1
    
    # Выбранный ребенок
    selected_child = None
    if child_id:
        for child in children_list:
            if str(child.id) == child_id:
                selected_child = child
                children_to_show = [child]
                break
        else:
            children_to_show = children_list
    else:
        children_to_show = children_list
    
    # ОПТИМИЗАЦИЯ: собираем все ID групп
    group_ids = [child.group_id for child in children_to_show if child.group_id]
    
    # ОПТИМИЗАЦИЯ: один запрос для получения всех табелей и записей
    from attendance.models import AttendanceSheet, AttendanceRecord
    
    # Получаем все табели за нужные месяцы одним запросом
    sheets = AttendanceSheet.objects.filter(
        group_id__in=group_ids,
        month=end_date.month,
        year=end_date.year
    ).select_related('group')
    
    # Создаем словарь для быстрого доступа: {group_id: sheet}
    sheets_dict = {sheet.group_id: sheet for sheet in sheets}
    
    # Получаем все записи одним запросом
    records = AttendanceRecord.objects.filter(
        sheet_id__in=[s.id for s in sheets]
    ).select_related('child')
    
    # Создаем словарь для быстрого доступа: {(sheet_id, child_id): record}
    records_dict = {}
    for record in records:
        records_dict[(record.sheet_id, record.child_id)] = record
    
    # ОПТИМИЗАЦИЯ: кешируем производственный календарь
    from attendance.models import ProductionCalendar
    holidays = {}
    
    # Загружаем праздники за период одним запросом
    holiday_entries = ProductionCalendar.objects.filter(
        date__range=[start_date, end_date]
    )
    for entry in holiday_entries:
        holidays[entry.date] = entry.is_holiday
    
    def is_holiday(date_obj):
        """Быстрая проверка выходного дня"""
        if date_obj in holidays:
            return holidays[date_obj]
        return date_obj.weekday() >= 5
    
    daily_labels = []
    daily_status = []
    children_stats = []
    
    # Словарь для быстрого доступа к дням
    days_in_month = {}
    
    for child in children_to_show:
        present_count = 0
        absent_count = 0
        sick_count = 0
        vacation_count = 0
        
        recent_attendance = []
        
        if selected_child and child.id == selected_child.id:
            daily_labels = []
            daily_status = []
        
        # Получаем табель и запись для ребенка
        sheet = sheets_dict.get(child.group_id)
        record = None
        if sheet:
            record = records_dict.get((sheet.id, child.id))
        
        # ОПТИМИЗАЦИЯ: предварительно получаем все статусы днями
        day_statuses = {}
        if record:
            for day in range(1, 32):
                status = getattr(record, f'day_{day}', '')
                if status:
                    day_statuses[day] = status
        
        current_date = start_date
        while current_date <= end_date:
            is_holiday_flag = is_holiday(current_date)
            
            status = 'not_marked'
            
            if is_holiday_flag:
                status = 'weekend'
            else:
                raw_status = day_statuses.get(current_date.day, '')
                
                if raw_status == 'present':
                    status = 'present'
                    present_count += 1
                elif raw_status == 'absent_unexcused':
                    status = 'absent'
                    absent_count += 1
                elif raw_status == 'absent_sick':
                    status = 'sick'
                    sick_count += 1
                elif raw_status == 'absent_vacation':
                    status = 'vacation'
                    vacation_count += 1
                elif not raw_status:
                    status = 'absent'
                    absent_count += 1
            
            # Для выбранного ребенка собираем данные графика
            if selected_child and child.id == selected_child.id:
                daily_labels.append(current_date.strftime('%d.%m'))
                daily_status.append(status)
            
            # Для мини-календаря (последние 7 дней)
            if current_date >= end_date - timedelta(days=6):
                recent_attendance.append({
                    'date': current_date,
                    'status': status,
                    'is_holiday': is_holiday_flag,
                    'day': current_date.day,
                })
            
            current_date += timedelta(days=1)
        
        attendance_percentage = round((present_count / total_days) * 100, 1) if total_days > 0 else 0
        
        children_stats.append({
            'child': child,
            'present_count': present_count,
            'absent_count': absent_count,
            'sick_count': sick_count,
            'vacation_count': vacation_count,
            'other_count': 0,
            'total_days': total_days,
            'attendance_percentage': attendance_percentage,
            'recent_attendance': recent_attendance,
        })
    
    context = {
        'children': children_list,
        'children_stats': children_stats,
        'selected_child': selected_child,
        'start_date': start_date,
        'end_date': end_date,
        'period': period,
        'total_days': total_days,
        'daily_labels': json.dumps(daily_labels),
        'daily_status': json.dumps(daily_status),
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
    
    while current_date <= end_date:
        is_holiday = is_holiday_date(current_date)
        
        if is_holiday:
            display = 'В'
        else:
            status = getattr(record, f'day_{current_date.day}', '') if record else ''
            display = STATUS_DISPLAY.get(status, '-')
        
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


# ==================== ДОКУМЕНТЫ ОТСУТСТВИЯ ====================

@login_required
@teacher_required
def add_absence_document(request, record_id):
    """Добавление документа к записи посещаемости (AJAX)"""
    record = get_object_or_404(AttendanceRecord, id=record_id)
    
    if record.sheet.group.teacher != request.user and request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Нет доступа'})
    
    if request.method == 'POST':
        try:
            document_type = request.POST.get('document_type')
            document_file = request.FILES.get('document_file')
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            
            if not document_type or not document_file:
                return JsonResponse({'success': False, 'error': 'Заполните все обязательные поля'})
            
            if not start_date_str or not end_date_str:
                return JsonResponse({'success': False, 'error': 'Укажите даты'})
            
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if end_date < start_date:
                return JsonResponse({'success': False, 'error': 'Дата окончания не может быть раньше даты начала'})
            
            # Создаем документ
            doc = AbsenceDocument(
                record=record,
                document_type=document_type,
                document_file=document_file,
                start_date=start_date,
                end_date=end_date,
                uploaded_by=request.user
            )
            doc.save()
            
            # Определяем статус
            if document_type in ['sick_leave', 'medical_certificate']:
                status = 'absent_sick'
            else:
                status = 'absent_vacation'
            
            # Отмечаем дни
            marked_days = []
            current_date = start_date
            while current_date <= end_date:
                day = current_date.day
                # Проверяем что день в пределах месяца табеля
                if (current_date.month == record.sheet.month and 
                    current_date.year == record.sheet.year and
                    day <= record.sheet.get_total_days()):
                    
                    current_date_obj = date(record.sheet.year, record.sheet.month, day)
                    if not record.sheet.is_holiday_date(current_date_obj):
                        setattr(record, f'day_{day}', status)
                        marked_days.append(str(day))
                        
                current_date += timedelta(days=1)
            
            record.save()
            
            # Формируем данные для UI
            date_range = f"{start_date.strftime('%d.%m')} – {end_date.strftime('%d.%m')}"
            
            return JsonResponse({
                'success': True,
                'message': f'Документ загружен. Отмечены дни: {", ".join(marked_days)}',
                'marked_days': marked_days,
                'status': status,
                'document_info': {
                    'id': doc.id,
                    'type_display': doc.get_document_type_display(),
                    'date_range': date_range,
                    'file_url': doc.document_file.url,
                    'file_name': doc.document_file.name
                }
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Метод не разрешен'})


@login_required
def delete_absence_document(request, doc_id):
    """Удаление документа (AJAX и обычный запрос)"""
    doc = get_object_or_404(AbsenceDocument, id=doc_id)
    record = doc.record
    sheet_id = record.sheet.id
    
    if record.sheet.group.teacher != request.user and request.user.role != 'director':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Нет доступа'})
        messages.error(request, 'У вас нет прав для удаления этого документа.')
        return redirect('attendance:attendance_sheet_edit', sheet_id=sheet_id)
    
    # Собираем дни для очистки
    cleared_days = []
    current_date = doc.start_date
    while current_date <= doc.end_date:
        day = current_date.day
        if (current_date.month == record.sheet.month and 
            current_date.year == record.sheet.year and
            day <= record.sheet.get_total_days()):
            
            current_date_obj = date(record.sheet.year, record.sheet.month, day)
            if not record.sheet.is_holiday_date(current_date_obj):
                current_status = getattr(record, f'day_{day}', '')
                if current_status in ['absent_sick', 'absent_vacation']:
                    setattr(record, f'day_{day}', '')
                    cleared_days.append(str(day))
                    
        current_date += timedelta(days=1)
    
    record.save()
    
    # Удаляем файл
    if doc.document_file:
        try:
            doc.document_file.delete(save=False)
        except Exception:
            pass
    
    doc.delete()
    
    # AJAX ответ
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Документ удалён',
            'cleared_days': cleared_days
        })
    
    messages.success(request, 'Документ удален, отметки очищены.')
    return redirect('attendance:attendance_sheet_edit', sheet_id=sheet_id)


@login_required
def download_absence_document(request, doc_id):
    """Скачивание документа"""
    doc = get_object_or_404(AbsenceDocument, id=doc_id)
    
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


# ==================== ОТЛАДОЧНЫЕ ФУНКЦИИ ====================

def debug_template(request):
    """Отладочная функция для проверки шаблона"""
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


def test_save_attendance(request, sheet_id):
    """Тестовая функция для сохранения"""
    sheet = AttendanceSheet.objects.get(id=sheet_id)
    record = sheet.records.first()
    
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
