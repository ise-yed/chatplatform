from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('id', 'username', 'email', 'is_online', 'is_staff')
    search_fields = ('username', 'email')