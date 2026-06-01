# contracts/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse, JsonResponse
from django.utils import timezone
from django.core.files.base import ContentFile
from django.urls import reverse
from notifications.models import Notification
from datetime import date
import os

from .models import EducationContract
from .services import ContractWordGenerator
from applications.models import ChildApplication, ApplicationStatus
from payments.models import Tariff
from children.models import Child, ChildParent, PersonalFile


# contracts/views.py

from django.db.models import Sum

@login_required
def my_contracts(request):
    """Список договоров - разные шаблоны для родителя и заведующей"""
    
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile'):
            messages.error(request, 'Профиль родителя не найден')
            return redirect('dashboard')
        
        contracts = EducationContract.objects.filter(
            parent=request.user.parentprofile
        ).order_by('-registration_date')
        
        # Статистика для родителя
        stats = {
            'total': contracts.count(),
            'signed': contracts.filter(parent_signed_at__isnull=False).count(),
            'pending': contracts.filter(parent_signed_at__isnull=True).count(),
        }
        
        # Шаблон для родителя
        template_name = 'contracts/parent_contracts_list.html'
        
    elif request.user.role == 'director':
        contracts = EducationContract.objects.all().order_by('-registration_date')
        
        # Статистика для заведующей
        stats = {
            'total': contracts.count(),
            'signed_by_director': contracts.filter(director_signed_at__isnull=False).count(),
            'signed_by_parent': contracts.filter(parent_signed_at__isnull=False).count(),
            'pending_director': contracts.filter(director_signed_at__isnull=True).count(),
            'pending_parent': contracts.filter(parent_signed_at__isnull=True, director_signed_at__isnull=False).count(),
            'total_amount': contracts.aggregate(total=Sum('parent_fee'))['total'] or 0,
        }
        
        # Шаблон для заведующей
        template_name = 'contracts/director_contracts_list.html'
        
    else:
        messages.error(request, 'Доступ запрещен')
        return redirect('dashboard')
    
    return render(request, template_name, {
        'contracts': contracts,
        'stats': stats,
    })

# contracts/views.py - обновите функцию contract_detail

@login_required
def contract_detail(request, pk):
    """Детальная страница договора с разными шаблонами для разных ролей"""
    contract = get_object_or_404(EducationContract, pk=pk)
    
    # Проверка прав доступа
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile') or contract.parent != request.user.parentprofile:
            messages.error(request, 'У вас нет доступа к этому договору')
            return redirect('dashboard')
        # Шаблон для родителя
        template_name = 'contracts/parent_contract_detail.html'
        
    elif request.user.role == 'director':
        # Шаблон для заведующей
        template_name = 'contracts/director_contract_detail.html'
        
    else:
        messages.error(request, 'Доступ запрещен')
        return redirect('dashboard')
    
    can_sign_parent = False
    if request.user.role == 'parent':
        can_sign_parent = (
            contract.parent_signed_at is None and 
            contract.director_signed_at is not None
        )
    
    return render(request, template_name, {
        'contract': contract,
        'can_sign_parent': can_sign_parent,
    })

@login_required
def generate_contract_word(request, pk):
    """Генерация и скачивание договора в Word"""
    contract = get_object_or_404(EducationContract, pk=pk)
    
    # Проверка прав
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile') or contract.parent != request.user.parentprofile:
            messages.error(request, 'Нет доступа')
            return redirect('dashboard')
    elif request.user.role != 'director':
        messages.error(request, 'Нет доступа')
        return redirect('dashboard')
    
    try:
        generator = ContractWordGenerator(contract)
        document_buffer = generator.generate()
        
        filename = f"Договор_{contract.contract_number}_{contract.child_full_name}.docx".replace(' ', '_')
        
        # Сохраняем в модель
        contract.generated_contract.save(filename, ContentFile(document_buffer.getvalue()))
        contract.save()
        
        # Отдаем на скачивание
        response = HttpResponse(
            document_buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        from urllib.parse import quote
        response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{quote(filename)}'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Ошибка при генерации договора: {str(e)}')
        return redirect('contracts:contract_detail', pk=pk)


