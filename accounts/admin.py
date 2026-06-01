from django.contrib import admin
from .models import ParentProfile, CustomUser, TeacherProfile, DirectorProfile, EmailVerificationCode, PasswordResetCode

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'email', 'role', 'email_verified', 'created_at']
    list_filter = ['role', 'email_verified']
    search_fields = ['username', 'email']
    list_editable = ['email_verified']
    
@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'mobile_phone', 'profile_completed']
    list_filter = ['profile_completed', 'not_working']
    search_fields = ['user__username', 'full_name', 'mobile_phone']

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'specialization', 'experience']

@admin.register(DirectorProfile)
class DirectorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'management_experience']

@admin.register(EmailVerificationCode)
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'created_at', 'expires_at', 'is_used']

@admin.register(PasswordResetCode)
class PasswordResetCodeAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'created_at', 'expires_at', 'is_used']