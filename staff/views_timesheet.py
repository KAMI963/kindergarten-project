# staff/views_timesheet.py

import os
import json
import calendar
import io
import logging
from datetime import date, datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


from .models import (
    DispensaryRecord, Timesheet, TimesheetEntry, Employee, OvertimeTracking,
    LeaveSchedule, EmployeeWorkSchedule, ProductionCalendar
)
from .forms_timesheet import QuickTimesheetEntryForm, TimesheetQuickEditForm

logger = logging.getLogger(__name__)


def get_holidays_for_month(year, month):
    """
    Получить все выходные и праздничные дни для месяца
    """
    holidays = {}
    days_in_month = calendar.monthrange(year, month)[1]
    
    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)
        try:
            cal_entry = ProductionCalendar.objects.get(date=current_date)
            is_holiday = cal_entry.is_holiday
            holiday_name = cal_entry.holiday_name if is_holiday else ''
        except ProductionCalendar.DoesNotExist:
            # По умолчанию суббота и воскресенье - выходные
            is_holiday = current_date.weekday() >= 5
            holiday_name = 'Выходной' if is_holiday else ''
        
        holidays[day] = {
            'is_holiday': is_holiday,
            'holiday_name': holiday_name,
            'weekday': current_date.weekday()
        }
    
    return holidays


def get_default_attendance_for_day(employee, date_obj, holidays):
    """
    Определить значение по умолчанию для дня с учетом производственного календаря
    """
    day = date_obj.day
    
    # Если день выходной или праздничный
    if day in holidays and holidays[day]['is_holiday']:
        return 'V'  # Выходной
    
    # Проверяем отпуск
    leave = LeaveSchedule.objects.filter(
        employee=employee,
        start_date__lte=date_obj,
        end_date__gte=date_obj,
        status__in=['planned', 'approved', 'in_progress']
    ).first()
    if leave:
        return 'OT'  # Отпуск
    
    # Проверяем график работы
    schedule = EmployeeWorkSchedule.objects.filter(
        employee=employee,
        start_date__lte=date_obj,
        end_date__isnull=True
    ).first()
    
    if schedule and schedule.schedule_template:
        template = schedule.schedule_template
        if template.schedule_type == '5x2':
            # Рабочие дни: Пн-Пт (0-4), выходные: Сб-Вс (5-6)
            if date_obj.weekday() >= 5:
                return 'V'
        elif template.schedule_type == '6x1':
            # Рабочие дни: Пн-Сб (0-5), выходной: Вс (6)
            if date_obj.weekday() == 6:
                return 'V'
    
    return 'I'  # Явка по умолчанию



@login_required
def fill_all_workdays(request, timesheet_id):
    """Заполнить все рабочие дни как присутствие (Я)"""
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    
    if timesheet.is_closed:
        return JsonResponse({'success': False, 'error': 'Табель закрыт, нельзя редактировать'})
    
    entries = TimesheetEntry.objects.filter(timesheet=timesheet)
    days_in_month = timesheet.get_days_in_month()
    holidays = get_holidays_for_month(timesheet.year, timesheet.month)
    
    filled_count = 0
    updated_entries = 0
    
    for entry in entries:
        entry_changed = False
        for day in range(1, days_in_month + 1):
            # Пропускаем выходные и праздничные дни
            if holidays.get(day, {}).get('is_holiday', False):
                continue
            
            current_code = getattr(entry, f'day_{day}', 'V')
            if current_code != 'I':
                setattr(entry, f'day_{day}', 'I')
                filled_count += 1
                entry_changed = True
                
                # Очищаем причину отсутствия для этого дня
                if hasattr(entry, 'absence_reasons') and str(day) in entry.absence_reasons:
                    del entry.absence_reasons[str(day)]
        
        if entry_changed:
            entry.calculate_totals()
            entry.save()
            updated_entries += 1
    
    return JsonResponse({
        'success': True, 
        'filled_count': filled_count,
        'updated_entries': updated_entries,
        'message': f'Заполнено {filled_count} отметок в {updated_entries} записях'
    })

