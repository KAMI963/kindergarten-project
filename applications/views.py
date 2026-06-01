from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from datetime import date, datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail
from notifications.models import Notification 
import json
import os

from .models import (
    ChildApplication, ApplicationStatus, BenefitCategory, 
    AgeCategory, QueueHistory, recalc_category_queue_positions,
    auto_reassign_age_categories, process_expired_invitations, QueueSettings
)
from .forms import ChildApplicationForm, ApplicationVerificationForm, QueuePositionChangeForm
from children.models import Child, ChildParent
from accounts.models import ParentProfile


def calculate_child_age(birth_date, reference_date=None):
    """Рассчитывает точный возраст ребенка в годах"""
    if reference_date is None:
        reference_date = date.today()
    age = reference_date.year - birth_date.year
    months_diff = reference_date.month - birth_date.month
    days_diff = reference_date.day - birth_date.day
    
    if months_diff < 0 or (months_diff == 0 and days_diff < 0):
        age -= 1
    
    return age


@login_required
def applications_list(request):
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile'):
            from accounts.models import ParentProfile
            ParentProfile.objects.create(user=request.user)
        
        applications = ChildApplication.objects.filter(parent=request.user.parentprofile)
        stats = {}  # Для родителей статистика не нужна
        
    elif request.user.role == 'director':
        # Получаем все заявления
        applications = ChildApplication.objects.all()
        
        # Подсчет статистики для директора
        stats = {
            'pending': applications.filter(status=ApplicationStatus.PENDING).count(),
            'approved': applications.filter(status=ApplicationStatus.QUEUE).count(),
            'rejected': applications.filter(status=ApplicationStatus.REJECTED).count(),
            'needs_correction': applications.filter(status=ApplicationStatus.RETURNED).count(),
            'enrolled': applications.filter(status=ApplicationStatus.ENROLLED).count(),
            'total': applications.count(),
        }
    else:
        applications = ChildApplication.objects.none()
        stats = {}
        messages.error(request, 'У вас нет доступа к просмотру заявлений.')
    
    # Пагинация - все на одной странице (100 записей)
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    paginator = Paginator(applications, 100)
    page = request.GET.get('page', 1)
    
    try:
        applications_page = paginator.page(page)
    except PageNotAnInteger:
        applications_page = paginator.page(1)
    except EmptyPage:
        applications_page = paginator.page(paginator.num_pages)
    
    return render(request, 'applications/applications_list.html', {
        'applications': applications_page,
        'stats': stats,
        'user': request.user,
    })

@login_required
def application_create(request):
    """Создание нового заявления"""
    if request.user.role != 'parent':
        messages.error(request, 'Только родители могут подавать заявления.')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'parentprofile'):
        ParentProfile.objects.create(user=request.user)
    
    profile = request.user.parentprofile
    
    if request.method == 'POST':
        form = ChildApplicationForm(request.POST, request.FILES, request=request)
        if form.is_valid():
            try:
                application = form.save(commit=False)
                application.parent = request.user.parentprofile
                application.status = 'draft'
                
                sibling_apps = ChildApplication.objects.filter(
                    parent=application.parent,
                    status__in=['enrolled', 'queue']
                ).exclude(id=application.id)
                if sibling_apps.exists():
                    application.sibling_in_kindergarten = True
                    application.sibling_application = sibling_apps.first()
                
                application.age_category = application.calculate_age_category()
                application.save()
                
                messages.success(request, 'Заявление успешно создано!')
                return redirect('applications:application_detail', application_id=application.id)
                
            except Exception as e:
                messages.error(request, f'Ошибка при сохранении заявления: {str(e)}')
        else:
            for field, field_errors in form.errors.items():
                for error in field_errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ChildApplicationForm(request=request)
    
    return render(request, 'applications/application_form.html', {
        'form': form,
        'profile': profile,
        'title': 'Подача заявления'
    })


