from django.urls import path
from . import views

app_name = 'nutrition'

urlpatterns = [
    path('', views.nutrition_dashboard, name='dashboard'),
    path('management/', views.menu_management, name='menu_management'),
    path('approval/', views.menu_approval, name='menu_approval'),
    path('parent/', views.parent_menu, name='parent_menu'),
    path('create/', views.create_menu, name='create_menu'),
    path('edit/<int:menu_id>/', views.edit_menu, name='edit_menu'),
    path('approve/ajax/', views.approve_menu_ajax, name='approve_menu_ajax'),
    path('approve/weekly/<str:week_start>/<int:group_id>/', views.approve_weekly_menu, name='approve_weekly_menu'),
    path('export/excel/', views.export_menu_excel, name='export_excel'),
]
