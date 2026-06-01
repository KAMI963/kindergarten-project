# lessons/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta, date
import json
from django.db.models import Q, Count
from django.core.paginator import Paginator

from .models import LessonPlan, LessonSchedule, LessonReminder, ActivityTemplate
from .forms import LessonPlanForm, LessonCompleteForm, LessonScheduleForm, LessonReminderForm, ActivityTemplateForm
from children.models import Group

def get_teacher_group(user):
    """Получает группу учителя"""
    try:
        return Group.objects.filter(teacher=user).first()
    except:
        return None

@login_required
def lessons_dashboard(request):
    """Главная страница занятий"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    teacher_group = get_teacher_group(request.user)
    today = timezone.now().date()
    
    # Ближайшие занятия
    upcoming_lessons = LessonPlan.objects.filter(
        teacher=request.user,
        planned_date__gte=today,
        completed=False
    ).order_by('planned_date', 'planned_time')[:5]
    
    # Предстоящие напоминания
    upcoming_reminders = LessonReminder.objects.filter(
        teacher=request.user,
        due_date__gte=today,
        completed=False
    ).order_by('due_date', 'due_time')[:5]
    
    # Сегодняшние занятия
    todays_lessons = LessonPlan.objects.filter(
        teacher=request.user,
        planned_date=today
    ).order_by('planned_time')
    
    # Статистика
    total_lessons = LessonPlan.objects.filter(teacher=request.user).count()
    completed_lessons = LessonPlan.objects.filter(teacher=request.user, completed=True).count()
    pending_lessons = total_lessons - completed_lessons
    
    # Расписание на текущую неделю
    current_week_schedule = get_weekly_schedule(request.user)
    
    context = {
        'teacher_group': teacher_group,
        'upcoming_lessons': upcoming_lessons,
        'upcoming_reminders': upcoming_reminders,
        'todays_lessons': todays_lessons,
        'total_lessons': total_lessons,
        'completed_lessons': completed_lessons,
        'pending_lessons': pending_lessons,
        'current_week_schedule': current_week_schedule,
        'today': today,
    }
    
    return render(request, 'lessons/lessons_dashboard.html', context)

def get_weekly_schedule(user):
    """Получает расписание на текущую неделю"""
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    
    weekly_schedule = {}
    for i in range(7):
        current_date = start_of_week + timedelta(days=i)
        day_schedule = LessonSchedule.objects.filter(
            group__teacher=user,
            day_of_week=current_date.weekday()
        ).order_by('start_time')
        weekly_schedule[current_date] = day_schedule
    
    return weekly_schedule

# lessons/views.py - исправленная функция

@login_required
def lesson_plan_list(request):
    """Список планов занятий"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    # Фильтрация
    status_filter = request.GET.get('status', 'all')
    lesson_type_filter = request.GET.get('type', 'all')
    group_filter = request.GET.get('group', 'all')
    
    lessons = LessonPlan.objects.filter(teacher=request.user)
    
    if status_filter == 'completed':
        lessons = lessons.filter(completed=True)
    elif status_filter == 'upcoming':
        lessons = lessons.filter(completed=False, planned_date__gte=timezone.now().date())
    elif status_filter == 'past':
        lessons = lessons.filter(planned_date__lt=timezone.now().date())
    
    if lesson_type_filter != 'all':
        lessons = lessons.filter(lesson_type=lesson_type_filter)
    
    if group_filter != 'all':
        lessons = lessons.filter(group_id=group_filter)
    
    # Пагинация
    paginator = Paginator(lessons.order_by('-planned_date'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Группы для фильтра
    groups = Group.objects.filter(teacher=request.user)
    
    context = {
        'page_obj': page_obj,
        'groups': groups,
        'status_filter': status_filter,
        'lesson_type_filter': lesson_type_filter,
        'group_filter': group_filter,
        'lesson_types': LessonPlan.LESSON_TYPE_CHOICES,
        'today': timezone.now().date(),  # ДОБАВЛЕНО: передаем сегодняшнюю дату
    }
    
    return render(request, 'lessons/lesson_plan_list.html', context)

@login_required
def lesson_plan_create(request):
    """Создание нового плана занятия"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LessonPlanForm(request.POST, user=request.user)
        if form.is_valid():
            lesson_plan = form.save(commit=False)
            lesson_plan.teacher = request.user
            lesson_plan.save()
            
            messages.success(request, 'План занятия успешно создан!')
            return redirect('lessons:lesson_plan_detail', plan_id=lesson_plan.id)
    else:
        form = LessonPlanForm(user=request.user)
    
    return render(request, 'lessons/lesson_plan_form.html', {
        'form': form,
        'title': 'Создание плана занятия',
        'submit_text': 'Создать план'
    })

@login_required
def lesson_plan_detail(request, plan_id):
    """Детальная информация о плане занятия"""
    lesson_plan = get_object_or_404(LessonPlan, id=plan_id, teacher=request.user)
    
    return render(request, 'lessons/lesson_plan_detail.html', {
        'lesson_plan': lesson_plan
    })

@login_required
def lesson_plan_edit(request, plan_id):
    """Редактирование плана занятия"""
    lesson_plan = get_object_or_404(LessonPlan, id=plan_id, teacher=request.user)
    
    if request.method == 'POST':
        form = LessonPlanForm(request.POST, instance=lesson_plan, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'План занятия успешно обновлен!')
            return redirect('lessons:lesson_plan_detail', plan_id=lesson_plan.id)
    else:
        form = LessonPlanForm(instance=lesson_plan, user=request.user)
    
    return render(request, 'lessons/lesson_plan_form.html', {
        'form': form,
        'title': 'Редактирование плана занятия',
        'submit_text': 'Сохранить изменения',
        'lesson_plan': lesson_plan
    })

@login_required
def lesson_plan_complete(request, plan_id):
    """Отметка о проведении занятия"""
    lesson_plan = get_object_or_404(LessonPlan, id=plan_id, teacher=request.user)
    
    if request.method == 'POST':
        form = LessonCompleteForm(request.POST, instance=lesson_plan)
        if form.is_valid():
            lesson_plan = form.save(commit=False)
            lesson_plan.completed = True
            lesson_plan.save()
            
            messages.success(request, 'Занятие отмечено как проведенное!')
            return redirect('lessons:lesson_plan_detail', plan_id=lesson_plan.id)
    else:
        form = LessonCompleteForm(instance=lesson_plan)
    
    return render(request, 'lessons/lesson_complete_form.html', {
        'form': form,
        'lesson_plan': lesson_plan
    })

@login_required
def lesson_plan_delete(request, plan_id):
    """Удаление плана занятия"""
    lesson_plan = get_object_or_404(LessonPlan, id=plan_id, teacher=request.user)
    
    if request.method == 'POST':
        lesson_plan.delete()
        messages.success(request, 'План занятия успешно удален!')
        return redirect('lessons:lesson_plan_list')
    
    return render(request, 'lessons/lesson_plan_confirm_delete.html', {
        'lesson_plan': lesson_plan
    })

@login_required
def schedule_view(request):
    """Просмотр расписания"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    teacher_group = get_teacher_group(request.user)
    
    if not teacher_group:
        messages.error(request, 'У вас нет назначенной группы.')
        return redirect('lessons:lessons_dashboard')
    
    # Полное расписание для группы
    schedule = LessonSchedule.objects.filter(group=teacher_group).order_by('day_of_week', 'start_time')
    
    # Группировка по дням недели
    schedule_by_day = {}
    for day_num, day_name in LessonSchedule.DAYS_OF_WEEK:
        day_schedule = schedule.filter(day_of_week=day_num)
        if day_schedule.exists():
            schedule_by_day[day_name] = day_schedule
    
    context = {
        'teacher_group': teacher_group,
        'schedule_by_day': schedule_by_day,
        'days_of_week': LessonSchedule.DAYS_OF_WEEK,
    }
    
    return render(request, 'lessons/schedule_view.html', context)

@login_required
def schedule_edit(request):
    """Редактирование расписания"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    teacher_group = get_teacher_group(request.user)
    
    if not teacher_group:
        messages.error(request, 'У вас нет назначенной группы.')
        return redirect('lessons:lessons_dashboard')
    
    if request.method == 'POST':
        form = LessonScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.group = teacher_group
            schedule.save()
            
            messages.success(request, 'Элемент расписания успешно добавлен!')
            return redirect('lessons:schedule_view')
    else:
        form = LessonScheduleForm(initial={'group': teacher_group})
    
    # Существующее расписание
    schedule = LessonSchedule.objects.filter(group=teacher_group).order_by('day_of_week', 'start_time')
    
    context = {
        'form': form,
        'teacher_group': teacher_group,
        'schedule': schedule,
        'days_of_week': LessonSchedule.DAYS_OF_WEEK,
    }
    
    return render(request, 'lessons/schedule_edit.html', context)

@login_required
def schedule_delete(request, schedule_id):
    """Удаление элемента расписания"""
    schedule_item = get_object_or_404(LessonSchedule, id=schedule_id, group__teacher=request.user)
    
    if request.method == 'POST':
        schedule_item.delete()
        messages.success(request, 'Элемент расписания удален!')
    
    return redirect('lessons:schedule_edit')

@login_required
def reminders_list(request):
    """Список напоминаний"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    # Фильтрация
    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    
    reminders = LessonReminder.objects.filter(teacher=request.user)
    
    if status_filter == 'completed':
        reminders = reminders.filter(completed=True)
    elif status_filter == 'pending':
        reminders = reminders.filter(completed=False)
    
    if priority_filter != 'all':
        reminders = reminders.filter(priority=priority_filter)
    
    # Пагинация
    paginator = Paginator(reminders.order_by('due_date', 'due_time'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
    }
    
    return render(request, 'lessons/reminders_list.html', context)

@login_required
def reminder_create(request):
    """Создание напоминания"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LessonReminderForm(request.POST, user=request.user)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.teacher = request.user
            reminder.save()
            
            messages.success(request, 'Напоминание успешно создано!')
            return redirect('lessons:reminders_list')
    else:
        form = LessonReminderForm(user=request.user)
    
    return render(request, 'lessons/reminder_form.html', {
        'form': form,
        'title': 'Создание напоминания',
        'submit_text': 'Создать напоминание'
    })

@login_required
def reminder_toggle(request, reminder_id):
    """Переключение статуса напоминания"""
    reminder = get_object_or_404(LessonReminder, id=reminder_id, teacher=request.user)
    
    if request.method == 'POST':
        reminder.completed = not reminder.completed
        reminder.save()
        
        status = "выполнено" if reminder.completed else "не выполнено"
        messages.success(request, f'Напоминание отмечено как {status}!')
    
    return redirect('lessons:reminders_list')

@login_required
def reminder_delete(request, reminder_id):
    """Удаление напоминания"""
    reminder = get_object_or_404(LessonReminder, id=reminder_id, teacher=request.user)
    
    if request.method == 'POST':
        reminder.delete()
        messages.success(request, 'Напоминание удалено!')
    
    return redirect('lessons:reminders_list')

@login_required
def calendar_view(request):
    """Календарный вид занятий и напоминаний"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    # Получаем год и месяц из параметров
    year = request.GET.get('year', timezone.now().year)
    month = request.GET.get('month', timezone.now().month)
    
    try:
        year = int(year)
        month = int(month)
    except (ValueError, TypeError):
        year = timezone.now().year
        month = timezone.now().month
    
    # Занятия на месяц
    lessons = LessonPlan.objects.filter(
        teacher=request.user,
        planned_date__year=year,
        planned_date__month=month
    )
    
    # Напоминания на месяц
    reminders = LessonReminder.objects.filter(
        teacher=request.user,
        due_date__year=year,
        due_date__month=month
    )
    
    context = {
        'year': year,
        'month': month,
        'lessons': lessons,
        'reminders': reminders,
    }
    
    return render(request, 'lessons/calendar_view.html', context)

@login_required
def templates_list(request):
    """Список шаблонов занятий"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    templates = ActivityTemplate.objects.filter(
        Q(created_by=request.user) | Q(is_public=True)
    )
    
    # Фильтрация
    age_filter = request.GET.get('age_group', 'all')
    type_filter = request.GET.get('lesson_type', 'all')
    
    if age_filter != 'all':
        templates = templates.filter(age_group=age_filter)
    
    if type_filter != 'all':
        templates = templates.filter(lesson_type=type_filter)
    
    context = {
        'templates': templates,
        'age_filter': age_filter,
        'type_filter': type_filter,
        'age_groups': ActivityTemplate.AGE_GROUP_CHOICES,
        'lesson_types': LessonPlan.LESSON_TYPE_CHOICES,
    }
    
    return render(request, 'lessons/templates_list.html', context)

@login_required
def template_create(request):
    """Создание шаблона занятия"""
    if request.user.role not in ['teacher', 'director']:
        messages.error(request, 'Доступ только для сотрудников детского сада.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ActivityTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user
            template.save()
            
            messages.success(request, 'Шаблон занятия успешно создан!')
            return redirect('lessons:templates_list')
    else:
        form = ActivityTemplateForm()
    
    return render(request, 'lessons/template_form.html', {
        'form': form,
        'title': 'Создание шаблона занятия',
        'submit_text': 'Создать шаблон'
    })

@login_required
def template_use(request, template_id):
    """Использование шаблона для создания плана занятия"""
    template = get_object_or_404(ActivityTemplate, id=template_id)
    teacher_group = get_teacher_group(request.user)
    
    if request.method == 'POST':
        form = LessonPlanForm(request.POST, user=request.user)
        if form.is_valid():
            lesson_plan = form.save(commit=False)
            lesson_plan.teacher = request.user
            lesson_plan.save()
            
            messages.success(request, 'План занятия создан на основе шаблона!')
            return redirect('lessons:lesson_plan_detail', plan_id=lesson_plan.id)
    else:
        # Предзаполняем форму данными из шаблона
        initial_data = {
            'title': template.title,
            'lesson_type': template.lesson_type,
            'description': template.description,
            'objectives': template.objectives,
            'materials': template.materials,
            'duration': template.duration,
        }
        
        if teacher_group and teacher_group.age_category == template.age_group:
            initial_data['group'] = teacher_group
        
        form = LessonPlanForm(initial=initial_data, user=request.user)
    
    return render(request, 'lessons/lesson_plan_form.html', {
        'form': form,
        'title': 'Создание занятия из шаблона',
        'submit_text': 'Создать план',
        'template': template
    })

# AJAX views
@login_required
def get_calendar_events(request):
    """AJAX endpoint для получения событий календаря"""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Занятия
    lessons = LessonPlan.objects.filter(
        teacher=request.user,
        planned_date__range=[start, end]
    )
    
    # Напоминания
    reminders = LessonReminder.objects.filter(
        teacher=request.user,
        due_date__range=[start, end],
        completed=False
    )
    
    events = []
    
    for lesson in lessons:
        events.append({
            'id': f'lesson_{lesson.id}',
            'title': lesson.title,
            'start': f"{lesson.planned_date.isoformat()}T{lesson.planned_time.isoformat()}",
            'end': f"{lesson.planned_date.isoformat()}T{(datetime.combine(lesson.planned_date, lesson.planned_time) + timedelta(minutes=lesson.duration)).time().isoformat()}",
            'color': '#3498db' if not lesson.completed else '#95a5a6',
            'textColor': 'white',
            'extendedProps': {
                'type': 'lesson',
                'completed': lesson.completed,
                'url': f"/lessons/plans/{lesson.id}/"
            }
        })
    
    for reminder in reminders:
        events.append({
            'id': f'reminder_{reminder.id}',
            'title': f"⏰ {reminder.title}",
            'start': f"{reminder.due_date.isoformat()}" + (f"T{reminder.due_time.isoformat()}" if reminder.due_time else ""),
            'color': '#e74c3c' if reminder.priority == 1 else '#f39c12' if reminder.priority == 2 else '#f1c40f',
            'textColor': 'white',
            'extendedProps': {
                'type': 'reminder',
                'priority': reminder.priority,
                'url': f"/lessons/reminders/"
            }
        })
    
    return JsonResponse(events, safe=False)