@login_required
def director_timesheet(request):
    """Основное представление табеля для заведующей с учетом производственного календаря"""
    
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)
    
    try:
        month = int(month)
        year = int(year)
    except ValueError:
        month = date.today().month
        year = date.today().year
    
    # Получаем производственный календарь на месяц
    holidays = get_holidays_for_month(year, month)
    
    timesheet, created = Timesheet.objects.get_or_create(
        month=month,
        year=year,
        defaults={'created_by': request.user}
    )
    
    if created:
        # Инициализируем записи для всех активных сотрудников с учетом календаря
        employees = Employee.objects.filter(is_active=True)
        for employee in employees:
            entry, _ = TimesheetEntry.objects.get_or_create(
                timesheet=timesheet,
                employee=employee
            )
            days_in_month = timesheet.get_days_in_month()
            for day in range(1, days_in_month + 1):
                current_date = date(year, month, day)
                default_code = get_default_attendance_for_day(employee, current_date, holidays)
                setattr(entry, f'day_{day}', default_code)
            entry.calculate_totals()
            entry.save()
        messages.info(request, f'Табель за {timesheet.month_name} {year} создан автоматически')
    
    entries = TimesheetEntry.objects.filter(
        timesheet=timesheet
    ).select_related('employee').order_by('employee__employee_type', 'employee__full_name')
    
    days_in_month = timesheet.get_days_in_month()
    days_numbers = list(range(1, days_in_month + 1))
    
    weekday_names = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']
    today = date.today()
    days_info = []
    
    for day_num in days_numbers:
        current_date = date(year, month, day_num)
        weekday = current_date.weekday()
        holiday_info = holidays.get(day_num, {'is_holiday': weekday >= 5, 'holiday_name': ''})
        
        days_info.append({
            'number': day_num,
            'weekday_name': weekday_names[weekday],
            'weekend': holiday_info['is_holiday'],
            'is_today': current_date == today,
            'weekday_index': weekday,
            'holiday_name': holiday_info.get('holiday_name', ''),
        })
    
    stats = {
        'total_employees': entries.count(),
        'present_today': 0,
        'absent_today': 0,
        'on_vacation': 0,
        'on_sick_leave': 0,
    }
    
    today_day = date.today().day if date.today().month == month and date.today().year == year else None
    
    # Собираем данные для каждого сотрудника о документах и причинах отсутствия
    entries_data = []
    for entry in entries:
        # Создаем словарь кодов для каждого дня
        day_codes = {}
        days_in_month = timesheet.get_days_in_month()
        for day in range(1, days_in_month + 1):
            day_codes[str(day)] = getattr(entry, f'day_{day}', 'V')
        
        entry_data = {
            'entry': entry,
            'day_codes': day_codes,  # Добавляем словарь с кодами
            'absence_reasons': entry.absence_reasons if hasattr(entry, 'absence_reasons') else {},
            'absence_documents': entry.absence_documents if hasattr(entry, 'absence_documents') else {},
        }
        entries_data.append(entry_data)
        
        if today_day:
            code = getattr(entry, f'day_{today_day}', 'V')
            if code in ['I', 'N', 'RV', 'C']:
                stats['present_today'] += 1
            elif code in ['B', 'OT', 'DD', 'OZ', 'G', 'NN']:
                stats['absent_today'] += 1
        
        for day_info in days_info:
            day_num = day_info['number']
            code = getattr(entry, f'day_{day_num}', 'V')
            if code == 'OT':
                stats['on_vacation'] += 1
            elif code == 'B':
                stats['on_sick_leave'] += 1
    
    notifications = get_timesheet_notifications(request.user)
    
    context = {
        'timesheet': timesheet,
        'entries_data': entries_data,
        'days': days_info,
        'days_in_month': days_in_month,
        'stats': stats,
        'notifications': notifications,
        'month': month,
        'year': year,
        'today_day': today_day,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': range(year - 2, year + 3),
    }
    
    return render(request, 'staff/director_timesheet.html', context)


