# children/admin.py
from django.contrib import admin
from .models import Child, Group, ChildParent

class ChildParentInline(admin.TabularInline):
    model = ChildParent
    extra = 1
    raw_id_fields = ['parent']

@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'birth_date', 'get_age', 'group', 'is_active', 'enrollment_date']
    list_filter = ['is_active', 'group', 'gender']
    search_fields = ['full_name', 'birth_certificate', 'policy_oms_number']
    inlines = [ChildParentInline]
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('application', 'full_name', 'birth_date', 'gender', 'photo', 'group')
        }),
        ('Документы', {
            'fields': ('birth_certificate', 'birth_certificate_issued_by', 'birth_certificate_issue_date',
                      'medical_card_number', 'policy_oms_number', 'snils')
        }),
        ('Медицинская информация', {
            'fields': ('blood_type', 'allergies', 'chronic_diseases', 'special_needs', 'disability_certificate')
        }),
        ('Адреса', {
            'fields': ('registration_address', 'actual_address')
        }),
        ('Статус', {
            'fields': ('is_active', 'enrollment_date', 'graduation_date')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'age_category', 'teacher', 'capacity', 'children_count']
    list_filter = ['age_category']
    search_fields = ['name', 'teacher__username']
    
    def children_count(self, obj):
        return obj.children_count
    children_count.short_description = 'Количество детей'

@admin.register(ChildParent)
class ChildParentAdmin(admin.ModelAdmin):
    list_display = ['child', 'parent', 'relation', 'is_primary']
    list_filter = ['relation', 'is_primary']
    search_fields = ['child__full_name', 'parent__full_name']