@login_required
def download_contract(request, pk):
    """Скачивание договора"""
    contract = get_object_or_404(EducationContract, pk=pk)
    
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile') or contract.parent != request.user.parentprofile:
            messages.error(request, 'Нет доступа')
            return redirect('dashboard')
    elif request.user.role != 'director':
        messages.error(request, 'Нет доступа')
        return redirect('dashboard')
    
    if not contract.generated_contract:
        messages.error(request, 'Договор еще не сгенерирован')
        return redirect('contracts:contract_detail', pk=pk)
    
    try:
        response = FileResponse(
            contract.generated_contract.open(),
            as_attachment=True,
            filename=f"Договор_{contract.contract_number}_{contract.child_full_name}.docx".replace(' ', '_')
        )
        return response
    except Exception as e:
        messages.error(request, f'Ошибка при скачивании: {str(e)}')
        return redirect('contracts:contract_detail', pk=pk)


# contracts/views.py - исправленная функция sign_contract_parent

# contracts/views.py - исправленная функция sign_contract_parent

@login_required
def sign_contract_parent(request, pk):
    """Подписание договора родителем"""
    contract = get_object_or_404(EducationContract, pk=pk)
    
    # Проверка прав: только родитель может подписать свой договор
    if request.user.role != 'parent' or contract.parent.user != request.user:
        messages.error(request, 'У вас нет прав для подписания этого договора')
        return redirect('contracts:contract_list')
    
    if request.method == 'POST':
        try:
            # Отмечаем, что родитель подписал
            contract.parent_signed_at = timezone.now()
            
            # Если заведующая уже подписала, меняем статус на 'active'
            if contract.director_signed_at:
                contract.status = 'active'
            else:
                contract.status = 'signed'
            
            contract.save()
            
            # Создаем уведомление для заведующей
            try:
                from notifications.models import Notification
                from accounts.models import CustomUser
                
                directors = CustomUser.objects.filter(role='director')
                for director in directors:
                    Notification.objects.create(
                        user=director,
                        title="📝 Договор подписан родителем",
                        message=f"Договор №{contract.contract_number} подписан родителем {contract.parent.user.get_full_name()}",
                        notification_type='contract',
                        link=f"/contracts/{contract.id}/"
                    )
            except Exception as e:
                print(f"Ошибка создания уведомления: {e}")
            
            # Обновляем информацию в личном деле ребенка (если есть)
            if contract.child:
                try:
                    # Находим личное дело ребенка
                    personal_file = contract.child.personal_file
                    if personal_file:
                        # Добавляем информацию о договоре (если есть поле для договора)
                        # Если нет поля contract_file, просто обновляем updated_at
                        personal_file.updated_at = timezone.now()
                        personal_file.save()
                        print(f"Личное дело ребенка {contract.child.full_name} обновлено")
                except Exception as e:
                    print(f"Ошибка обновления личного дела: {e}")
            
            messages.success(request, f'Договор №{contract.contract_number} успешно подписан!')
            
            # Перенаправляем на страницу договора
            return redirect('contracts:contract_detail', pk=contract.pk)
            
        except Exception as e:
            messages.error(request, f'Ошибка при подписании договора: {str(e)}')
            return redirect('contracts:contract_detail', pk=contract.pk)
    
    return render(request, 'contracts/sign_contract.html', {'contract': contract})


@login_required
def sign_contract_director(request, pk):
    """
    Подписание договора заведующей
    """
    contract = get_object_or_404(EducationContract, pk=pk)
    
    # Проверка прав - только заведующая
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может подписать договор')
        return redirect('dashboard')
    
    if contract.director_signed_at:
        messages.warning(request, 'Договор уже подписан заведующей')
        return redirect('contracts:contract_detail', pk=pk)
    
    if request.method == 'POST':
        contract.director_signed_at = timezone.now()
        contract.status = 'signed_director'
        contract.save()
        
        # Отправляем уведомление родителю
        try:
            from notifications.models import Notification
            Notification.objects.create(
                user=contract.parent.user,
                title="📄 Договор подписан заведующей",
                message=f"Договор №{contract.contract_number} подписан заведующей. Теперь вы можете подписать его в личном кабинете.",
                notification_type='enrollment',
                link=f"/contracts/{contract.pk}/"
            )
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")
        
        messages.success(request, 'Договор подписан заведующей! Родитель уведомлен.')
        return redirect('contracts:contract_detail', pk=pk)
    
    return redirect('contracts:contract_detail', pk=pk)


