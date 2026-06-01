from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.orders_list, name='orders_list'),
    path('create/', views.order_create, name='order_create'),
    path('create-from-contract/<int:contract_id>/', views.create_order_from_contract, name='create_from_contract'),
    path('grouped-bulk/', views.grouped_bulk_enrollment, name='grouped_bulk_enrollment'),
    path('get-applications-for-group/<int:group_id>/', views.get_applications_for_group, name='get_applications_for_group'),
    path('generate-group-order/', views.generate_group_order_word, name='generate_group_order'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/edit/', views.order_edit, name='order_edit'),
    path('<int:pk>/delete/', views.order_delete, name='order_delete'),
    path('<int:pk>/word/', views.generate_single_order_word, name='generate_word'),
    path('child/<int:child_id>/info/', views.get_child_info, name='get_child_info'),
    path('generate-group-order/', views.generate_group_order_word, name='generate_group_order'),

    path('debug-applications/', views.debug_applications, name='debug_applications'),
    path('debug-check/', views.debug_check, name='debug_check'),
    
    path('<int:pk>/print-ajax/', views.print_order_ajax, name='print_order_ajax'),  # Добавьте эту строку
]