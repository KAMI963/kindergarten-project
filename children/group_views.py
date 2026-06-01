from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Group
from .forms import GroupForm

@login_required
def group_list(request):
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может просматривать список групп.')
        return redirect('dashboard')
    
    groups = Group.objects.all().order_by('age_category', 'name')
    
    # Статистика по группам
    group_stats = []
    total_children = 0
    total_free_spaces = 0
    total_percentage = 0
    
    for group in groups:
        group_stats.append({
            'group': group,
            'children_count': group.children_count,
            'fill_percentage': group.fill_percentage,
            'free_spaces': group.free_spaces
        })
        
        total_children += group.children_count
        total_free_spaces += group.free_spaces
        total_percentage += group.fill_percentage
    
    # Вычисляем среднюю заполненность
    avg_fill_percentage = round(total_percentage / len(groups), 1) if groups else 0
    
    # Статистика по возрастным категориям
    age_categories = []
    for category_choice in Group.AGE_CATEGORY_CHOICES:
        category_code, category_name = category_choice
        category_groups = groups.filter(age_category=category_code)
        category_children_count = sum(group.children_count for group in category_groups)
        age_categories.append({
            'name': category_name,
            'count': category_children_count
        })
    
    return render(request, 'children/group_list.html', {
        'groups': groups,
        'group_stats': group_stats,
        'total_children': total_children,
        'total_free_spaces': total_free_spaces,
        'avg_fill_percentage': avg_fill_percentage,
        'age_categories': age_categories
    })

@login_required
def group_create(request):
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может создавать группы.')
        return redirect('children:group_list')
    
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            messages.success(request, f'Группа "{group.name}" успешно создана!')
            return redirect('children:group_list')
    else:
        form = GroupForm()
    
    return render(request, 'children/group_form.html', {
        'form': form,
        'title': 'Создание новой группы',
        'submit_text': 'Создать группу'
    })

@login_required
def group_edit(request, group_id):
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может редактировать группы.')
        return redirect('children:group_list')
    
    group = get_object_or_404(Group, id=group_id)
    
    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f'Группа "{group.name}" успешно обновлена!')
            return redirect('children:group_list')
    else:
        form = GroupForm(instance=group)
    
    return render(request, 'children/group_form.html', {
        'form': form,
        'group': group,
        'title': f'Редактирование группы: {group.name}',
        'submit_text': 'Сохранить изменения'
    })

@login_required
def group_detail(request, group_id):
    if request.user.role not in ['director', 'teacher']:
        messages.error(request, 'У вас нет доступа к просмотру информации о группах.')
        return redirect('dashboard')
    
    group = get_object_or_404(Group, id=group_id)
    children = group.child_set.all().order_by('full_name')
    
    # Добавляем необходимые переменные
    children_count = children.count()
    
    # Подсчет мальчиков и девочек (опционально)
    boys_count = children.filter(gender='male').count()
    girls_count = children.filter(gender='female').count()
    
    return render(request, 'children/group_detail.html', {
        'group': group,
        'children': children,
        'children_count': children_count,  # Добавлено
        'fill_percentage': group.fill_percentage,
        'boys_count': boys_count,  # Добавлено (опционально)
        'girls_count': girls_count,  # Добавлено (опционально)
    })
    
    