@login_required
def timesheet_quick_edit(request):
    """
    AJAX-обработчик для быстрого редактирования ячейки табеля
    """
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})
    
    entry_id = request.POST.get('entry_id')
    day = request.POST.get('day')
    action = request.POST.get('action')
    reason = request.POST.get('reason')
    hours = request.POST.get('hours')
    reason_description = request.POST.get('reason_description', '')
    document_type = request.POST.get('document_type', '')
    document_number = request.POST.get('document_number', '')
    document_start_date = request.POST.get('document_start_date', '')
    document_end_date = request.POST.get('document_end_date', '')
    
    logger.info(f"QUICK_EDIT: entry_id={entry_id}, day={day}, action={action}, reason={reason}")
    
    if not all([entry_id, day, action]):
        return JsonResponse({'success': False, 'error': 'Не все параметры переданы'})
    
    try:
        entry = TimesheetEntry.objects.get(id=entry_id)
        day = int(day)
        timesheet = entry.timesheet
        current_date = date(timesheet.year, timesheet.month, day)
        
        # Проверяем, не выходной ли день
        holidays = get_holidays_for_month(timesheet.year, timesheet.month)
        if holidays.get(day, {}).get('is_holiday', False):
            return JsonResponse({'success': False, 'error': 'Нельзя редактировать выходной день'})
        
        new_code = getattr(entry, f'day_{day}', 'V')
        
        # Обработка действий
        if action == 'present':
            new_code = 'I'  # Явка
            # Очищаем причину отсутствия для этого дня
            if hasattr(entry, 'absence_reasons') and str(day) in entry.absence_reasons:
                del entry.absence_reasons[str(day)]
                entry.save()
                
        elif action == 'absent':
            # Маппинг причин отсутствия на коды
            mapping = {
                'sick': 'B',
                'vacation': 'OT',
                'leave_out_of_schedule': 'OT',
                'dispensary': 'DD',
                'family_reasons': 'OZ',
                'no_show': 'G',
                'business_trip': 'K',
                'training': 'UO',
                'parental_leave': 'DO',
                'other': 'NN',
            }
            new_code = mapping.get(reason, 'NN')
            
            # Сохраняем причину отсутствия
            entry.set_absence_reason(day, reason, reason_description)
            
        elif action == 'overtime':
            new_code = 'C'
            # Добавляем сверхурочные часы
            if hours:
                hours_val = float(hours)
                year = timesheet.year
                tracking, _ = OvertimeTracking.objects.get_or_create(
                    employee=entry.employee,
                    year=year,
                    defaults={'total_hours': 0}
                )
                tracking.add_hours(hours_val)
                
        elif action == 'night':
            new_code = 'N'
            
        else:
            return JsonResponse({'success': False, 'error': f'Неизвестное действие: {action}'})
        
        # Обновляем код
        setattr(entry, f'day_{day}', new_code)
        
        # Обработка документа
        if document_type and request.FILES.get('document_file'):
            document_file = request.FILES['document_file']
            # Сохраняем файл
            file_path = default_storage.save(
                f'absence_documents/{timesheet.year}/{timesheet.month}/{entry.employee.id}/day_{day}_{int(timezone.now().timestamp())}_{document_file.name}',
                ContentFile(document_file.read())
            )
            
            doc_id = f"doc_{day}_{int(timezone.now().timestamp())}"
            
            start_date_obj = None
            end_date_obj = None
            if document_start_date:
                try:
                    start_date_obj = datetime.strptime(document_start_date, '%Y-%m-%d').date()
                except:
                    pass
            if document_end_date:
                try:
                    end_date_obj = datetime.strptime(document_end_date, '%Y-%m-%d').date()
                except:
                    pass
            
            if not hasattr(entry, 'absence_documents') or not entry.absence_documents:
                entry.absence_documents = {}
            
            entry.absence_documents[doc_id] = {
                'day': day,
                'document_type': document_type,
                'document_file': file_path,
                'document_number': document_number or '',
                'uploaded_at': timezone.now().isoformat(),
                'uploaded_by': request.user.username,
                'start_date': start_date_obj.isoformat() if start_date_obj else None,
                'end_date': end_date_obj.isoformat() if end_date_obj else None,
            }
        
        # Пересчитываем итоги
        entry.calculate_totals()
        entry.save()
        
        # Формируем информацию о документе для ответа
        document_info = None
        if document_type and request.FILES.get('document_file'):
            document_info = {
                'type': document_type,
                'number': document_number,
                'file_name': request.FILES['document_file'].name
            }
        
        return JsonResponse({
            'success': True,
            'new_code': new_code,
            'entry_id': entry_id,
            'day': day,
            'total_days': entry.total_days,
            'total_hours': float(entry.total_hours),
            'overtime_hours': float(entry.overtime_hours),
            'night_hours': float(entry.night_hours),
            'document_info': document_info,
            'absence_reason': reason if action == 'absent' else None,
        })
        
    except TimesheetEntry.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Запись не найдена'})
    except Exception as e:
        logger.error(f"QUICK_EDIT ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_absence_documents(request, entry_id, day):
    """
    Получить список документов для конкретного дня (AJAX)
    """
    entry = get_object_or_404(TimesheetEntry, id=entry_id)
    
    documents = []
    if hasattr(entry, 'absence_documents'):
        for doc_id, doc_info in entry.absence_documents.items():
            if doc_info.get('day') == day:
                documents.append({
                    'id': doc_id,
                    'type': doc_info.get('document_type', ''),
                    'number': doc_info.get('document_number', ''),
                    'file_name': doc_info.get('document_file', '').split('/')[-1],
                    'uploaded_at': doc_info.get('uploaded_at', ''),
                    'uploaded_by': doc_info.get('uploaded_by', ''),
                })
    
    return JsonResponse({'documents': documents})


@login_required
def delete_absence_document(request, entry_id, doc_id):
    """
    Удалить документ о отсутствии (AJAX)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})
    
    entry = get_object_or_404(TimesheetEntry, id=entry_id)
    
    if hasattr(entry, 'absence_documents') and doc_id in entry.absence_documents:
        doc_info = entry.absence_documents[doc_id]
        
        # Удаляем файл
        if 'document_file' in doc_info:
            file_path = doc_info['document_file']
            if file_path and default_storage.exists(file_path):
                default_storage.delete(file_path)
        
        del entry.absence_documents[doc_id]
        entry.save()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Документ не найден'})


def get_timesheet_notifications(user):
    """Получение уведомлений для табеля"""
    
    notifications = []
    current_year = date.today().year
    
    overtime_exceed = OvertimeTracking.objects.filter(
        year=current_year,
        total_hours__gt=120
    ).select_related('employee')
    
    for ot in overtime_exceed:
        notifications.append({
            'type': 'danger',
            'message': f'{ot.employee.full_name}: превышен лимит сверхурочных ({ot.total_hours} из 120 часов)'
        })
    
    dispensary_missing = DispensaryRecord.objects.filter(
        year=current_year,
        status='completed',
        medical_certificate=''
    ).select_related('employee')
    
    for rec in dispensary_missing:
        notifications.append({
            'type': 'warning',
            'message': f'{rec.employee.full_name}: не предоставлена справка о диспансеризации'
        })
    
    return notifications


# staff/views_timesheet.py - добавьте в конец файла

@login_required
def timesheet_export_excel(request, timesheet_id):
    """Экспорт табеля в Excel (стандартный)"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    entries = TimesheetEntry.objects.filter(
        timesheet=timesheet
    ).select_related('employee').order_by('employee__employee_type', 'employee__full_name')
    
    days_in_month = timesheet.get_days_in_month()
    days_numbers = list(range(1, days_in_month + 1))
    weekday_names = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Табель_{timesheet.month}_{timesheet.year}"
    
    # Заголовок
    ws.merge_cells('A1:AH1')
    ws['A1'] = f"Табель учета рабочего времени за {timesheet.month_name} {timesheet.year}"
    ws['A1'].font = Font(size=14, bold=True)
    
    ws.merge_cells('A2:AH2')
    ws['A2'] = "Форма по ОКУД 0504421"
    ws['A2'].font = Font(size=10, italic=True)
    
    # Заголовки столбцов
    headers = ['№ п/п', 'ФИО сотрудника', 'Должность']
    for day_num in days_numbers:
        current_date = date(timesheet.year, timesheet.month, day_num)
        weekday = current_date.weekday()
        headers.append(f"{day_num}\n({weekday_names[weekday]})")
    headers.extend(['Отработано дней', 'Отработано часов', 'Сверхурочные', 'Ночные', 'Примечания'])
    
    header_row = 4
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # Данные
    row = header_row + 1
    code_mapping = {
        'I': 'Я', 'V': 'В', 'B': 'Б', 'OT': 'ОТ', 'OZ': 'ОЗ',
        'DD': 'ДД', 'C': 'С', 'N': 'Н', 'G': 'ПР', 'K': 'К',
        'UO': 'У', 'RV': 'РП', 'NN': 'НН', 'PR': 'ПР'
    }
    
    for i, entry in enumerate(entries, 1):
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=entry.employee.full_name)
        ws.cell(row=row, column=3, value=entry.employee.position)
        
        col = 4
        for day_num in days_numbers:
            code = getattr(entry, f'day_{day_num}', 'V')
            ws.cell(row=row, column=col, value=code_mapping.get(code, code))
            col += 1
        
        last_col_start = 4 + len(days_numbers)
        ws.cell(row=row, column=last_col_start, value=entry.total_days)
        ws.cell(row=row, column=last_col_start + 1, value=float(entry.total_hours))
        ws.cell(row=row, column=last_col_start + 2, value=float(entry.overtime_hours))
        ws.cell(row=row, column=last_col_start + 3, value=float(entry.night_hours))
        ws.cell(row=row, column=last_col_start + 4, value=entry.notes)
        
        row += 1
    
    # Настройка ширины столбцов
    for i, width in enumerate([5, 30, 25, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 10, 12, 10, 10, 20], 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"tabely_{timesheet.month}_{timesheet.year}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response


@login_required
def timesheet_close(request, timesheet_id):
    """Закрытие табеля"""
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    
    if request.method == 'POST':
        timesheet.is_closed = True
        timesheet.closed_at = timezone.now()
        timesheet.save()
        messages.success(request, f'Табель за {timesheet.month_name} {timesheet.year} закрыт!')
    
    return redirect('staff:director_timesheet')


@login_required
def export_timesheet_t13_template(request, timesheet_id):
    """Экспорт табеля в форму Т-13"""
    import openpyxl
    from openpyxl import load_workbook
    
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    entries = TimesheetEntry.objects.filter(
        timesheet=timesheet
    ).select_related('employee').order_by('employee__employee_type', 'employee__full_name')
    
    template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'forma-t-13-obrazec.xlsx')
    
    if not os.path.exists(template_path):
        messages.error(request, f'Шаблон Т-13 не найден')
        return redirect('staff:director_timesheet')
    
    wb = load_workbook(template_path)
    ws = wb.active
    
    def safe_set_cell(row, column, value):
        try:
            cell = ws.cell(row=row, column=column)
            for merged_range in ws.merged_cells.ranges:
                if row >= merged_range.min_row and row <= merged_range.max_row and \
                   column >= merged_range.min_col and column <= merged_range.max_col:
                    if row == merged_range.min_row and column == merged_range.min_col:
                        cell.value = value
                    return
            cell.value = value
        except:
            pass
    
    safe_set_cell(4, 1, "МБДОУ 'Рябинушка'")
    safe_set_cell(6, 1, "Детский сад")
    safe_set_cell(10, 35, f"Т-13-{timesheet.id}")
    safe_set_cell(10, 58, date.today().strftime('%d.%m.%Y'))
    
    days_in_month = timesheet.get_days_in_month()
    
    code_mapping = {
        'I': 'Я', 'V': 'В', 'B': 'Б', 'OT': 'ОТ', 'OZ': 'ОЗ',
        'DD': 'ДД', 'C': 'С', 'N': 'Н', 'G': 'ПР', 'K': 'К',
    }
    
    data_start_row = 18
    
    for idx, entry in enumerate(entries):
        row = data_start_row + idx * 2
        
        safe_set_cell(row, 1, idx + 1)
        safe_set_cell(row, 2, f"{entry.employee.full_name}\n{entry.employee.position}")
        safe_set_cell(row, 3, entry.employee.id)
        
        col = 4
        for day in range(1, days_in_month + 1):
            code = getattr(entry, f'day_{day}', 'V')
            safe_set_cell(row, col, code_mapping.get(code, code))
            col += 1
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"tabely_T13_{timesheet.month}_{timesheet.year}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    wb.save(response)
    return response


