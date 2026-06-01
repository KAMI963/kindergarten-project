from django.contrib import admin
from .models import Tariff, Payment, PaymentCalculation, AdditionalService, ServiceEnrollment, ChildAccount


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ['age_category', 'year', 'content_amount', 'food_amount', 'daily_rate', 'food_daily_rate', 'total_amount']
    list_filter = ['age_category', 'year']
    search_fields = ['age_category']
    ordering = ['-year', 'age_category']

@admin.register(AdditionalService)
class AdditionalServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'service_type', 'price_per_month', 'is_active', 'max_students']
    list_filter = ['service_type', 'is_active']
    search_fields = ['name', 'teacher']
    list_editable = ['price_per_month', 'is_active']


@admin.register(ServiceEnrollment)
class ServiceEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['child', 'service', 'enrollment_date', 'start_date', 'status']
    list_filter = ['status', 'service']
    search_fields = ['child__full_name', 'service__name']
    list_editable = ['status']


@admin.register(ChildAccount)
class ChildAccountAdmin(admin.ModelAdmin):
    list_display = ['child', 'account_number', 'balance']
    search_fields = ['child__full_name', 'account_number']
    readonly_fields = ['account_number', 'created_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['child', 'month', 'year', 'amount', 'status', 'attendance_days', 'discount_amount']
    list_filter = ['status', 'month', 'year', 'paid_at']
    search_fields = ['child__full_name', 'child__group__name']
    readonly_fields = ['attendance_days', 'food_days', 'total_days', 'base_amount', 
                       'discount_amount', 'additional_services_amount']
    date_hierarchy = 'paid_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('child', 'month', 'year', 'amount', 'status')
        }),
        ('Расчетные данные', {
            'fields': (
                'base_amount', 'discount_rate', 'discount_amount',
                'attendance_days', 'total_days', 'daily_rate',
                'food_days', 'food_daily_rate',
                'additional_services_amount', 'additional_services_details'
            ),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('paid_at', 'transaction_id', 'paid_from_account', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('child')


@admin.register(PaymentCalculation)
class PaymentCalculationAdmin(admin.ModelAdmin):
    list_display = ['payment', 'calculation_date']
    list_filter = ['calculation_date']
    readonly_fields = ['calculation_date', 'details']
    date_hierarchy = 'calculation_date'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False