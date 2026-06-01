from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta, date
import json
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from .models import Menu, WeeklyMenuPlan, ChildMeal
from .forms import MenuForm, WeeklyMenuPlanForm, MenuApprovalForm
from children.models import Child, ChildParent, Group
from openpyxl.utils import get_column_letter

def director_required(view_func):
    decorated_view_func = user_passes_test(
        lambda u: u.is_authenticated and u.role == 'director',
        login_url='/accounts/login/'
    )(view_func)
    return decorated_view_func

@login_required
def nutrition_dashboard(request):
    """Главная страница питания"""
    if request.user.role == 'director':
        return redirect('nutrition:menu_approval')
    elif request.user.role == 'parent':
        return redirect('nutrition:parent_menu')
    elif request.user.role == 'teacher':
        return redirect('nutrition:teacher_dashboard')
    
    return redirect('dashboard')

@login_required
@director_required
def menu_management(request):
    """Управление меню для заведующей"""
    # Получаем текущую неделю
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    
    groups = Group.objects.all()
    selected_group_id = request.GET.get('group')
    selected_week = request.GET.get('week', start_of_week.isoformat())
    
    try:
        selected_week = datetime.strptime(selected_week, '%Y-%m-%d').date()
    except:
        selected_week = start_of_week
    
    # Получаем меню для выбранной группы и недели
    menus = {}
    if selected_group_id:
        group = get_object_or_404(Group, id=selected_group_id)
        
        # Создаем структуру данных для недельного меню
        for day in range(7):
            current_date = selected_week + timedelta(days=day)
            day_menus = Menu.objects.filter(
                group=group,
                day_of_week=day
            ).order_by('meal_type')
            
            menus[current_date] = {
                'date': current_date,
                'day_name': current_date.strftime('%A'),
                'meals': {
                    'breakfast': None,
                    'lunch': None,
                    'snack': None,
                    'dinner': None,
                }
            }
            
            for menu in day_menus:
                menus[current_date]['meals'][menu.meal_type] = menu
    
    # Получаем планы меню на неделю
    weekly_plans = WeeklyMenuPlan.objects.filter(week_start_date=selected_week)
    
    context = {
        'groups': groups,
        'selected_group_id': selected_group_id,
        'selected_week': selected_week,
        'menus': menus,
        'weekly_plans': weekly_plans,
        'meal_types': Menu.MEAL_TYPES,
        'next_week': selected_week + timedelta(days=7),
        'prev_week': selected_week - timedelta(days=7),
    }
    
    return render(request, 'nutrition/menu_management.html', context)

@login_required
@director_required
def menu_approval(request):
    """Страница утверждения меню"""
    # Получаем неподтвержденные меню
    pending_menus = Menu.objects.filter(is_approved=False).select_related('group')
    
    # Группируем по неделям и группам
    weekly_menus = {}
    for menu in pending_menus:
        # Определяем неделю для меню
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        week_key = f"{start_of_week}_{menu.group.id}"
        
        if week_key not in weekly_menus:
            weekly_menus[week_key] = {
                'group': menu.group,
                'week_start': start_of_week,
                'menus': []
            }
        
        weekly_menus[week_key]['menus'].append(menu)
    
    if request.method == 'POST':
        form = MenuApprovalForm(request.POST)
        if form.is_valid():
            menu_ids = request.POST.getlist('menu_ids')
            if menu_ids and form.cleaned_data['is_approved']:
                # Утверждаем выбранные меню
                approved_count = Menu.objects.filter(
                    id__in=menu_ids
                ).update(
                    is_approved=True,
                    approved_by=request.user,
                    approved_date=timezone.now()
                )
                
                messages.success(request, f'Утверждено {approved_count} позиций меню.')
                return redirect('nutrition:menu_approval')
            else:
                messages.error(request, 'Выберите меню для утверждения и поставьте подпись.')
    
    else:
        form = MenuApprovalForm()
    
    context = {
        'weekly_menus': list(weekly_menus.values()),
        'form': form,
    }
    
    return render(request, 'nutrition/menu_approval.html', context)