@login_required
def export_timesheet_t12_from_template(request, timesheet_id):
    """Экспорт табеля в форму Т-12 с корректной заменой плейсхолдеров"""
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import parse_xml
    
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    entries = TimesheetEntry.objects.filter(
        timesheet=timesheet
    ).select_related('employee').order_by('employee__employee_type', 'employee__full_name')
    
    template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель_учета_рабочего_времени.docx')
    
    if not os.path.exists(template_path):
        messages.error(request, f'Шаблон не найден: {template_path}')
        return redirect('staff:director_timesheet')
    
    # Загружаем документ
    doc = Document(template_path)
    
    days_in_month = timesheet.get_days_in_month()
    
    # Сопоставление кодов для отображения
    code_mapping = {
        'I': 'Я',      # Явка
        'N': 'Н',      # Ночная работа
        'RV': 'РВ',    # Работа в выходной
        'C': 'С',      # Сверхурочная работа
        'B': 'Б',      # Больничный
        'OT': 'ОТ',    # Отпуск
        'OZ': 'ОЗ',    # Отпуск за свой счет
        'UO': 'У',     # Учебный отпуск
        'DO': 'ДО',    # Отпуск по уходу за ребенком
        'K': 'К',      # Командировка
        'G': 'ПР',     # Прогул
        'NN': 'НН',    # Неявка
        'PR': 'ПР',    # Отстранение
        'V': 'В',      # Выходной
    }
    
    # ========== 1. ЗАПОЛНЯЕМ ШАПКУ ==========
    
    # Название организации
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if '{{ organization_name }}' in cell.text:
                    cell.text = cell.text.replace('{{ organization_name }}', "МБДОУ 'Рябинушка'")
                if '{{ structural_unit }}' in cell.text:
                    cell.text = cell.text.replace('{{ structural_unit }}', "Детский сад")
                if '{{ document_number }}' in cell.text:
                    cell.text = cell.text.replace('{{ document_number }}', f"Т-12-{timesheet.id}")
                if '{{ date_created }}' in cell.text:
                    cell.text = cell.text.replace('{{ date_created }}', datetime.now().strftime('%d.%m.%Y'))
                if '{{ period_start }}' in cell.text:
                    cell.text = cell.text.replace('{{ period_start }}', f"01.{timesheet.month}.{timesheet.year}")
                if '{{ period_end }}' in cell.text:
                    cell.text = cell.text.replace('{{ period_end }}', f"{days_in_month}.{timesheet.month}.{timesheet.year}")
                if '{{ month_name }}' in cell.text:
                    cell.text = cell.text.replace('{{ month_name }}', timesheet.month_name)
                if '{{ year }}' in cell.text:
                    cell.text = cell.text.replace('{{ year }}', str(timesheet.year))
                if '{{ director_name }}' in cell.text:
                    cell.text = cell.text.replace('{{ director_name }}', "Михайлова Н.В.")
    
    # ========== 2. ЗАПОЛНЯЕМ ТАБЛИЦУ С ДАННЫМИ ==========
    
    # Находим таблицу с данными
    data_table = None
    for table in doc.tables:
        # Проверяем, есть ли в таблице плейсхолдеры
        for row in table.rows:
            for cell in row.cells:
                if '{{ index }}' in cell.text or '{{ full_name }}' in cell.text:
                    data_table = table
                    break
            if data_table:
                break
        if data_table:
            break
    
    if data_table:
        # Находим строку-шаблон и удаляем все строки после заголовков
        rows_to_keep = []
        template_row = None
        
        for i, row in enumerate(data_table.rows):
            row_text = ' '.join([cell.text for cell in row.cells])
            if '{{ index }}' in row_text and '{{ full_name }}' in row_text:
                template_row = row
                # Сохраняем строки до шаблона (заголовки)
                for j in range(i):
                    rows_to_keep.append(data_table.rows[j])
                break
        
        if template_row:
            # Удаляем все строки после заголовков
            while len(data_table.rows) > len(rows_to_keep):
                tbl = data_table._element
                tbl.remove(data_table.rows[-1]._element)
            
            # Добавляем строки для каждого сотрудника
            for idx, entry in enumerate(entries, 1):
                new_row = data_table.add_row()
                
                # Устанавливаем вертикальное центрирование
                for cell in new_row.cells:
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                
                # Заполняем ячейки
                for col_idx, cell in enumerate(new_row.cells):
                    # Номер по порядку (колонка 0)
                    if col_idx == 0:
                        cell.text = str(idx)
                    
                    # ФИО и должность (колонка 1)
                    elif col_idx == 1:
                        cell.text = f"{entry.employee.full_name}\n{entry.employee.position}"
                        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
                    
                    # Табельный номер (колонка 2)
                    elif col_idx == 2:
                        cell.text = str(entry.employee.id)
                    
                    # Дни месяца (колонки 3-33)
                    elif 3 <= col_idx <= 33:
                        day_num = col_idx - 2
                        if 1 <= day_num <= days_in_month:
                            code = getattr(entry, f'day_{day_num}', 'V')
                            display_code = code_mapping.get(code, code)
                            cell.text = display_code
                        else:
                            cell.text = ''
                    
                    # Итого за I половину (дни) - колонка 18
                    elif col_idx == 18:
                        half1_days = 0
                        for day in range(1, 16):
                            if day <= days_in_month:
                                code = getattr(entry, f'day_{day}', 'V')
                                if code in ['I', 'N', 'RV', 'C']:
                                    half1_days += 1
                        cell.text = str(half1_days) if half1_days > 0 else ''
                    
                    # Итого за II половину (дни) - колонка 34
                    elif col_idx == 34:
                        half2_days = 0
                        for day in range(16, days_in_month + 1):
                            code = getattr(entry, f'day_{day}', 'V')
                            if code in ['I', 'N', 'RV', 'C']:
                                half2_days += 1
                        cell.text = str(half2_days) if half2_days > 0 else ''
                    
                    # Всего дней (колонка 35)
                    elif col_idx == 35:
                        cell.text = str(entry.total_days)
                        if cell.text == '0':
                            cell.text = ''
                        # Жирный шрифт для итогов
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.font.bold = True
                    
                    # Всего часов (колонка 36)
                    elif col_idx == 36:
                        cell.text = f"{entry.total_hours:.1f}"
                        if cell.text == '0.0':
                            cell.text = ''
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs:
                                run.font.bold = True
                    
                    # Сверхурочные часы (колонка 37)
                    elif col_idx == 37:
                        cell.text = f"{entry.overtime_hours:.1f}" if entry.overtime_hours > 0 else ''
                    
                    # Ночные часы (колонка 38)
                    elif col_idx == 38:
                        cell.text = f"{entry.night_hours:.1f}" if entry.night_hours > 0 else ''
                    
                    # Устанавливаем выравнивание по центру для всех ячеек
                    if cell.text and col_idx != 1:
                        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Добавляем итоговую строку
        total_row = data_table.add_row()
        
        # Объединяем первые три ячейки для подписи "ИТОГО"
        if len(total_row.cells) >= 3:
            total_row.cells[0].merge(total_row.cells[2])
            total_row.cells[0].text = "ИТОГО:"
            total_row.cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            for paragraph in total_row.cells[0].paragraphs:
                for run in paragraph.runs:
                    run.font.bold = True
        
        # Подсчет итогов
        total_days_sum = sum(e.total_days for e in entries)
        total_hours_sum = sum(float(e.total_hours) for e in entries)
        total_overtime_sum = sum(float(e.overtime_hours) for e in entries)
        total_night_sum = sum(float(e.night_hours) for e in entries)
        
        # Заполняем итоговые ячейки
        if len(total_row.cells) > 35:
            total_row.cells[35].text = str(total_days_sum) if total_days_sum > 0 else ''
            for paragraph in total_row.cells[35].paragraphs:
                for run in paragraph.runs:
                    run.font.bold = True
        
        if len(total_row.cells) > 36:
            total_row.cells[36].text = f"{total_hours_sum:.1f}" if total_hours_sum > 0 else ''
            for paragraph in total_row.cells[36].paragraphs:
                for run in paragraph.runs:
                    run.font.bold = True
        
        if len(total_row.cells) > 37:
            total_row.cells[37].text = f"{total_overtime_sum:.1f}" if total_overtime_sum > 0 else ''
        
        if len(total_row.cells) > 38:
            total_row.cells[38].text = f"{total_night_sum:.1f}" if total_night_sum > 0 else ''
    
    # ========== 3. ЗАПОЛНЯЕМ ПОДПИСИ ==========
    
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if '{{ director_name }}' in cell.text:
                    cell.text = cell.text.replace('{{ director_name }}', "Михайлова Н.В.")
    
    # ========== 4. СОХРАНЯЕМ ДОКУМЕНТ ==========
    
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    
    # Формируем имя файла на русском
    month_names = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    month_name = month_names.get(timesheet.month, str(timesheet.month))
    
    filename = f"Табель_Т12_{month_name}_{timesheet.year}.docx"
    
    # Кодируем имя файла для поддержки кириллицы
    from urllib.parse import quote
    encoded_filename = quote(filename)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
    
    return response