@login_required
def application_detail(request, application_id):
    """Детальная страница заявления"""
    application = get_object_or_404(ChildApplication, id=application_id)
    
    # Проверка прав доступа
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile'):
            ParentProfile.objects.create(user=request.user)
        if application.parent != request.user.parentprofile:
            messages.error(request, 'У вас нет доступа к этому заявлению.')
            return redirect('dashboard')
    
    # ===== ОТЛАДКА: проверяем документы =====
    print("\n" + "="*60)
    print(f"DEBUG: Проверка документов для заявления #{application.id}")
    print("="*60)
    print(f"Статус заявления: {application.status}")
    print(f"ФИО ребенка: {application.child_full_name}")
    print(f"\n--- Обязательные документы ---")
    print(f"birth_certificate_file: {application.birth_certificate_file}")
    print(f"medical_card: {application.medical_card}")
    print(f"applicant1_passport_file: {application.applicant1_passport_file}")
    print(f"residence_certificate: {application.residence_certificate}")
    print(f"\n--- Результат проверки ---")
    print(f"has_all_required_documents: {application.has_all_required_documents()}")
    print(f"missing documents: {application.get_missing_documents()}")
    print("="*60 + "\n")
    
    # ===== ПРЕОБРАЗУЕМ QUEUE_HISTORY В СПИСОК =====
    application.queue_history_list = list(application.queue_history.all()[:10])
    
    # Рассчитываем позицию в очереди
    queue_position = application.get_queue_position()
    if queue_position:
        application.display_queue_position = queue_position
    elif application.queue_position:
        application.display_queue_position = application.queue_position
    else:
        application.display_queue_position = None
    
    # Генерация документа при POST запросе
    if request.method == 'POST':
        print("\n" + "="*60)
        print("DEBUG: POST запрос в application_detail")
        print(f"POST keys: {list(request.POST.keys())}")
        print("="*60 + "\n")
        
        if 'generate_document' in request.POST or 'regenerate_document' in request.POST:
            print("DEBUG: Генерация документа")
            try:
                from .services import WordDocumentGenerator
                generator = WordDocumentGenerator(application)
                file_path = generator.fill_application_template()
                
                if hasattr(application, 'generated_application'):
                    application.generated_application.name = file_path
                    application.save()
                
                messages.success(request, 'Заявление успешно сгенерировано!')
            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Ошибка при генерации документа: {str(e)}')
        
        elif 'submit_for_review' in request.POST:
            print("DEBUG: Нажата кнопка 'submit_for_review'")
            print(f"Текущий статус: {application.status}")
            print(f"application.status == 'draft': {application.status == 'draft'}")
            print(f"application.status == ApplicationStatus.DRAFT: {application.status == ApplicationStatus.DRAFT}")
            
            # Проверяем, что заявление в статусе черновика
            if application.status == ApplicationStatus.DRAFT or application.status == 'draft':
                missing_docs = application.get_missing_documents()
                print(f"Недостающие документы: {missing_docs}")
                
                if len(missing_docs) == 0 or (len(missing_docs) == 4 and all('необязательно' in doc for doc in missing_docs)):
                    print("DEBUG: Все обязательные документы на месте, меняем статус на PENDING")
                    application.status = ApplicationStatus.PENDING
                    application.submission_date = timezone.now()
                    application.save(update_fields=['status', 'submission_date'])
                    
                    print(f"Новый статус: {application.status}")
                    
                    # Создаем уведомление для заведующей
                    try:
                        from notifications.models import Notification
                        from accounts.models import CustomUser
                        
                        directors = CustomUser.objects.filter(role='director')
                        for director in directors:
                            Notification.objects.create(
                                user=director,
                                title="📝 Новое заявление на проверку",
                                message=f"Поступило новое заявление от {application.parent.user.get_full_name() or application.parent.user.username} для ребенка {application.child_full_name}",
                                notification_type='application',
                                link=f"/applications/{application.id}/"
                            )
                        print("DEBUG: Уведомления отправлены заведующим")
                    except Exception as e:
                        print(f"Ошибка создания уведомления: {e}")
                    
                    messages.success(request, 'Заявление отправлено на проверку!')
                else:
                    print(f"DEBUG: ОТКАЗ - недостающие обязательные документы: {missing_docs}")
                    messages.warning(
                        request, 
                        f'Для отправки заявления необходимо загрузить следующие документы: {", ".join([d for d in missing_docs if "необязательно" not in d])}'
                    )
            else:
                print(f"DEBUG: Некорректный статус для отправки: {application.status}")
                messages.warning(request, f'Заявление нельзя отправить (текущий статус: {application.get_status_display()})')
        
        elif 'cancel_submit' in request.POST:
            print("DEBUG: Отмена отправки заявления")
            if application.status == ApplicationStatus.PENDING or application.status == 'pending':
                application.status = ApplicationStatus.DRAFT
                application.save(update_fields=['status'])
                messages.success(request, 'Отправка заявления отменена. Вы можете продолжить редактирование.')
            else:
                messages.warning(request, 'Невозможно отменить отправку для этого статуса')
        
        return redirect('applications:application_detail', application_id=application.id)
    
    # AJAX запрос для получения данных
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        data = {
            'id': application.id,
            'child_full_name': application.child_full_name,
            'child_birth_date': application.child_birth_date.strftime('%d.%m.%Y'),
            'child_gender': application.get_child_gender_display() if hasattr(application, 'get_child_gender_display') else application.child_gender,
            'child_snils': getattr(application, 'child_snils', ''),
            'registration_address': application.registration_address,
            'actual_address': application.actual_address,
            'applicant1_full_name': application.applicant1_full_name,
            'applicant1_phone': application.applicant1_phone,
            'applicant2_full_name': application.applicant2_full_name,
            'applicant2_phone': application.applicant2_phone,
            'phone_number': application.phone_number,
            'email': application.email,
            'status': application.status,
            'status_display': application.get_status_display_verbose(),
            'queue_position': application.display_queue_position,
            'generated_application': application.generated_application.url if application.generated_application else None,
            'has_all_documents': application.has_all_required_documents(),
            'missing_documents': application.get_missing_documents(),
            'benefit_category': application.benefit_category,
            'benefit_display': application.get_benefit_category_display() if hasattr(application, 'get_benefit_category_display') else '',
            'created_at': application.created_at.strftime('%d.%m.%Y %H:%M'),
        }
        
        # Добавляем URL-ы документов
        documents = {
            'birth_certificate': application.birth_certificate_file.url if application.birth_certificate_file else None,
            'medical_card': application.medical_card.url if application.medical_card else None,
            'passport': application.applicant1_passport_file.url if application.applicant1_passport_file else None,
            'residence': application.residence_certificate.url if application.residence_certificate else None,
            'child_snils': application.child_snils_file.url if application.child_snils_file else None,
            'vaccination': application.vaccination_certificate_file.url if application.vaccination_certificate_file else None,
            'insurance': application.insurance_policy_file.url if application.insurance_policy_file else None,
            'medical_card_a4': application.medical_card_a4_file.url if application.medical_card_a4_file else None,
            'benefit': (application.benefit_document_right or application.benefit_document).url if (application.benefit_document_right or application.benefit_document) else None,
        }
        data['documents'] = documents
        
        return JsonResponse(data)
    
    # Собираем информацию о документах для отображения в шаблоне
    documents_info = {
        'birth_certificate': {
            'exists': bool(application.birth_certificate_file),
            'url': application.birth_certificate_file.url if application.birth_certificate_file else None,
            'name': 'Свидетельство о рождении',
            'required': True,
            'icon': 'fas fa-certificate'
        },
        'medical_card': {
            'exists': bool(application.medical_card),
            'url': application.medical_card.url if application.medical_card else None,
            'name': 'Медицинская карта',
            'required': True,
            'icon': 'fas fa-notes-medical'
        },
        'passport': {
            'exists': bool(application.applicant1_passport_file),
            'url': application.applicant1_passport_file.url if application.applicant1_passport_file else None,
            'name': 'Паспорт заявителя',
            'required': True,
            'icon': 'fas fa-id-card'
        },
        'residence': {
            'exists': bool(application.residence_certificate),
            'url': application.residence_certificate.url if application.residence_certificate else None,
            'name': 'Подтверждение места жительства',
            'required': True,
            'icon': 'fas fa-home'
        },
        'child_snils': {
            'exists': bool(application.child_snils_file),
            'url': application.child_snils_file.url if application.child_snils_file else None,
            'name': 'СНИЛС ребенка',
            'required': False,
            'icon': 'fas fa-id-card'
        },
        'vaccination': {
            'exists': bool(application.vaccination_certificate_file),
            'url': application.vaccination_certificate_file.url if application.vaccination_certificate_file else None,
            'name': 'Сертификат о прививках (№063/у)',
            'required': False,
            'icon': 'fas fa-syringe'
        },
        'insurance': {
            'exists': bool(application.insurance_policy_file),
            'url': application.insurance_policy_file.url if application.insurance_policy_file else None,
            'name': 'Полис медицинского страхования',
            'required': False,
            'icon': 'fas fa-file-medical'
        },
        'medical_card_a4': {
            'exists': bool(application.medical_card_a4_file),
            'url': application.medical_card_a4_file.url if application.medical_card_a4_file else None,
            'name': 'Медицинская карта (форма №026/у) А4',
            'required': False,
            'icon': 'fas fa-file-alt'
        },
        'benefit_document': {
            'exists': bool(application.benefit_document_right or application.benefit_document),
            'url': (application.benefit_document_right or application.benefit_document).url if (application.benefit_document_right or application.benefit_document) else None,
            'name': 'Документ о льготе',
            'required': application.benefit_category != 'none',
            'icon': 'fas fa-star-of-life'
        }
    }
    
    # Получаем только обязательные недостающие документы
    all_missing = application.get_missing_documents()
    required_missing = [d for d in all_missing if 'необязательно' not in d]
    
    return render(request, 'applications/application_detail.html', {
        'application': application,
        'documents_info': documents_info,
        'missing_documents': required_missing,
        'has_all_documents': len(required_missing) == 0,
        'all_missing_documents': all_missing,
    })


@login_required
def application_edit(request, application_id):
    """Редактирование заявления"""
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if request.user.role != 'parent':
        messages.error(request, 'Только родители могут редактировать заявления.')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'parentprofile'):
        ParentProfile.objects.create(user=request.user)
    
    if application.parent != request.user.parentprofile:
        messages.error(request, 'У вас нет доступа к этому заявлению.')
        return redirect('dashboard')
    
    if application.status not in [ApplicationStatus.DRAFT, ApplicationStatus.PENDING, ApplicationStatus.RETURNED]:
        messages.error(request, 'Это заявление нельзя редактировать.')
        return redirect('applications:application_detail', application_id=application_id)
    
    if request.method == 'POST':
        form = ChildApplicationForm(request.POST, request.FILES, instance=application, request=request)
        if form.is_valid():
            try:
                updated_application = form.save(commit=False)
                
                if updated_application.status == ApplicationStatus.RETURNED:
                    updated_application.status = ApplicationStatus.PENDING
                    updated_application.documents_verified = False
                    updated_application.returned_reason = ''
                elif updated_application.status == ApplicationStatus.PENDING:
                    updated_application.status = ApplicationStatus.DRAFT
                    updated_application.documents_verified = False
                
                updated_application.age_category = updated_application.calculate_age_category()
                updated_application.save()
                messages.success(request, 'Заявление успешно отредактировано!')
                return redirect('applications:application_detail', application_id=application_id)
            except Exception as e:
                messages.error(request, f'Ошибка при сохранении: {str(e)}')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = ChildApplicationForm(instance=application, request=request)
    
    return render(request, 'applications/application_edit.html', {
        'form': form,
        'application': application,
        'title': 'Редактирование заявления'
    })