@login_required
def contract_edit(request, pk):
    """Редактирование договора (только для заведующей)"""
    if request.user.role != 'director':
        messages.error(request, 'Доступ только для заведующей')
        return redirect('dashboard')
    
    contract = get_object_or_404(EducationContract, pk=pk)
    
    if request.method == 'POST':
        contract.group_name = request.POST.get('group_name', contract.group_name)
        contract.parent_fee = request.POST.get('parent_fee', contract.parent_fee)
        contract.subscription_fee = request.POST.get('subscription_fee', contract.subscription_fee)
        contract.food_fee = request.POST.get('food_fee', contract.food_fee)
        contract.save()
        messages.success(request, 'Договор обновлен')
        return redirect('contracts:contract_detail', pk=pk)
    
    return render(request, 'contracts/contract_edit.html', {'contract': contract})


@login_required
def generate_contract_from_application(request, application_id):
    """Генерация договора из одобренного заявления"""
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if request.user.role != 'director':
        messages.error(request, 'Доступ только для заведующей')
        return redirect('dashboard')
    
    if application.status not in [ApplicationStatus.APPROVED, ApplicationStatus.QUEUE]:
        messages.error(request, 'Договор можно создать только для одобренного заявления')
        return redirect('applications:application_detail', application_id=application.id)
    
    existing_contract = EducationContract.objects.filter(application=application).first()
    if existing_contract:
        messages.warning(request, f'Договор №{existing_contract.contract_number} уже существует')
        return redirect('contracts:contract_detail', pk=existing_contract.pk)
    
    if request.method == 'POST':
        try:
            child_age = application.get_age()
            age_category = 'nursery' if child_age < 3 else 'kindergarten'
            current_year = date.today().year
            tariff = Tariff.objects.filter(age_category=age_category, year=current_year).first()
            
            if tariff:
                content_amount = float(tariff.content_amount)
                food_amount = float(tariff.food_amount)
                total_amount = content_amount + food_amount
            else:
                content_amount = 1684.00
                food_amount = 2503.00
                total_amount = content_amount + food_amount
            
            # Определяем группу
            if child_age < 2:
                group_name = "Первая младшая группа (1-2 года)"
            elif child_age < 3:
                group_name = "Вторая младшая группа (2-3 года)"
            elif child_age < 4:
                group_name = "Младшая группа (3-4 года)"
            elif child_age < 5:
                group_name = "Средняя группа (4-5 лет)"
            elif child_age < 6:
                group_name = "Старшая группа (5-6 лет)"
            else:
                group_name = "Подготовительная группа (6-7 лет)"
            
            contract = EducationContract(
                application=application,
                parent=application.parent,
                child_full_name=application.child_full_name,
                child_birth_date=application.child_birth_date,
                group_name=group_name,
                enrollment_date=date.today(),
                study_period=5,
                stay_regimen='пятидневная неделя (понедельник – пятница), 12 часов (с 6.00 до 18.00)',
                parent_fee=total_amount,
                subscription_fee=content_amount,
                food_fee=food_amount,
                basis_documents=f"На основании заявления родителей",
                educational_program='Основная общеобразовательная программа дошкольного образования',
                status='draft',
                is_active=True
            )
            contract.save()
            
            # Генерируем Word-документ
            generator = ContractWordGenerator(contract)
            document_buffer = generator.generate()
            filename = f"Договор_{contract.contract_number}_{contract.child_full_name}.docx".replace(' ', '_')
            contract.generated_contract.save(filename, ContentFile(document_buffer.getvalue()))
            contract.save()
            
            # ========== ОТПРАВКА УВЕДОМЛЕНИЯ РОДИТЕЛЮ ==========
            try:
                Notification.objects.create(
                    user=application.parent.user,
                    title="📄 Создан договор об образовании",
                    message=f"Для вашего ребенка {application.child_full_name} создан договор №{contract.contract_number}. Пожалуйста, ознакомьтесь и подпишите его в личном кабинете.",
                    notification_type='enrollment',
                    link=f"/contracts/{contract.pk}/"
                )
                print(f"✅ Уведомление отправлено родителю {application.parent.user.email}")
            except Exception as e:
                print(f"Ошибка отправки уведомления: {e}")
            
            messages.success(request, f'Договор №{contract.contract_number} создан! Уведомление отправлено родителю.')
            return redirect('contracts:contract_detail', pk=contract.pk)
            
        except Exception as e:
            messages.error(request, f'Ошибка при создании договора: {str(e)}')
    
    return render(request, 'contracts/generate_contract_form.html', {
        'application': application
    })