# staff/admin.py
from django.contrib import admin
from .models import (
    Employee, PersonalFile, PassportData, INN, SNILS,
    EducationDocument, QualificationCourse, Attestation,
    MedicalExamination, CriminalRecordCheck, StaffPosition,
    StaffUnit, Vacancy, VacancyCandidate, LaborContract,
    AdditionalAgreement, WorkSchedule,  # Убрали WorkScheduleEntry
    Timesheet, TimesheetEntry, LeaveSchedule, LeaveRequest,
    DisciplinaryAction, Encouragement, DispensaryRecord,
    SalaryCalculation, SalaryComponent, HireOrder
)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'position', 'employee_type', 'hire_date', 'is_active']
    list_filter = ['employee_type', 'position', 'is_active']
    search_fields = ['full_name', 'position', 'email', 'phone']
    list_per_page = 25
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('full_name', 'employee_type', 'position', 'photo')
        }),
        ('Контактные данные', {
            'fields': ('phone', 'email', 'address')
        }),
        ('Личные данные', {
            'fields': ('birth_date', 'birth_place')
        }),
        ('Статус', {
            'fields': ('is_active', 'hire_date', 'dismissal_date', 'dismissal_reason')
        }),
    )

@admin.register(PersonalFile)
class PersonalFileAdmin(admin.ModelAdmin):
    list_display = ['employee', 'file_number', 'created_at']
    search_fields = ['employee__full_name', 'file_number']

@admin.register(PassportData)
class PassportDataAdmin(admin.ModelAdmin):
    list_display = ['employee', 'series', 'number', 'issue_date']
    search_fields = ['employee__full_name', 'series', 'number']

@admin.register(INN)
class INNAdmin(admin.ModelAdmin):
    list_display = ['employee', 'inn_number']
    search_fields = ['employee__full_name', 'inn_number']

@admin.register(SNILS)
class SNILSAdmin(admin.ModelAdmin):
    list_display = ['employee', 'snils_number']
    search_fields = ['employee__full_name', 'snils_number']

@admin.register(EducationDocument)
class EducationDocumentAdmin(admin.ModelAdmin):
    list_display = ['employee', 'education_level', 'institution', 'issue_date']
    list_filter = ['education_level']
    search_fields = ['employee__full_name', 'institution']

@admin.register(QualificationCourse)
class QualificationCourseAdmin(admin.ModelAdmin):
    list_display = ['employee', 'course_name', 'end_date', 'hours']
    search_fields = ['employee__full_name', 'course_name']

@admin.register(Attestation)
class AttestationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'attestation_date', 'category', 'valid_until']
    list_filter = ['category', 'result']
    search_fields = ['employee__full_name']

@admin.register(MedicalExamination)
class MedicalExaminationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'examination_type', 'examination_date', 'valid_until']
    list_filter = ['examination_type']
    search_fields = ['employee__full_name']
    date_hierarchy = 'valid_until'

@admin.register(CriminalRecordCheck)
class CriminalRecordCheckAdmin(admin.ModelAdmin):
    list_display = ['employee', 'check_date', 'valid_until']
    search_fields = ['employee__full_name']

@admin.register(StaffPosition)
class StaffPositionAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'category', 'base_salary', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['code', 'title']

@admin.register(StaffUnit)
class StaffUnitAdmin(admin.ModelAdmin):
    list_display = ['position', 'quantity', 'is_vacant', 'employee']
    list_filter = ['is_vacant', 'position__category']
    search_fields = ['position__title', 'employee__full_name']

@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['staff_unit', 'is_published', 'publish_date', 'closing_date']
    list_filter = ['is_published']
    search_fields = ['staff_unit__position__title']

@admin.register(VacancyCandidate)
class VacancyCandidateAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'vacancy', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['full_name', 'email']

@admin.register(LaborContract)
class LaborContractAdmin(admin.ModelAdmin):
    list_display = ['employee', 'contract_number', 'contract_type', 'start_date', 'end_date', 'is_active']
    list_filter = ['contract_type', 'is_active']
    search_fields = ['contract_number', 'employee__full_name']

@admin.register(AdditionalAgreement)
class AdditionalAgreementAdmin(admin.ModelAdmin):
    list_display = ['contract', 'agreement_number', 'agreement_date']
    search_fields = ['agreement_number']

@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'schedule_type', 'weekly_hours', 'is_active']
    list_filter = ['schedule_type', 'is_active']
    search_fields = ['name']

@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ['month', 'year', 'created_by', 'is_closed']
    list_filter = ['month', 'year', 'is_closed']

@admin.register(TimesheetEntry)
class TimesheetEntryAdmin(admin.ModelAdmin):
    list_display = ['employee', 'timesheet', 'total_days', 'total_hours']
    list_filter = ['timesheet__month', 'timesheet__year']
    search_fields = ['employee__full_name']

@admin.register(LeaveSchedule)
class LeaveScheduleAdmin(admin.ModelAdmin):
    list_display = ['employee', 'year', 'start_date', 'end_date', 'leave_type', 'status']
    list_filter = ['year', 'leave_type', 'status']
    search_fields = ['employee__full_name']

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'start_date', 'end_date', 'status', 'request_date']
    list_filter = ['status', 'leave_type']
    search_fields = ['employee__full_name']

@admin.register(DisciplinaryAction)
class DisciplinaryActionAdmin(admin.ModelAdmin):
    list_display = ['employee', 'action_type', 'order_date', 'is_active', 'valid_until']
    list_filter = ['action_type', 'is_active']
    search_fields = ['employee__full_name']

@admin.register(Encouragement)
class EncouragementAdmin(admin.ModelAdmin):
    list_display = ['employee', 'encouragement_type', 'order_date', 'bonus_amount']
    list_filter = ['encouragement_type']
    search_fields = ['employee__full_name']

@admin.register(DispensaryRecord)
class DispensaryRecordAdmin(admin.ModelAdmin):
    list_display = ['employee', 'year', 'status', 'exemption_start', 'exemption_end']
    list_filter = ['year', 'status']
    search_fields = ['employee__full_name']

@admin.register(SalaryCalculation)
class SalaryCalculationAdmin(admin.ModelAdmin):
    list_display = ['employee', 'month', 'year', 'total_accrued', 'total_payable', 'status']
    list_filter = ['month', 'year', 'status']
    search_fields = ['employee__full_name']

@admin.register(SalaryComponent)
class SalaryComponentAdmin(admin.ModelAdmin):
    list_display = ['salary_calculation', 'component_type', 'name', 'amount']
    list_filter = ['component_type']

@admin.register(HireOrder)
class HireOrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'order_date', 'employee', 'position', 'status']
    list_filter = ['status', 'order_date']
    search_fields = ['order_number', 'employee__full_name', 'position']