@login_required
def generate_application_document(request, application_id):
    """Генерация заявления в формате DOCX"""
    application = get_object_or_404(ChildApplication, id=application_id)
    
    # Проверка доступа
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile'):
            messages.error(request, 'Профиль не найден.')
            return redirect('dashboard')
        if application.parent != request.user.parentprofile:
            messages.error(request, 'Нет доступа.')
            return redirect('dashboard')
    elif request.user.role != 'director':
        messages.error(request, 'Нет доступа.')
        return redirect('dashboard')
    
    try:
        from docx import Document
        from docx.shared import Pt
        import os
        from datetime import datetime
        from django.core.files import File
        
        # Путь к шаблону
        template_path = os.path.join(settings.BASE_DIR, 'templates', 'applications', 'Заявление.docx')
        
        if not os.path.exists(template_path):
            messages.error(request, f'Шаблон не найден: {template_path}')
            return redirect('applications:application_detail', application_id=application.id)
        
        # Открываем шаблон
        doc = Document(template_path)
        
        # ===== ФУНКЦИЯ ДЛЯ СКЛОНЕНИЯ ФИО =====
        def decline_full_name(full_name, case='accusative'):
            """Склонение ФИО в русском языке."""
            if not full_name or ' ' not in full_name:
                return full_name
            
            parts = full_name.strip().split()
            if len(parts) < 3:
                return full_name
            
            last_name = parts[0]
            first_name = parts[1]
            patronymic = parts[2]
            
            if case == 'accusative':
                if last_name.endswith(('а', 'я')):
                    last_name = last_name[:-1] + 'у'
                elif last_name.endswith(('ий', 'ый', 'ой')):
                    last_name = last_name[:-2] + 'ого'
                elif last_name.endswith(('ов', 'ев', 'ин', 'ын')):
                    last_name = last_name + 'а'
                
                if first_name.endswith('я'):
                    first_name = first_name[:-1] + 'ю'
                elif first_name.endswith('а'):
                    first_name = first_name[:-1] + 'у'
                elif first_name.endswith('ий'):
                    first_name = first_name[:-2] + 'ия'
                
                if patronymic.endswith('на'):
                    patronymic = patronymic[:-2] + 'ну'
                elif patronymic.endswith('вич'):
                    patronymic = patronymic[:-2] + 'ича'
            
            return f"{last_name} {first_name} {patronymic}"
        
        # Склоняем ФИО ребенка
        child_name_accusative = decline_full_name(application.child_full_name, 'accusative')
        
        # Определяем ФИО родителя (заявителя)
        parent_name = application.applicant1_full_name or application.applicant2_full_name or application.parent.user.get_full_name() or '______________'
        parent_phone = application.applicant1_phone or application.applicant2_phone or application.phone_number or '______________'
        
        # Словарь замен
        replacements = {
            '{{ФИО_родителя}}': parent_name,
            '{{ФИО_ребенка}}': child_name_accusative,
            '{{ФИО_ребенка_именительный}}': application.child_full_name,
            '{{дата_рождения_ребенка}}': application.child_birth_date.strftime("%d.%m.%Y"),
            '{{адрес_регистрации}}': application.registration_address or '______________',
            '{{фактический_адрес_проживания}}': application.actual_address or application.registration_address or '______________',
            '{{серия_свидетельства}}': application.birth_certificate_series or '______________',
            '{{номер_свидетельства}}': application.birth_certificate_number or '______________',
            '{{выдано}}': application.birth_certificate_issued_by or '______________',
            '{{ФИО_матери}}': application.applicant1_full_name if application.applicant1_full_name else parent_name,
            '{{номер_телефона}}': parent_phone,
            '{{ФИО_отца}}': application.applicant2_full_name or '______________',
            '{{дата}}': datetime.now().strftime("%d.%m.%Y")
        }
        
        # Заменяем текст во всех параграфах
        for paragraph in doc.paragraphs:
            original_text = paragraph.text
            new_text = original_text
            for key, value in replacements.items():
                if key in new_text:
                    new_text = new_text.replace(key, value)
            
            if new_text != original_text:
                alignment = paragraph.paragraph_format.alignment
                paragraph.clear()
                new_run = paragraph.add_run(new_text)
                new_run.font.name = 'Times New Roman'
                new_run.font.size = Pt(12)
                if alignment:
                    paragraph.paragraph_format.alignment = alignment
        
        # Заменяем текст в таблицах
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        original_text = paragraph.text
                        new_text = original_text
                        for key, value in replacements.items():
                            if key in new_text:
                                new_text = new_text.replace(key, value)
                        
                        if new_text != original_text:
                            alignment = paragraph.paragraph_format.alignment
                            paragraph.clear()
                            new_run = paragraph.add_run(new_text)
                            new_run.font.name = 'Times New Roman'
                            new_run.font.size = Pt(12)
                            if alignment:
                                paragraph.paragraph_format.alignment = alignment
        
        # Сохраняем файл
        child_name = application.child_full_name.replace(' ', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Заявление_на_зачисление_{child_name}_{timestamp}.docx"
        
        save_dir = os.path.join(settings.MEDIA_ROOT, 'applications', 'generated')
        os.makedirs(save_dir, exist_ok=True)
        
        file_path = os.path.join(save_dir, filename)
        doc.save(file_path)
        
        # Удаляем старый файл если есть
        if application.generated_application:
            try:
                old_path = application.generated_application.path
                if os.path.exists(old_path):
                    os.remove(old_path)
            except:
                pass
        
        # Сохраняем в модель
        with open(file_path, 'rb') as f:
            application.generated_application.save(filename, File(f))
            application.save()
        
        messages.success(request, f'✅ Заявление успешно сформировано!')
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f'❌ Ошибка: {str(e)}')
    
    return redirect('applications:application_detail', application_id=application.id)


@login_required
def download_application(request, application_id):
    """Скачивание сгенерированного заявления"""
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if not application.generated_application:
        messages.error(request, 'Документ еще не сгенерирован.')
        return redirect('applications:application_detail', application_id=application_id)
    
    if request.user.role == 'parent' and application.parent != request.user.parentprofile:
        messages.error(request, 'У вас нет доступа к этому документу.')
        return redirect('dashboard')
    
    file_path = application.generated_application.path
    if os.path.exists(file_path):
        if file_path.endswith('.docx'):
            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            content_type = 'application/octet-stream'
        
        child_name = application.child_full_name.replace(' ', '_')
        download_filename = f"Заявление_на_зачисление_{child_name}.docx"
        
        from urllib.parse import quote
        
        response = HttpResponse(open(file_path, 'rb').read(), content_type=content_type)
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(download_filename)}"
        
        return response
    else:
        messages.error(request, 'Файл не найден.')
        return redirect('applications:application_detail', application_id=application_id)


