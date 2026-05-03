from django.contrib import admin
from django.urls import path, include
from payments.views import dashboard
from core.views import create_admin_once

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),

    # services
    path('services/', include('services.urls')),

    # payments
    path('payments/', include('payments.urls')),

    # billing (LEVEL 3)
    path('billing/', include('billing.urls')),
    path("create-admin-once/", create_admin_once),
]