# staff/views_timesheet.py - добавьте эти функции в конец файла

@login_required
def get_available_employees(request, timesheet_id):
    """Получение сотрудников, которые ещё не добавлены в табель"""
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    
    # Все активные сотрудники
    all_employees = Employee.objects.filter(is_active=True)
    
    # ID уже добавленных
    existing_ids = TimesheetEntry.objects.filter(timesheet=timesheet).values_list('employee_id', flat=True)
    
    # Доступные сотрудники
    available = all_employees.exclude(id__in=existing_ids)
    
    data = []
    for emp in available:
        data.append({
            'id': emp.id,
            'full_name': emp.full_name,
            'position': emp.position,
            'employee_type_display': emp.get_employee_type_display()
        })
    
    return JsonResponse({'employees': data})


@login_required
def add_employees_to_timesheet(request, timesheet_id):
    """Добавление выбранных сотрудников в табель"""
    import json
    
    timesheet = get_object_or_404(Timesheet, id=timesheet_id)
    
    # Проверяем, не закрыт ли табель
    if timesheet.is_closed:
        return JsonResponse({'success': False, 'error': 'Табель закрыт, нельзя добавлять сотрудников'})
    
    try:
        data = json.loads(request.body)
        employee_ids = data.get('employee_ids', [])
        
        added_count = 0
        errors = []
        
        # Получаем производственный календарь на месяц
        holidays = get_holidays_for_month(timesheet.year, timesheet.month)
        
        for emp_id in employee_ids:
            try:
                employee = Employee.objects.get(id=emp_id, is_active=True)
                
                # Проверяем, не добавлен ли уже
                existing = TimesheetEntry.objects.filter(timesheet=timesheet, employee=employee).exists()
                if not existing:
                    entry = TimesheetEntry.objects.create(timesheet=timesheet, employee=employee)
                    
                    # Инициализируем дни с учетом выходных
                    days_in_month = timesheet.get_days_in_month()
                    for day in range(1, days_in_month + 1):
                        current_date = date(timesheet.year, timesheet.month, day)
                        default_code = get_default_attendance_for_day(employee, current_date, holidays)
                        setattr(entry, f'day_{day}', default_code)
                    
                    entry.calculate_totals()
                    entry.save()
                    added_count += 1
                    
            except Employee.DoesNotExist:
                errors.append(f'Сотрудник с ID {emp_id} не найден')
        
        if added_count > 0:
            return JsonResponse({'success': True, 'added_count': added_count, 'errors': errors})
        else:
            return JsonResponse({'success': False, 'error': 'Нет сотрудников для добавления', 'errors': errors})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Неверный формат данных'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def check_dispensary_right(request):
    """AJAX-проверка права на диспансеризацию"""
    
    entry_id = request.GET.get('entry_id')
    day = request.GET.get('day')
    
    if not entry_id or not day:
        return JsonResponse({'has_right': False, 'message': 'Недостаточно данных'})
    
    try:
        entry = get_object_or_404(TimesheetEntry, id=entry_id)
        employee = entry.employee
        age = employee.age
        
        if age < 18:
            return JsonResponse({'has_right': False, 'message': 'Сотрудники младше 18 лет не имеют права'})
        
        dispensary_count = DispensaryRecord.objects.filter(
            employee=employee, year=entry.timesheet.year
        ).count()
        
        if age >= 40 and dispensary_count >= 1:
            return JsonResponse({'has_right': False, 'message': 'Сотрудник уже использовал день диспансеризации'})
        
        return JsonResponse({'has_right': True, 'message': ''})
        
    except Exception as e:
        return JsonResponse({'has_right': False, 'message': str(e)})