@login_required
def application_approve(request, application_id):
    """Одобрение заявления"""
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может одобрять заявления.')
        return redirect('dashboard')
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.status != ApplicationStatus.PENDING:
        messages.error(request, 'Это заявление уже обработано.')
        return redirect('applications:application_detail', application_id=application_id)
    
    try:
        if not application.has_all_required_documents():
            missing = application.get_missing_documents()
            messages.warning(
                request,
                f'Отсутствуют документы: {", ".join(missing)}. Заявление отправлено на доработку.'
            )
            ChildApplication.objects.filter(pk=application.pk).update(
                status=ApplicationStatus.RETURNED,
                returned_reason=f'Отсутствуют документы: {", ".join(missing)}'
            )
        else:
            priority = application.calculate_priority_score()
            age_category = application.age_category or application.calculate_age_category()
            
            # Обновляем статус
            ChildApplication.objects.filter(pk=application.pk).update(
                status=ApplicationStatus.QUEUE,
                queue_priority=priority,
                age_category=age_category,
            )
            
            if age_category:
                recalc_category_queue_positions(age_category)
            
            application.refresh_from_db()
            position = application.get_queue_position()
            
            messages.success(
                request,
                f'Заявление одобрено и поставлено в очередь (позиция {position}).'
            )
            
            # ========== ПРИНУДИТЕЛЬНОЕ СОЗДАНИЕ ДОГОВОРА ==========
            try:
                from contracts.models import EducationContract
                from payments.models import Tariff
                
                # Проверяем, нет ли уже договора
                existing_contract = EducationContract.objects.filter(application=application).first()
                if not existing_contract:
                    print(f"\n📝 ПРИНУДИТЕЛЬНОЕ СОЗДАНИЕ ДОГОВОРА для {application.child_full_name}")
                    
                    # Получаем возраст ребенка
                    child_age = application.get_age()
                    age_category_tariff = 'nursery' if child_age < 3 else 'kindergarten'
                    current_year = date.today().year
                    tariff = Tariff.objects.filter(age_category=age_category_tariff, year=current_year).first()
                    
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
                    
                    # Создаем договор
                    contract = EducationContract(
                        application=application,
                        parent=application.parent,
                        child_full_name=application.child_full_name,
                        child_birth_date=application.child_birth_date,
                        child_gender=application.child_gender,
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
                    
                    print(f"   ✅ ДОГОВОР СОЗДАН! Номер: {contract.contract_number}")
                    
                    # Генерируем Word-документ
                    try:
                        from contracts.services import ContractWordGenerator
                        from django.core.files.base import ContentFile
                        generator = ContractWordGenerator(contract)
                        document_buffer = generator.generate()
                        filename = f"Договор_{contract.contract_number}_{contract.child_full_name}.docx".replace(' ', '_')
                        contract.generated_contract.save(filename, ContentFile(document_buffer.getvalue()))
                        contract.save()
                        print(f"   ✅ Документ сгенерирован")
                        messages.info(request, f'Договор №{contract.contract_number} автоматически создан!')
                    except Exception as e:
                        print(f"   ⚠️ Ошибка генерации документа: {e}")
                else:
                    print(f"   ℹ️ Договор уже существует: {existing_contract.contract_number}")
            except Exception as e:
                print(f"   ❌ Ошибка создания договора: {e}")
                import traceback
                traceback.print_exc()
            
            # Приглашаем, если есть свободные места
            from .queue_logic import auto_invite_from_queue
            invited = auto_invite_from_queue(age_category)
            if invited > 0:
                messages.info(request, f'📧 Приглашения отправлены {invited} родителям.')
        
        return redirect('applications:application_detail', application_id=application_id)
        
    except Exception as e:
        messages.error(request, f'Ошибка при одобрении заявления: {str(e)}')
        return redirect('applications:application_detail', application_id=application_id)


@login_required
def application_reject(request, application_id):
    """Отклонение заявления"""
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может отклонять заявления.')
        return redirect('dashboard')
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if request.method == 'POST':
        data = json.loads(request.body) if request.headers.get('Content-Type') == 'application/json' else request.POST
        rejection_reason = data.get('rejection_reason', '')
        
        application.reject(rejection_reason)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Заявление отклонено'})
        
        messages.success(request, 'Заявление отклонено.')
        return redirect('applications:application_detail', application_id=application_id)
    
    return render(request, 'applications/application_reject.html', {
        'application': application
    })


@login_required
def application_need_correction(request, application_id):
    """Запрос корректировки заявления"""
    if request.user.role != 'director':
        messages.error(request, 'Только заведующая может запрашивать корректировки.')
        return redirect('dashboard')
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if request.method == 'POST':
        correction_notes = request.POST.get('correction_notes', '')
        application.return_for_revision(correction_notes)
        messages.success(request, 'Заявлению требуется корректировка. Родитель уведомлён.')
        return redirect('applications:application_detail', application_id=application_id)
    
    return render(request, 'applications/application_correction.html', {
        'application': application
    })


@login_required
def return_for_revision(request, application_id):
    """Вернуть заявление на доработку (AJAX)"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        reason = data.get('reason', '')
        
        application.return_for_revision(reason)
        
        return JsonResponse({'success': True, 'message': 'Заявление возвращено на доработку'})


@login_required
def sync_from_profile(request):
    """AJAX синхронизация данных из профиля родителя"""
    if request.user.role != 'parent':
        return JsonResponse({'success': False, 'error': 'Доступ только для родителей'})
    
    if not hasattr(request.user, 'parentprofile'):
        return JsonResponse({'success': False, 'error': 'Профиль не найден'})
    
    profile = request.user.parentprofile
    
    data = {
        'success': True,
        'phone_number': profile.mobile_phone,
        'email': request.user.email,
        'registration_address': profile.registration_address,
        'actual_address': profile.actual_address or profile.registration_address,
    }
    
    if profile.full_name:
        if profile.full_name.endswith(('а', 'я', 'ва', 'на', 'ия')):
            data['mother_full_name'] = profile.full_name
            data['mother_phone'] = profile.mobile_phone
        else:
            data['father_full_name'] = profile.full_name
            data['father_phone'] = profile.mobile_phone
    
    return JsonResponse(data)


# ==================== ЭЛЕКТРОННАЯ ОЧЕРЕДЬ ====================

@login_required
def parent_queue_status(request):
    """Личный кабинет родителя: просмотр своей позиции в очереди"""
    if request.user.role != 'parent':
        messages.error(request, 'Только для родителей')
        return redirect('dashboard')
    
    if not hasattr(request.user, 'parentprofile'):
        ParentProfile.objects.create(user=request.user)
    
    # Получаем все заявления родителя
    applications = ChildApplication.objects.filter(
        parent=request.user.parentprofile
    ).order_by('-created_at')
    
    # Для каждого заявления получаем историю очереди
    for app in applications:
        app.history = app.queue_history.all()[:15]
        app.current_position = app.get_queue_position()
        years, months = app.get_age_detailed()
        app.years = years
        app.months = months
    
    return render(request, 'applications/parent_queue.html', {
        'applications': applications
    })


@login_required
def director_queue_admin(request):
    """Административная панель очереди для заведующей"""
    if request.user.role != 'director':
        messages.error(request, 'Доступ только для заведующей')
        return redirect('dashboard')
    
    # Автоматическое приглашение
    from .queue_logic import auto_invite_from_queue
    invited = auto_invite_from_queue()
    if invited > 0:
        messages.success(request, f'✅ Автоматически приглашено {invited} заявителей!')
    
    # Получаем параметры фильтрации
    status_filter = request.GET.get('status', '')
    benefit_filter = request.GET.get('benefit', '')
    age_filter = request.GET.get('age_category', '')
    search = request.GET.get('search', '')
    
    # Базовый запрос
    applications = ChildApplication.objects.select_related('parent__user').all()
    
    # Применяем фильтры
    if status_filter:
        applications = applications.filter(status=status_filter)
    if benefit_filter:
        applications = applications.filter(benefit_category=benefit_filter)
    if age_filter:
        applications = applications.filter(age_category=age_filter)
    if search:
        applications = applications.filter(
            Q(child_full_name__icontains=search) |
            Q(parent__user__last_name__icontains=search) |
            Q(parent__user__first_name__icontains=search)
        )
    
    # ========== ГЛАВНОЕ: ПРАВИЛЬНАЯ СОРТИРОВКА И РАСЧЕТ ПОЗИЦИЙ ==========
    
    # Разделяем на два потока:
    # 1. Льготники (extraordinary, priority, preferential)
    # 2. Общая очередь (none)
    
    benefit_apps = []
    general_apps = []
    
    for app in applications:
        if app.benefit_category in ['extraordinary', 'priority', 'preferential']:
            benefit_apps.append(app)
        else:
            general_apps.append(app)
    
    # Сортируем льготников по приоритету и дате
    benefit_apps.sort(key=lambda x: (
        0 if x.benefit_category == 'extraordinary' else
        1 if x.benefit_category == 'priority' else
        2 if x.benefit_category == 'preferential' else 3,
        x.created_at
    ))
    
    # Сортируем общую очередь строго по дате подачи
    general_apps.sort(key=lambda x: x.created_at)
    
    # Объединяем и присваиваем позиции
    all_apps = benefit_apps + general_apps
    
    for index, app in enumerate(all_apps, 1):
        app.display_position = index
        app.stream_group = 'benefit' if app.benefit_category != 'none' else 'general'
        
        # Определяем, попадает ли в гарантированный набор (первые N мест)
        # N = количество свободных мест в категории
        free_places = 0
        if app.age_category:
            settings = QueueSettings.objects.filter(age_category=app.age_category).first()
            if settings:
                free_places = settings.get_free_places()
        
        app.is_guaranteed = (index <= free_places) and app.status == 'queue'
        app.is_borderline = (index > free_places and index <= free_places + 3) and app.status == 'queue'
        
        # Добавляем информацию о движении за неделю
        one_week_ago = timezone.now() - timedelta(days=7)
        old_history = app.queue_history.filter(changed_at__gte=one_week_ago).first()
        
        if old_history and old_history.old_position:
            change = old_history.old_position - index
            if change > 0:
                app.movement = {
                    'type': 'up',
                    'description': f'Поднялся на {change} место',
                    'change_display': f'+{change}'
                }
            elif change < 0:
                app.movement = {
                    'type': 'down',
                    'description': f'Опустился на {abs(change)} место',
                    'change_display': f'{change}'
                }
            else:
                app.movement = {
                    'type': 'stable',
                    'description': 'Позиция не изменилась',
                    'change_display': '0'
                }
        else:
            app.movement = {
                'type': 'stable',
                'description': 'Нет данных',
                'change_display': '0'
            }
    
    # Пагинация
    paginator = Paginator(all_apps, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Статистика по возрастным категориям
    age_stats = {}
    for age_cat in AgeCategory.choices:
        age_cat_code, age_cat_name = age_cat
        queue_count = ChildApplication.objects.filter(
            status__in=['queue', 'invited', 'processing'],
            age_category=age_cat_code
        ).count()
        
        settings = QueueSettings.objects.filter(age_category=age_cat_code).first()
        capacity = settings.capacity if settings else 20
        enrolled = settings.current_enrolled if settings else 0
        
        age_stats[age_cat_code] = {
            'name': age_cat_name,
            'queue': queue_count,
            'capacity': capacity,
            'enrolled': enrolled,
            'free_places': max(0, capacity - enrolled)
        }
    
    stats = {
        'queue': ChildApplication.objects.filter(status='queue').count(),
        'pending': ChildApplication.objects.filter(status='pending').count(),
        'invited': ChildApplication.objects.filter(status='invited').count(),
        'enrolled': ChildApplication.objects.filter(status='enrolled').count(),
        'age_stats': age_stats,
    }
    
    return render(request, 'queue/queue_management.html', {
        'applications': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'benefit_filter': benefit_filter,
        'age_filter': age_filter,
        'search': search,
    })


def export_queue_to_excel(applications):
    """Экспорт очереди в Excel"""
    import pandas as pd
    from io import BytesIO
    from urllib.parse import quote
    
    data = []
    for app in applications:
        data.append({
            'ID': app.id,
            'ФИО ребенка': app.child_full_name,
            'Дата рождения': app.child_birth_date.strftime('%d.%m.%Y') if app.child_birth_date else '',
            'Возраст': app.get_age(),
            'Родитель': app.parent.user.get_full_name() if app.parent.user else '',
            'Телефон': getattr(app.parent.user, 'phone', ''),
            'Дата подачи': app.created_at.strftime('%d.%m.%Y'),
            'Статус': app.get_status_display_verbose(),
            'Категория льготы': app.get_benefit_category_display(),
            'Баллы приоритета': app.queue_priority,
            'Позиция в очереди': app.get_queue_position() or '-',
            'Возрастная категория': app.get_age_category_display() or '-',
            'Брат/сестра в саду': 'Да' if app.sibling_in_kindergarten else 'Нет',
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Очередь', index=False)
    
    output.seek(0)
    
    filename = f'queue_export_{date.today().strftime("%Y%m%d")}.xlsx'
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{quote(filename)}'
    
    return response


@login_required
def verify_application_documents(request, application_id):
    """Проверка документов заявления (заведующая)"""
    if request.user.role != 'director':
        messages.error(request, 'Доступ только для заведующей')
        return redirect('dashboard')
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if request.method == 'POST':
        if request.headers.get('Content-Type') == 'application/json':
            data = json.loads(request.body)
            application.documents_verified = data.get('documents_verified', False)
            application.verification_comment = data.get('verification_comment', '')
            new_status = data.get('status', '')
            
            if new_status == 'queue':
                application.status = ApplicationStatus.QUEUE
                application.queue_priority = application.calculate_priority_score()
                application.save()
                recalc_category_queue_positions(application.age_category)
            elif new_status == 'rejected':
                application.status = ApplicationStatus.REJECTED
                application.save()
            elif new_status == 'returned':
                application.return_for_revision(data.get('comment', ''))
            else:
                application.status = ApplicationStatus.PENDING
                application.save()
            
            return JsonResponse({'success': True})
        else:
            form = ApplicationVerificationForm(request.POST)
            if form.is_valid():
                application.documents_verified = form.cleaned_data['documents_verified']
                application.verification_comment = form.cleaned_data['verification_comment']
                new_status = form.cleaned_data['status']
                
                if new_status == 'queue':
                    application.status = ApplicationStatus.QUEUE
                    application.queue_priority = application.calculate_priority_score()
                    application.save()
                    recalc_category_queue_positions(application.age_category)
                    messages.success(request, f'Заявление поставлено в очередь (позиция {application.get_queue_position()})')
                elif new_status == 'rejected':
                    application.status = ApplicationStatus.REJECTED
                    application.save()
                    messages.warning(request, 'Заявление отклонено')
                else:
                    application.status = ApplicationStatus.PENDING
                    application.save()
                    messages.info(request, 'Заявление оставлено на проверке')
                
                return redirect('applications:director_queue')
    
    # GET запрос - возвращаем форму для AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = f'''
        <form id="verifyForm">
            <div class="mb-3">
                <label class="form-label">Документы проверены</label>
                <input type="checkbox" name="documents_verified" class="form-check-input" {'checked' if application.documents_verified else ''}>
            </div>
            <div class="mb-3">
                <label class="form-label">Примечание</label>
                <textarea name="verification_comment" class="form-control" rows="3">{application.verification_comment}</textarea>
            </div>
            <div class="mb-3">
                <label class="form-label">Новый статус</label>
                <select name="status" class="form-select" id="verifyStatusSelect">
                    <option value="pending">На проверке</option>
                    <option value="queue">В очередь</option>
                    <option value="rejected">Отказать</option>
                    <option value="returned">Вернуть на доработку</option>
                </select>
            </div>
            <div class="mb-3" id="returnReasonDiv" style="display:none;">
                <label class="form-label">Причина возврата</label>
                <textarea name="comment" class="form-control" rows="2"></textarea>
            </div>
        </form>
        <script>
            document.getElementById('verifyStatusSelect').addEventListener('change', function() {{
                document.getElementById('returnReasonDiv').style.display = this.value === 'returned' ? 'block' : 'none';
            }});
        </script>
        '''
        return JsonResponse({'html': html})
    
    # Список документов для отображения
    documents = [
        {'name': 'Свидетельство о рождении', 'file': application.birth_certificate_file, 'required': True},
        {'name': 'Медицинская карта', 'file': application.medical_card, 'required': True},
        {'name': 'Паспорт родителя', 'file': application.passport_file or application.parent_passport_file, 'required': True},
        {'name': 'Подтверждение места жительства', 'file': application.residence_certificate or application.residence_proof_file, 'required': True},
        {'name': 'Документ о льготе', 'file': application.benefit_document_right or application.benefit_document, 'required': False},
        {'name': 'Медицинская справка (оздоровительная группа)', 'file': application.health_certificate_oz or application.health_certificate, 'required': False},
        {'name': 'Заключение ПМПК', 'file': application.pmpk_conclusion or application.pmpk_file, 'required': False},
    ]
    
    return render(request, 'applications/verify_documents.html', {
        'application': application,
        'documents': documents
    })


@login_required
def invite_to_enrollment(request, application_id):
    """Пригласить на оформление (заведующая)"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Доступ только для заведующей'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.status != ApplicationStatus.QUEUE:
        return JsonResponse({'success': False, 'error': 'Пригласить можно только заявление, находящееся в очереди'}, status=400)
    
    if request.method == 'POST':
        application.invite_to_enrollment()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'Родитель {application.parent.user.get_full_name()} приглашён на оформление'})
        
        messages.success(request, f'Родитель {application.parent.user.get_full_name()} приглашён на оформление')
        return redirect('applications:director_queue')
    
    return render(request, 'applications/invite_enrollment.html', {
        'application': application
    })


