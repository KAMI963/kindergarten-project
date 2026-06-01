# contracts/admin.py
from django.contrib import admin
from .models import EducationContract, ContractRegistry

@admin.register(EducationContract)
class EducationContractAdmin(admin.ModelAdmin):
    list_display = [
        'contract_number', 
        'registration_date', 
        'child', 
        'parent',
        'status',
        'is_active'
    ]
    list_filter = ['status', 'is_active', 'registration_date']
    search_fields = ['contract_number', 'child__full_name', 'parent__user__username']
    readonly_fields = ['contract_number', 'created_at', 'updated_at']
    date_hierarchy = 'registration_date'
    
    fieldsets = (
        ('Регистрационные данные', {
            'fields': ('contract_number', 'registration_date', 'status', 'is_active')
        }),
        ('Участники договора', {
            'fields': ('child', 'parent')
        }),
        ('Основные условия', {
            'fields': ('enrollment_date', 'group_name', 'educational_program', 'study_period', 'stay_regimen')
        }),
        ('Финансовые условия', {
            'fields': ('parent_fee', 'subscription_fee', 'food_fee')
        }),
        ('Дополнительная информация', {
            'fields': ('basis_documents', 'notes', 'generated_contract')
        }),
        ('Служебная информация', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ContractRegistry)
class ContractRegistryAdmin(admin.ModelAdmin):
    list_display = [
        'registry_number', 
        'contract', 
        'has_additional_agreements', 
        'last_check_date',
        'checked_by'
    ]
    list_filter = ['has_additional_agreements', 'last_check_date']
    search_fields = ['registry_number', 'contract__contract_number']
    readonly_fields = ['registry_number', 'created_at', 'updated_at']
