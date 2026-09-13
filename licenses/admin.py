from django.contrib import admin
from .models import LicenseKey, Activation


@admin.register(LicenseKey)
class LicenseKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'user', 'is_active', 'created_at', 'expires_at')
    list_filter = ('is_active',)
    search_fields = ('key', 'user__username')


@admin.register(Activation)
class ActivationAdmin(admin.ModelAdmin):
    list_display = ('license_key', 'hardware_id', 'activated_at')
    search_fields = ('license_key__key', 'hardware_id')