@login_required
def change_queue_position(request, application_id):
    """Ручное изменение позиции в очереди (заведующая)"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Доступ только для заведующей'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.status != ApplicationStatus.QUEUE:
        return JsonResponse({'success': False, 'error': 'Изменить позицию можно только для заявлений в очереди'}, status=400)
    
    if request.method == 'POST':
        if request.headers.get('Content-Type') == 'application/json':
            data = json.loads(request.body)
            new_pos = data.get('new_position')
            comment = data.get('comment', '')
        else:
            new_pos = request.POST.get('new_position')
            comment = request.POST.get('comment', '')
        
        if new_pos:
            new_pos = int(new_pos)
            old_pos = application.queue_position
            
            # Сохраняем старую позицию для истории
            old_position = old_pos
            
            # Получаем все заявления в этой категории
            category_apps = list(ChildApplication.objects.filter(
                status=ApplicationStatus.QUEUE,
                age_category=application.age_category
            ).order_by('-queue_priority', 'created_at'))
            
            # Удаляем текущее заявление из списка
            current_index = category_apps.index(application)
            category_apps.pop(current_index)
            
            # Вставляем на новую позицию
            category_apps.insert(new_pos - 1, application)
            
            # Обновляем позиции
            for idx, app in enumerate(category_apps, 1):
                app.queue_position = idx
                app.save(update_fields=['queue_position'])
                
                QueueHistory.objects.create(
                    application=app,
                    old_position=old_position if app == application else app.queue_position,
                    new_position=idx,
                    new_priority=app.queue_priority,
                    age_category=application.age_category,
                    reason='Изменено заведующей',
                    comment=comment if app == application else ''
                )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Позиция изменена с {old_pos} на {new_pos}'})
            
            messages.success(request, f'Позиция изменена с {old_pos} на {new_pos}')
            return redirect('applications:director_queue')
    
    # GET запрос - форма для изменения позиции
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = f'''
        <form id="positionForm">
            <div class="mb-3">
                <label class="form-label">Текущая позиция</label>
                <input type="text" class="form-control" value="{application.queue_position}" disabled>
            </div>
            <div class="mb-3">
                <label class="form-label">Новая позиция</label>
                <input type="number" name="new_position" class="form-control" min="1" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Причина изменения</label>
                <textarea name="comment" class="form-control" rows="2"></textarea>
            </div>
        </form>
        '''
        return JsonResponse({'html': html})
    
    return render(request, 'applications/change_position.html', {
        'application': application
    })


@login_required
def application_withdraw(request, application_id):
    """Отзыв заявления родителем"""
    if request.user.role != 'parent':
        messages.error(request, 'Только для родителей')
        return redirect('dashboard')
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.parent != request.user.parentprofile:
        messages.error(request, 'Нет доступа')
        return redirect('dashboard')
    
    if application.status in [ApplicationStatus.ENROLLED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN]:
        messages.error(request, 'Заявление нельзя отозвать')
        return redirect('applications:parent_queue')
    
    if request.method == 'POST':
        application.withdraw()
        messages.success(request, 'Заявление отозвано')
        return redirect('applications:parent_queue')
    
    return render(request, 'applications/application_withdraw.html', {
        'application': application
    })


def estimate_wait_time(application):
    """Оценка времени ожидания (в днях)"""
    if not application.queue_position:
        return None
    
    # Среднее количество зачислений в месяц для данной возрастной категории
    settings = QueueSettings.objects.filter(age_category=application.age_category).first()
    if not settings:
        return None
    
    monthly_throughput = 5  # Примерное значение
    weeks_wait = application.queue_position / monthly_throughput
    
    return {
        'weeks': round(weeks_wait, 1),
        'months': round(weeks_wait / 4, 1)
    }


@login_required
def get_queue_position_json(request):
    """API для получения позиции в очереди (для родителя)"""
    if request.user.role != 'parent':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if not hasattr(request.user, 'parentprofile'):
        return JsonResponse({'error': 'Profile not found'}, status=404)
    
    applications = ChildApplication.objects.filter(
        parent=request.user.parentprofile,
        status=ApplicationStatus.QUEUE
    )
    
    result = []
    for app in applications:
        result.append({
            'application_id': app.id,
            'child_name': app.child_full_name,
            'age_category': app.get_age_category_display(),
            'queue_position': app.get_queue_position(),
            'queue_priority': app.queue_priority,
            'benefit_category': app.get_benefit_category_display(),
            'days_in_queue': (date.today() - app.created_at.date()).days,
            'estimated_wait_time': estimate_wait_time(app)
        })
    
    return JsonResponse({'applications': result})


@login_required
def queue_calendar(request):
    """Календарь записи на приём для оформления"""
    if request.user.role != 'parent':
        return redirect('dashboard')
    
    applications = ChildApplication.objects.filter(
        parent=request.user.parentprofile,
        status=ApplicationStatus.INVITED
    )
    
    # Доступные слоты для записи
    available_slots = generate_available_slots()
    
    return render(request, 'applications/queue_calendar.html', {
        'applications': applications,
        'available_slots': available_slots
    })


def generate_available_slots():
    """Генерация доступных слотов для записи"""
    slots = []
    start_date = date.today() + timedelta(days=1)
    
    for i in range(14):  # На 2 недели вперёд
        current_date = start_date + timedelta(days=i)
        if current_date.weekday() < 5:  # Только будние дни
            for hour in [10, 11, 14, 15, 16]:  # Часы приёма
                slots.append({
                    'date': current_date,
                    'time': f'{hour:02d}:00',
                    'datetime': datetime.combine(current_date, datetime.min.time().replace(hour=hour))
                })
    
    return slots


@login_required
def book_appointment(request, application_id):
    """Запись на приём для оформления документов"""
    if request.user.role != 'parent':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.parent != request.user.parentprofile:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        appointment_date_str = data.get('appointment_date')
        
        if appointment_date_str:
            appointment_date = datetime.fromisoformat(appointment_date_str.replace('Z', '+00:00'))
            application.appointment_date = appointment_date
            application.status = ApplicationStatus.PROCESSING
            application.save()
            
            return JsonResponse({'success': True, 'message': 'Время успешно забронировано'})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def queue_statistics(request):
    """API для получения статистики очереди (для виджета)"""
    if request.user.role != 'director':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    stats = {
        'queue': ChildApplication.objects.filter(status=ApplicationStatus.QUEUE).count(),
        'pending': ChildApplication.objects.filter(status=ApplicationStatus.PENDING).count(),
        'invited': ChildApplication.objects.filter(status=ApplicationStatus.INVITED).count(),
        'enrolled': ChildApplication.objects.filter(status=ApplicationStatus.ENROLLED).count(),
    }
    
    return JsonResponse(stats)


@login_required
def create_enrollment_order(request, application_id):
    """Создание приказа о зачислении"""
    if request.user.role != 'director':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Доступ только для заведующей'}, status=403)
        messages.error(request, 'Доступ только для заведующей')
        return redirect('dashboard')
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.status != ApplicationStatus.PROCESSING:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Заявление не на стадии оформления'}, status=400)
        messages.error(request, 'Заявление не на стадии оформления')
        return redirect('applications:director_queue')
    
    if request.method == 'POST':
        if request.headers.get('Content-Type') == 'application/json':
            data = json.loads(request.body)
            order_number = data.get('order_number', '')
            order_date = data.get('order_date', date.today().isoformat())
            group_name = data.get('group_name', '')
        else:
            order_number = request.POST.get('order_number', '')
            order_date = request.POST.get('order_date', date.today().isoformat())
            group_name = request.POST.get('group_name', '')
        
        if not order_number or not group_name:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Заполните все поля'}, status=400)
            messages.error(request, 'Заполните все поля')
            return redirect('applications:director_queue')
        
        application.create_enrollment_order(order_number, order_date, group_name)
        
        # Обновляем настройки очереди для категории
        if application.age_category:
            settings, _ = QueueSettings.objects.get_or_create(age_category=application.age_category)
            settings.current_enrolled += 1
            settings.save()
            recalc_category_queue_positions(application.age_category)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Приказ создан, ребёнок зачислен'})
        
        messages.success(request, f'Приказ {order_number} создан, ребёнок зачислен в группу {group_name}')
        return redirect('applications:director_queue')
    
    # GET запрос - форма для создания приказа
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = f'''
        <form id="orderForm">
            <div class="mb-3">
                <label class="form-label">Номер приказа</label>
                <input type="text" name="order_number" class="form-control" required>
                <small class="text-muted">Пример: 2025-001</small>
            </div>
            <div class="mb-3">
                <label class="form-label">Дата приказа</label>
                <input type="date" name="order_date" class="form-control" value="{date.today().isoformat()}" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Группа для зачисления</label>
                <input type="text" name="group_name" class="form-control" placeholder="Например: Младшая группа №1" required>
            </div>
        </form>
        '''
        return JsonResponse({'html': html})
    
    return render(request, 'applications/create_order.html', {
        'application': application,
        'today': date.today()
    })


# ==================== API ENDPOINTS ====================

@login_required
def application_api_detail(request, application_id):
    """API для получения данных заявления в JSON"""
    if request.user.role not in ['director', 'parent']:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile'):
            return JsonResponse({'error': 'Profile not found'}, status=404)
        if application.parent != request.user.parentprofile:
            return JsonResponse({'error': 'Access denied'}, status=403)
    
    queue_position = application.get_queue_position()
    if queue_position is None and application.queue_position:
        queue_position = application.queue_position
    
    data = {
        'id': application.id,
        'child_full_name': application.child_full_name,
        'child_birth_date': application.child_birth_date.strftime('%d.%m.%Y') if application.child_birth_date else '',
        'child_gender': application.child_gender,
        'child_snils': getattr(application, 'child_snils', ''),
        'registration_address': application.registration_address,
        'actual_address': application.actual_address,
        'applicant1_full_name': application.applicant1_full_name or '',
        'applicant1_phone': application.applicant1_phone or '',
        'applicant2_full_name': application.applicant2_full_name or '',
        'applicant2_phone': application.applicant2_phone or '',
        'phone_number': application.phone_number or '',
        'email': application.email or '',
        'blood_type': application.blood_type or '',
        'allergies': application.allergies or '',
        'chronic_diseases': application.chronic_diseases or '',
        'has_vaccinations': application.has_vaccinations,
        'data_processing_consent': application.data_processing_consent,
        'rules_acquainted': application.rules_acquainted,
        'medical_examination_consent': application.medical_examination_consent,
        'photo_video_consent': application.photo_video_consent,
        'queue_position': queue_position,
        'queue_priority': application.queue_priority,
        'status': application.status,
        'status_display': application.get_status_display_verbose(),
        'benefit_category': application.benefit_category,
        'benefit_display': application.get_benefit_category_display(),
        'created_at': application.created_at.strftime('%d.%m.%Y %H:%M'),
        'birth_certificate_file': application.birth_certificate_file.url if application.birth_certificate_file else None,
        'medical_card': application.medical_card.url if application.medical_card else None,
        'applicant1_passport_file': application.applicant1_passport_file.url if application.applicant1_passport_file else None,
        'residence_certificate': application.residence_certificate.url if application.residence_certificate else None,
        'benefit_document': (application.benefit_document_right or application.benefit_document).url if (application.benefit_document_right or application.benefit_document) else None,
        'generated_application': application.generated_application.url if application.generated_application else None,
    }
    return JsonResponse(data)


@login_required
def application_history_api(request, application_id):
    """API для получения истории движения заявления"""
    # Разрешаем доступ и родителям, и директору
    if request.user.role not in ['director', 'parent']:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    # Проверка прав для родителя
    if request.user.role == 'parent':
        if not hasattr(request.user, 'parentprofile'):
            return JsonResponse({'error': 'Profile not found'}, status=404)
        if application.parent != request.user.parentprofile:
            return JsonResponse({'error': 'Access denied'}, status=403)
    
    history = application.queue_history.all()[:20]
    
    history_data = []
    for item in history:
        movement_type = 'stable'
        if item.old_position and item.new_position:
            if item.new_position < item.old_position:
                movement_type = 'up'
            elif item.new_position > item.old_position:
                movement_type = 'down'
        
        history_data.append({
            'old_position': item.old_position,
            'new_position': item.new_position,
            'movement_type': movement_type,
            'date': item.changed_at.strftime('%d.%m.%Y %H:%M'),
            'reason': item.reason or '',
        })
    
    return JsonResponse({'history': history_data})


@login_required
def verify_form_api(request, application_id):
    """API для получения формы проверки документов"""
    if request.user.role != 'director':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    html = f'''
    <div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Документы проверены</label>
            <input type="checkbox" name="documents_verified" id="docVerified" class="w-5 h-5" {'checked' if application.documents_verified else ''}>
        </div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Примечание</label>
            <textarea name="verification_comment" id="verifyComment" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" rows="3">{application.verification_comment or ''}</textarea>
        </div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Новый статус</label>
            <select name="status" id="statusSelect" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500">
                <option value="pending">На проверке</option>
                <option value="queue">В очередь</option>
                <option value="rejected">Отказать</option>
                <option value="returned">Вернуть на доработку</option>
            </select>
        </div>
        <div class="mb-4" id="returnReasonDiv" style="display:none;">
            <label class="block text-sm font-medium text-gray-700 mb-2">Причина возврата</label>
            <textarea name="comment" id="returnComment" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" rows="2"></textarea>
        </div>
    </div>
    <script>
        document.getElementById('statusSelect').addEventListener('change', function() {{
            document.getElementById('returnReasonDiv').style.display = this.value === 'returned' ? 'block' : 'none';
        }});
    </script>
    '''
    return JsonResponse({'html': html})


@login_required
def verify_api(request, application_id):
    """API для сохранения результатов проверки"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    data = json.loads(request.body)
    
    application.documents_verified = data.get('documents_verified', False)
    application.verification_comment = data.get('verification_comment', '')
    new_status = data.get('status', '')
    
    if new_status == 'queue':
        application.status = ApplicationStatus.QUEUE
        application.queue_priority = application.calculate_priority_score()
        application.save()
        recalc_category_queue_positions(application.age_category)
    elif new_status == 'rejected':
        application.status = ApplicationStatus.REJECTED
        application.save()
    elif new_status == 'returned':
        application.return_for_revision(data.get('comment', ''))
    else:
        application.status = ApplicationStatus.PENDING
        application.save()
    
    return JsonResponse({'success': True})


