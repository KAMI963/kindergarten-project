# contracts/urls.py
from django.urls import path
from . import views

app_name = 'contracts'

# contracts/urls.py
urlpatterns = [
    path('', views.my_contracts, name='my_contracts'),
    path('my-contracts/', views.my_contracts, name='my_contracts'),
    path('<int:pk>/', views.contract_detail, name='contract_detail'),
    path('<int:pk>/generate/', views.generate_contract_word, name='generate_contract'),
    path('<int:pk>/download/', views.download_contract, name='download_contract'),
    path('<int:pk>/sign-parent/', views.sign_contract_parent, name='sign_contract_parent'),
    path('<int:pk>/sign-director/', views.sign_contract_director, name='sign_contract_director'),
    path('<int:pk>/edit/', views.contract_edit, name='contract_edit'),
    path('generate-from-application/<int:application_id>/', 
         views.generate_contract_from_application, 
         name='generate_from_application'),
]