@login_required
@director_required
def approve_menu_ajax(request):
    """AJAX утверждение меню"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            menu_id = data.get('menu_id')
            signature = data.get('signature')
            
            if not signature:
                return JsonResponse({'success': False, 'error': 'Требуется подпись'})
            
            menu = get_object_or_404(Menu, id=menu_id)
            menu.is_approved = True
            menu.approved_by = request.user
            menu.approved_date = timezone.now()
            menu.save()
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Неверный запрос'})

@login_required
@director_required
def approve_weekly_menu(request, week_start, group_id):
    """Утверждение всего недельного меню для группы"""
    try:
        week_start = datetime.strptime(week_start, '%Y-%m-%d').date()
        group = get_object_or_404(Group, id=group_id)
        
        # Утверждаем все меню группы на указанную неделю
        approved_count = Menu.objects.filter(
            group=group,
            day_of_week__in=range(7),
            is_approved=False
        ).update(
            is_approved=True,
            approved_by=request.user,
            approved_date=timezone.now()
        )
        
        # Создаем или обновляем план меню на неделю
        weekly_plan, created = WeeklyMenuPlan.objects.get_or_create(
            group=group,
            week_start_date=week_start,
            defaults={
                'is_approved': True,
                'approved_by': request.user,
                'approved_date': timezone.now()
            }
        )
        
        if not created:
            weekly_plan.is_approved = True
            weekly_plan.approved_by = request.user
            weekly_plan.approved_date = timezone.now()
            weekly_plan.save()
        
        messages.success(request, f'Меню для группы "{group.name}" на неделю с {week_start} утверждено. Утверждено {approved_count} позиций.')
        
    except Exception as e:
        messages.error(request, f'Ошибка при утверждении меню: {str(e)}')
    
    return redirect('nutrition:menu_approval')

# nutrition/views.py - ИСПРАВЛЕННАЯ ФУНКЦИЯ parent_menu

@login_required
def parent_menu(request):
    """Просмотр меню для родителя"""
    import json
    from datetime import date, timedelta
    from django.utils import timezone
    
    print("\n" + "="*60)
    print("РОДИТЕЛЬСКОЕ МЕНЮ - НАЧАЛО")
    print("="*60)
    print(f"Пользователь: {request.user.username}, роль: {request.user.role}")
    
    # Получаем детей родителя
    try:
        parent_profile = request.user.parentprofile
        print(f"Родитель: {parent_profile.user.get_full_name()}")
        
        # ИСПРАВЛЕНО: используем 'parent_relations' вместо 'parents_relations'
        children = Child.objects.filter(
            parent_relations__parent=parent_profile,
            is_active=True
        ).distinct()
        
        print(f"Найдено детей: {children.count()}")
        for child in children:
            print(f"  - {child.full_name}, группа: {child.group.name if child.group else 'НЕТ ГРУППЫ'}")
            
    except Exception as e:
        print(f"Ошибка получения детей: {e}")
        children = Child.objects.none()
    
    # Параметры фильтрации
    selected_child_id = request.GET.get('child')
    selected_week = request.GET.get('week', date.today().isoformat())
    
    try:
        selected_week = datetime.strptime(selected_week, '%Y-%m-%d').date()
        start_of_week = selected_week - timedelta(days=selected_week.weekday())
        print(f"Выбрана неделя: {start_of_week}")
    except Exception as e:
        print(f"Ошибка парсинга даты: {e}")
        start_of_week = date.today() - timedelta(days=date.today().weekday())
    
    selected_child = None
    weekly_menu = {}
    
    if selected_child_id and children.filter(id=selected_child_id).exists():
        selected_child = children.get(id=selected_child_id)
        print(f"Выбран ребенок: {selected_child.full_name}")
        print(f"Группа ребенка: {selected_child.group.name if selected_child.group else 'НЕТ ГРУППЫ'}")
        
        if selected_child.group:
            # Получаем утвержденное меню для группы ребенка
            for day in range(7):
                current_date = start_of_week + timedelta(days=day)
                day_menus = Menu.objects.filter(
                    group=selected_child.group,
                    day_of_week=day,
                    is_approved=True
                ).order_by('meal_type')
                
                weekly_menu[current_date] = {
                    'date': current_date,
                    'day_name': current_date.strftime('%A'),
                    'is_today': current_date == date.today(),
                    'meals': {
                        'breakfast': None,
                        'lunch': None,
                        'snack': None,
                        'dinner': None,
                    }
                }
                
                for menu in day_menus:
                    weekly_menu[current_date]['meals'][menu.meal_type] = menu
                    print(f"  {current_date} - {menu.get_meal_type_display()}: {menu.dish_name}")
            
            print(f"Сформировано меню на {len(weekly_menu)} дней")
        else:
            print("У ребенка нет группы!")
    else:
        print("Ребенок не выбран или не найден")
    
    # Подсчет общего количества блюд
    total_dishes = 0
    for date, day_data in weekly_menu.items():
        for meal in day_data['meals'].values():
            if meal:
                total_dishes += 1
    
    context = {
        'children': children,
        'selected_child': selected_child,
        'selected_week': start_of_week,
        'weekly_menu': weekly_menu,
        'meal_types': Menu.MEAL_TYPES,
        'next_week': start_of_week + timedelta(days=7),
        'prev_week': start_of_week - timedelta(days=7),
        'total_dishes': total_dishes,
    }
    
    print("\n" + "="*60)
    print("РОДИТЕЛЬСКОЕ МЕНЮ - ЗАВЕРШЕНИЕ")
    print("="*60 + "\n")
    
    return render(request, 'nutrition/parent_menu.html', context)

@login_required
@director_required
def export_menu_excel(request):
    """Выгрузка меню в Excel"""
    group_id = request.GET.get('group')
    week_start = request.GET.get('week_start')
    
    print(f"DEBUG: group_id={group_id}, week_start={week_start}")  # Для отладки
    
    # Если параметры не указаны, используем текущую неделю
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    
    if not week_start:
        week_start = start_of_week.isoformat()
    
    # Создаем Excel файл
    wb = Workbook()
    ws = wb.active
    
    try:
        # Пытаемся преобразовать дату
        week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
    except (ValueError, TypeError) as e:
        print(f"DEBUG: Date parsing error: {e}")
        # Если не удалось распарсить дату, используем текущую неделю
        week_start_date = start_of_week
        messages.warning(request, f'Используется текущая неделя: {week_start_date}')
    
    if group_id and group_id != 'all':
        try:
            group = get_object_or_404(Group, id=group_id)
            ws.title = f"Меню {group.name}"
            # Получаем меню для конкретной группы на указанную неделю
            menus = Menu.objects.filter(
                group=group,
                day_of_week__in=range(7),
                is_approved=True
            ).order_by('day_of_week', 'meal_type')
        except Group.DoesNotExist:
            return HttpResponse('Группа не найдена')
    else:
        # Все группы
        ws.title = "Все меню"
        menus = Menu.objects.filter(
            day_of_week__in=range(7),
            is_approved=True
        ).select_related('group').order_by('group__name', 'day_of_week', 'meal_type')
    
    # Заголовок
    if group_id and group_id != 'all':
        title = f'Меню для группы "{group.name}" на неделю с {week_start_date}'
        # Для одной группы - 9 столбцов
        ws.merge_cells('A1:I1')
        headers = ['День недели', 'Тип питания', 'Блюдо', 'Описание', 'Вес (г)', 'Калории', 'Белки (г)', 'Жиры (г)', 'Углеводы (г)']
    else:
        title = f'Меню питания на неделю с {week_start_date}'
        # Для всех групп - 10 столбцов
        ws.merge_cells('A1:J1')
        headers = ['Группа', 'День недели', 'Тип питания', 'Блюдо', 'Описание', 'Вес (г)', 'Калории', 'Белки (г)', 'Жиры (г)', 'Углеводы (г)']
    
    ws['A1'] = title
    ws['A1'].font = Font(size=14, bold=True)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # Заголовки столбцов
    start_row = 3
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')
    
    # Данные
    row = start_row + 1
    day_names = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    meal_type_names = dict(Menu.MEAL_TYPES)
    
    for menu in menus:
        if group_id and group_id != 'all':
            # Для одной группы
            ws.cell(row=row, column=1, value=day_names[menu.day_of_week])
            ws.cell(row=row, column=2, value=meal_type_names[menu.meal_type])
            ws.cell(row=row, column=3, value=menu.dish_name)
            ws.cell(row=row, column=4, value=menu.description)
            ws.cell(row=row, column=5, value=menu.weight)
            ws.cell(row=row, column=6, value=menu.calories)
            ws.cell(row=row, column=7, value=float(menu.proteins))
            ws.cell(row=row, column=8, value=float(menu.fats))
            ws.cell(row=row, column=9, value=float(menu.carbohydrates))
        else:
            # Для всех групп
            ws.cell(row=row, column=1, value=menu.group.name)
            ws.cell(row=row, column=2, value=day_names[menu.day_of_week])
            ws.cell(row=row, column=3, value=meal_type_names[menu.meal_type])
            ws.cell(row=row, column=4, value=menu.dish_name)
            ws.cell(row=row, column=5, value=menu.description)
            ws.cell(row=row, column=6, value=menu.weight)
            ws.cell(row=row, column=7, value=menu.calories)
            ws.cell(row=row, column=8, value=float(menu.proteins))
            ws.cell(row=row, column=9, value=float(menu.fats))
            ws.cell(row=row, column=10, value=float(menu.carbohydrates))
        row += 1
    
    # Настройка ширины столбцов
    try:
        if group_id and group_id != 'all':
            # Для одной группы - 9 столбцов
            column_widths = [15, 12, 25, 30, 8, 10, 10, 10, 12]
            for i, width in enumerate(column_widths, 1):
                col_letter = get_column_letter(i)
                ws.column_dimensions[col_letter].width = width
        else:
            # Для всех групп - 10 столбцов
            column_widths = [15, 15, 12, 25, 30, 8, 10, 10, 10, 12]
            for i, width in enumerate(column_widths, 1):
                col_letter = get_column_letter(i)
                ws.column_dimensions[col_letter].width = width
    except Exception as e:
        print(f"DEBUG: Column width error: {e}")
        # Резервная настройка ширины
        if group_id and group_id != 'all':
            ws.column_dimensions['A'].width = 15
            ws.column_dimensions['B'].width = 12
            ws.column_dimensions['C'].width = 25
            ws.column_dimensions['D'].width = 30
            ws.column_dimensions['E'].width = 8
            ws.column_dimensions['F'].width = 10
            ws.column_dimensions['G'].width = 10
            ws.column_dimensions['H'].width = 10
            ws.column_dimensions['I'].width = 12
        else:
            ws.column_dimensions['A'].width = 15
            ws.column_dimensions['B'].width = 15
            ws.column_dimensions['C'].width = 12
            ws.column_dimensions['D'].width = 25
            ws.column_dimensions['E'].width = 30
            ws.column_dimensions['F'].width = 8
            ws.column_dimensions['G'].width = 10
            ws.column_dimensions['H'].width = 10
            ws.column_dimensions['I'].width = 10
            ws.column_dimensions['J'].width = 12
    
    # Создаем ответ
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
    if group_id and group_id != 'all':
        filename = f'menu_{group.name}_{week_start_date}.xlsx'
    else:
        filename = f'menu_all_groups_{week_start_date}.xlsx'
    
    # Очистка имени файла от недопустимых символов
    import re
    filename = re.sub(r'[^\w.-]', '_', filename)
    filename = filename.replace(' ', '_')
    
    if not filename.endswith('.xlsx'):
        filename += '.xlsx'
    
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    wb.save(response)
    return response

@login_required
@director_required
def create_menu(request):
    """Создание нового пункта меню"""
    if request.method == 'POST':
        form = MenuForm(request.POST)
        if form.is_valid():
            menu = form.save(commit=False)
            menu.created_by = request.user
            menu.save()
            messages.success(request, 'Пункт меню успешно создан!')
            return redirect('nutrition:menu_management')
    else:
        form = MenuForm()
    
    context = {
        'form': form,
        'title': 'Создание пункта меню',
    }
    
    return render(request, 'nutrition/menu_form.html', context)

@login_required
@director_required
def edit_menu(request, menu_id):
    """Редактирование пункта меню"""
    menu = get_object_or_404(Menu, id=menu_id)
    
    if request.method == 'POST':
        form = MenuForm(request.POST, instance=menu)
        if form.is_valid():
            form.save()
            messages.success(request, 'Пункт меню успешно обновлен!')
            return redirect('nutrition:menu_management')
    else:
        form = MenuForm(instance=menu)
    
    context = {
        'form': form,
        'title': 'Редактирование пункта меню',
        'menu': menu,
    }
    
    return render(request, 'nutrition/menu_form.html', context)