@login_required
def invite_api(request, application_id):
    """API для приглашения на оформление"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Доступ только для заведующей'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.status != ApplicationStatus.QUEUE:
        return JsonResponse({'success': False, 'error': 'Пригласить можно только заявление в очереди'}, status=400)
    
    try:
        application.status = ApplicationStatus.INVITED
        application.invitation_expires_at = timezone.now() + timedelta(days=14)
        application.save()
        
        # Создаем уведомление
        try:
            from notifications.models import Notification
            Notification.objects.create(
                user=application.parent.user,
                title="🎉 Приглашение на оформление!",
                message=f"Уважаемый(ая)! Ваш ребенок {application.child_full_name} приглашен для оформления в детский сад. Срок действия приглашения до {application.invitation_expires_at.strftime('%d.%m.%Y')}.",
                notification_type='invite',
                link=f"/applications/{application.id}/"
            )
        except Exception as e:
            print(f"Ошибка создания уведомления: {e}")
        
        return JsonResponse({'success': True, 'message': 'Родитель приглашен на оформление'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def position_form_api(request, application_id):
    """API для получения формы изменения позиции"""
    if request.user.role != 'director':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    html = f'''
    <div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Текущая позиция</label>
            <input type="text" class="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-100" value="{application.queue_position or '—'}" disabled>
        </div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Новая позиция</label>
            <input type="number" name="new_position" id="newPosition" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" min="1" required>
        </div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Причина изменения</label>
            <textarea name="comment" id="positionComment" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" rows="2"></textarea>
        </div>
    </div>
    '''
    return JsonResponse({'html': html})


@login_required
def position_change_api(request, application_id):
    """API для изменения позиции"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    data = json.loads(request.body)
    new_pos = data.get('new_position')
    comment = data.get('comment', '')
    
    if not new_pos:
        return JsonResponse({'success': False, 'error': 'Не указана новая позиция'}, status=400)
    
    new_pos = int(new_pos)
    old_pos = application.queue_position
    
    # Получаем все заявления в этой категории
    category_apps = list(ChildApplication.objects.filter(
        status=ApplicationStatus.QUEUE,
        age_category=application.age_category
    ).order_by('-queue_priority', 'created_at'))
    
    # Удаляем текущее заявление из списка
    current_index = category_apps.index(application)
    category_apps.pop(current_index)
    
    # Вставляем на новую позицию
    category_apps.insert(new_pos - 1, application)
    
    # Обновляем позиции
    for idx, app in enumerate(category_apps, 1):
        app.queue_position = idx
        app.save(update_fields=['queue_position'])
        
        QueueHistory.objects.create(
            application=app,
            old_position=old_pos if app == application else app.queue_position,
            new_position=idx,
            new_priority=app.queue_priority,
            age_category=application.age_category,
            reason='Изменено заведующей',
            comment=comment if app == application else ''
        )
    
    return JsonResponse({'success': True})


