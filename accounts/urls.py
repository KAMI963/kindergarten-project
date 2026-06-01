from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Регистрация и подтверждение
    path('register/', views.register, name='register'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-verification/ajax/', views.resend_verification_ajax, name='resend_verification_ajax'),
    path('change-photo/', views.change_photo, name='change_photo'),
    path('upload-parent-photo/', views.upload_parent_photo, name='upload_parent_photo'),
    path('change-password/', views.change_password, name='change_password'), 
    
    # Вход и выход
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('profile/', views.profile, name='profile'),  
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Восстановление пароля
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/verify/', views.password_reset_verify, name='password_reset_verify'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),

    # Родительские профили
    path('parent-profile/', views.parent_profile_view, name='parent_profile'),
    path('parent-profile/edit/', views.parent_profile_edit, name='parent_profile_edit'),
    
    # AJAX endpoints
    path('verify-email/ajax/', views.verify_email_ajax, name='verify_email_ajax'),
]