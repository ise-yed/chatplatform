
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('api/v1/accounts/', include('apps.accounts.api.v1.urls')),
    path('api/v1/chat/', include('apps.chat.api.v1.urls')),
    path('chat/', include('apps.chat.urls')),
]