@login_required
def order_form_api(request, application_id):
    """API для получения формы создания приказа"""
    if request.user.role != 'director':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    html = f'''
    <div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Номер приказа</label>
            <input type="text" name="order_number" id="orderNumber" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" required>
            <small class="text-gray-400 text-xs">Пример: 2025-001</small>
        </div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Дата приказа</label>
            <input type="date" name="order_date" id="orderDate" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" value="{date.today().isoformat()}" required>
        </div>
        <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-2">Группа для зачисления</label>
            <input type="text" name="group_name" id="groupName" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500" placeholder="Например: Младшая группа №1" required>
        </div>
    </div>
    '''
    return JsonResponse({'html': html})


@login_required
def order_create_api(request, application_id):
    """API для создания приказа"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    application = get_object_or_404(ChildApplication, id=application_id)
    data = json.loads(request.body)
    
    order_number = data.get('order_number', '')
    order_date = data.get('order_date', '')
    group_name = data.get('group_name', '')
    
    if not order_number or not group_name:
        return JsonResponse({'success': False, 'error': 'Заполните все поля'}, status=400)
    
    application.status = ApplicationStatus.ENROLLED
    application.enrollment_order_number = order_number
    application.enrollment_order_date = order_date
    application.enrolled_group = group_name
    application.save()
    
    # Обновляем настройки очереди для категории
    if application.age_category:
        settings, _ = QueueSettings.objects.get_or_create(age_category=application.age_category)
        settings.current_enrolled += 1
        settings.save()
        recalc_category_queue_positions(application.age_category)
    
    return JsonResponse({'success': True})


@login_required
def queue_statistics_api(request):
    """API для получения статистики очереди"""
    if request.user.role != 'director':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    stats = {
        'queue': ChildApplication.objects.filter(status=ApplicationStatus.QUEUE).count(),
        'pending': ChildApplication.objects.filter(status=ApplicationStatus.PENDING).count(),
        'invited': ChildApplication.objects.filter(status=ApplicationStatus.INVITED).count(),
        'processing': ChildApplication.objects.filter(status=ApplicationStatus.PROCESSING).count(),
        'enrolled': ChildApplication.objects.filter(status=ApplicationStatus.ENROLLED).count(),
    }
    
    return JsonResponse(stats)


@login_required
def recalculate_queue(request):
    """Пересчёт очереди и автоматическое приглашение"""
    if request.user.role != 'director':
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Обновляем приоритеты
    queue_apps = ChildApplication.objects.filter(status=ApplicationStatus.QUEUE)
    for app in queue_apps:
        app.queue_priority = app.calculate_priority_score()
        app.save(update_fields=['queue_priority'])
    
    # Пересчитываем позиции
    for age_cat in AgeCategory.choices:
        age_cat_code = age_cat[0]
        recalc_category_queue_positions(age_cat_code)
    
    # 🔥 АВТОМАТИЧЕСКОЕ ПРИГЛАШЕНИЕ
    from .queue_logic import auto_invite_from_queue
    invited_count = auto_invite_from_queue()
    
    return JsonResponse({
        'success': True,
        'invited_count': invited_count,
        'message': f'Очередь пересчитана. Приглашено {invited_count} заявителей.'
    })


def auto_invite_from_queue(age_category=None):
    """Автоматическое приглашение следующего в очереди при наличии свободных мест"""
    from .models import QueueSettings, ChildApplication, ApplicationStatus, AgeCategory
    
    invited_count = 0
    
    try:
        categories = [age_category] if age_category else [cat[0] for cat in AgeCategory.choices]
        
        for cat in categories:
            # Получаем настройки очереди
            settings_queue = QueueSettings.objects.filter(age_category=cat).first()
            if not settings_queue:
                continue
            
            # Вычисляем свободные места
            free_places = settings_queue.get_free_places()
            if free_places <= 0:
                continue
            
            # Находим следующих в очереди
            next_apps = ChildApplication.objects.filter(
                status=ApplicationStatus.QUEUE,
                age_category=cat
            ).order_by('-queue_priority', 'created_at')[:free_places]
            
            for app in next_apps:
                # Приглашаем на оформление
                app.status = ApplicationStatus.INVITED
                app.invitation_expires_at = timezone.now() + timedelta(days=14)
                app.save()
                invited_count += 1
                
                # 1. СОЗДАЕМ УВЕДОМЛЕНИЕ В БАЗЕ ДАННЫХ
                try:
                    Notification.objects.create(
                        user=app.parent.user,
                        title="🎉 Приглашение на оформление!",
                        message=f"Уважаемый(ая)! Ваш ребенок {app.child_full_name} приглашен для оформления в детский сад. Пожалуйста, запишитесь на прием в личном кабинете. Срок действия приглашения до {app.invitation_expires_at.strftime('%d.%m.%Y')}.",
                        notification_type='invite',
                        link=f"/applications/{app.id}/"
                    )
                    print(f"✅ Уведомление создано для {app.parent.user.email}")
                except Exception as e:
                    print(f"Ошибка создания уведомления: {e}")
                
                # 2. ОТПРАВЛЯЕМ EMAIL
                try:
                    parent_email = app.parent.user.email
                    if parent_email:
                        subject = f'🎉 Приглашение на оформление в детский сад - {app.child_full_name}'
                        message = f"""
