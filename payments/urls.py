from django.urls import path
from . import views


app_name = 'payments'

urlpatterns = [
    # Существующие URL
    path('finance/', views.parent_finance_cabinet, name='parent_finance'),
    path('history/', views.payment_history, name='payment_history'),
    path('parent/', views.parent_payments, name='parent_payments'),
    path('child/<int:child_id>/', views.payment_page, name='payment_page'),
    path('child/<int:child_id>/calculation/', views.payment_calculation, name='payment_calculation'),
    path('child/<int:child_id>/calculation/<int:month>/<int:year>/', views.payment_calculation, name='payment_calculation_detail'),
    path('simulate/<int:payment_id>/', views.simulate_payment, name='simulate_payment'),
    path('success/', views.payment_success, name='payment_success'),
    path('recalculate/', views.recalculate_payment_ajax, name='recalculate_payment_ajax'),
    path('recalculate-all/', views.recalculate_all_payments, name='recalculate_all_payments'),
    path('tariffs/', views.tariff_management, name='tariff_management'),
    path('receipt/<int:payment_id>/', views.generate_receipt, name='generate_receipt'),
    path('child/<int:child_id>/pay/', views.payment_page, name='payment_page'),
    # Новые URL для оплаты с карты (используем payment_views)
    path('credit-cards-payment-direct/', views.credit_cards_payment_direct, name='credit_cards_payment_direct'),
    path('credit-cards-payment/<int:payment_id>/', views.credit_cards_payment_page, name='credit_cards_payment'),
    
    # Управление банковскими картами
    path('api/add-card/', views.add_card_api, name='add_card_api'),
    path('api/delete-card/<int:card_id>/', views.delete_card_api, name='delete_card_api'),
    path('api/set-default-card/<int:card_id>/', views.set_default_card_api, name='set_default_card_api'),
    
    # Новые URL для дополнительных услуг
    path('services/', views.services_catalog, name='services_catalog'),
    path('services/enroll/<int:service_id>/', views.enroll_in_service, name='enroll_in_service'),
    path('my-enrollments/', views.my_enrollments, name='my_enrollments'),
    path('group-enrollments/', views.group_service_enrollments, name='group_enrollments'),
    path('enrollment/<int:enrollment_id>/update-status/', views.update_enrollment_status, name='update_enrollment_status'),
    # ✅ ДОБАВЬТЕ ЭТИ ДВЕ СТРОКИ:
    path('services/manage/create-ajax/', views.service_create_ajax, name='service_create_ajax'),
    path('services/manage/<int:pk>/edit-ajax/', views.service_edit_ajax, name='service_edit_ajax'),
    
        # Для заведующей
    path('director/dashboard/', views.director_payments_dashboard, name='director_payments_dashboard'),
    path('director/recalculate/<int:year>/<int:month>/', views.recalculate_month_payments, name='recalculate_month_payments'),
    
    # Управление дополнительными услугами (для заведующей)
    path('services/manage/', views.manage_services, name='manage_services'),
    path('services/manage/create/', views.service_create, name='service_create'),
    path('services/manage/<int:pk>/edit/', views.service_edit, name='service_edit'),
    path('services/manage/<int:pk>/delete/', views.service_delete_ajax, name='service_delete_ajax'),
    path('services/manage/<int:pk>/toggle/', views.service_toggle_active, name='service_toggle_active'),
    path('api/service/<int:pk>/', views.api_service_detail, name='api_service_detail'),
    
    # Для воспитателя
    path('teacher/dashboard/', views.teacher_services_dashboard, name='teacher_dashboard'),
    path('teacher/attendance/<int:service_id>/', views.mark_service_attendance, name='mark_service_attendance'),
    path('teacher/attendance-sheet/<int:service_id>/', views.service_attendance_sheet, name='service_attendance_sheet'),
    
    # Договора
    path('contract/generate/<int:enrollment_id>/', views.generate_service_contract, name='generate_service_contract'),
    path('contract/sign/<int:enrollment_id>/', views.sign_service_contract, name='sign_service_contract'),
]