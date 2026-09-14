from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UsuarioCustom


@admin.register(UsuarioCustom)
class UsuarioCustomAdmin(UserAdmin):
    model = UsuarioCustom
    list_display = ('email', 'first_name', 'role', 'provider', 'is_active', 'is_staff')
    list_filter = ('role', 'provider', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'username')
    ordering = ('email',)
    fieldsets = UserAdmin.fieldsets + (
        ('CropAnalytics', {'fields': ('role', 'provider', 'avatar', 'es_investigador', 'institucion')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('CropAnalytics', {'fields': ('email', 'role', 'provider')}),
    )
