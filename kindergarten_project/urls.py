from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from accounts import views as account_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', account_views.dashboard, name='dashboard'),
    path('home/', TemplateView.as_view(template_name='home.html'), name='home'),
    path('accounts/', include('accounts.urls')),
    path('applications/', include('applications.urls')),
    path('children/', include('children.urls')),
    path('payments/', include('payments.urls')),
    path('attendance/', include('attendance.urls')),
    path('orders/', include('orders.urls')),
    path('communication/', include('communication.urls')),
    path('nutrition/', include('nutrition.urls')),
    path('lessons/', include('lessons.urls')),  
    path('staff/', include('staff.urls')),
    path('contracts/', include('contracts.urls')),
    path('notifications/', include('notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