Здравствуйте, {app.parent.user.get_full_name() or app.parent.user.username}!

🎉 Ваш ребенок {app.child_full_name} приглашен для оформления в детский сад.

📅 Срок действия приглашения: до {app.invitation_expires_at.strftime('%d.%m.%Y')}

📝 Для подтверждения необходимо:
1. Войдите в личный кабинет
2. Выберите удобное время для визита
3. Приходите с оригиналами документов

🔗 Перейти к заявлению: http://127.0.0.1:8000/applications/{app.id}/

С уважением,
Администрация детского сада
                        """
                        send_mail(
                            subject,
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [parent_email],
                            fail_silently=False
                        )
                        print(f"✅ Email отправлен на {parent_email}")
                except Exception as e:
                    print(f"Ошибка отправки email: {e}")
                
        return invited_count
        
    except Exception as e:
        print(f"Ошибка автоматического приглашения: {e}")
        return 0


def send_invitation_email(application):
    """Отправка email уведомления родителю о приглашении"""
    try:
        parent_email = application.parent.user.email
        parent_name = application.parent.user.get_full_name() or 'Родитель'
        child_name = application.child_full_name
        expiry_date = application.invitation_expires_at.strftime('%d.%m.%Y')
        
        subject = f'Приглашение на оформление в детский сад - {child_name}'
        message = f"""
Уважаемый(ая) {parent_name}!

Ваш ребенок {child_name} приглашен для оформления в детский сад "Рябинушка".

📅 Явиться до: {expiry_date}

Необходимые документы:
• Паспорт родителя (оригинал)
• Свидетельство о рождении ребенка (оригинал)
• Медицинская карта (оригинал)
• Документы, подтверждающие льготу (при наличии)

Для записи на прием войдите в личный кабинет и выберите удобное время.

С уважением,
Администрация детского сада "Рябинушка"
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [parent_email],
            fail_silently=True
        )
        print(f"Email отправлен на {parent_email}")
        
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        
        
@login_required
def available_slots_api(request, application_id):
    """API для получения доступных слотов записи"""
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.parent.user != request.user:
        return JsonResponse({'success': False, 'error': 'Доступ запрещен'})
    
    # Генерируем слоты на ближайшие 14 дней
    slots = []
    start_date = date.today() + timedelta(days=1)
    
    for i in range(14):
        current_date = start_date + timedelta(days=i)
        if current_date.weekday() < 5:  # Пн-Пт
            for hour in [10, 11, 14, 15, 16]:
                slots.append({
                    'date': current_date.strftime('%d.%m.%Y'),
                    'time': f'{hour:02d}:00',
                    'datetime': datetime.combine(current_date, datetime.min.time().replace(hour=hour)).isoformat()
                })
    
    return JsonResponse({'success': True, 'slots': slots})


@login_required
def book_appointment_api(request):
    """API для бронирования времени визита"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не разрешен'})
    
    data = json.loads(request.body)
    application_id = data.get('application_id')
    appointment_date = data.get('appointment_date')
    
    application = get_object_or_404(ChildApplication, id=application_id)
    
    if application.parent.user != request.user:
        return JsonResponse({'success': False, 'error': 'Доступ запрещен'})
    
    if application.status != ApplicationStatus.INVITED:
        return JsonResponse({'success': False, 'error': 'Заявление не приглашено на оформление'})
    
    # Бронируем время
    application.appointment_date = datetime.fromisoformat(appointment_date)
    application.status = ApplicationStatus.PROCESSING
    application.save()
    
    # Отправляем подтверждение
    send_mail(
        'Подтверждение записи на приём',
        f'Вы записаны на {application.appointment_date.strftime("%d.%m.%Y в %H:%M")}. Приходите с оригиналами документов.',
        settings.DEFAULT_FROM_EMAIL,
        [application.parent.user.email],
        fail_silently=True
    )
    
    return JsonResponse({'success': True})