@login_required
def debug_template_structure(request):
    """Временная функция для отладки структуры шаблона"""
    from docx import Document
    
    template_path = os.path.join(settings.BASE_DIR, 'templates', 'documents', 'Табель_учета_рабочего_времени.docx')
    
    if not os.path.exists(template_path):
        return HttpResponse(f"Шаблон не найден: {template_path}")
    
    doc = Document(template_path)
    
    # Собираем информацию о структуре
    output = []
    output.append("=== СТРУКТУРА ШАБЛОНА ===\n")
    
    # Параграфы
    output.append("ПАРАГРАФЫ:")
    for i, para in enumerate(doc.paragraphs):
        if para.text.strip():
            output.append(f"  {i}: {para.text[:100]}")
    
    output.append("\n" + "="*50 + "\n")
    
    # Таблицы
    output.append("ТАБЛИЦЫ:")
    for t_idx, table in enumerate(doc.tables):
        output.append(f"\nТаблица {t_idx + 1}: {len(table.rows)} строк, {len(table.columns)} колонок")
        
        for r_idx, row in enumerate(table.rows[:10]):  # первые 10 строк
            row_data = []
            for c_idx, cell in enumerate(row.cells[:20]):  # первые 20 колонок
                text = cell.text.strip().replace('\n', ' ')[:30]
                if text:
                    row_data.append(f"[{c_idx}]={text}")
            if row_data:
                output.append(f"  Строка {r_idx}: {', '.join(row_data)}")
    
    return HttpResponse('<br>'.join(output), content_type='text/html')