from django.contrib import admin
from .models import (
    Activation,
    BillingAccount,
    BillingOperation,
    LedgerEntry,
    LicenseKey,
    Payment,
    RecurringTopUpSettings,
    SavedPaymentMethod,
    ServiceNotification,
    ServiceSettings,
    YookassaWebhookEvent,
)


@admin.register(LicenseKey)
class LicenseKeyAdmin(admin.ModelAdmin):
    list_display = (
        'display_number',
        'key',
        'point_comment',
        'user',
        'is_active',
        'auto_renew_enabled',
        'created_at',
        'expires_at',
    )
    list_filter = ('is_active', 'auto_renew_enabled')
    search_fields = ('key', 'point_comment', 'user__username')


@admin.register(Activation)
class ActivationAdmin(admin.ModelAdmin):
    list_display = ('license_key', 'hardware_id', 'activated_at')
    search_fields = ('license_key__key', 'hardware_id')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'operation_type',
        'amount',
        'status',
        'provider',
        'gateway_payment_id',
        'created_at',
        'paid_at',
    )
    list_filter = ('operation_type', 'status', 'provider', 'save_payment_method')
    search_fields = ('user__username', 'user__email', 'gateway_payment_id', 'license_key__key')


@admin.register(BillingAccount)
class BillingAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance_kopecks', 'updated_at')
    search_fields = ('user__username', 'user__email')


@admin.register(BillingOperation)
class BillingOperationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'operation_type',
        'status',
        'amount_kopecks',
        'balance_used_kopecks',
        'external_payment_kopecks',
        'created_at',
        'completed_at',
    )
    list_filter = ('operation_type', 'status')
    search_fields = ('user__username', 'user__email', 'idempotency_key')


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'entry_type', 'amount_kopecks', 'balance_after_kopecks', 'created_at')
    list_filter = ('entry_type',)
    search_fields = ('user__username', 'user__email', 'comment')


@admin.register(SavedPaymentMethod)
class SavedPaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'method_type', 'title', 'is_active', 'is_default', 'updated_at')
    list_filter = ('provider', 'method_type', 'is_active', 'is_default')
    search_fields = ('user__username', 'user__email', 'provider_payment_method_id', 'title')


@admin.register(RecurringTopUpSettings)
class RecurringTopUpSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_enabled', 'amount_kopecks', 'saved_payment_method', 'updated_at')
    list_filter = ('is_enabled',)
    search_fields = ('user__username', 'user__email')


@admin.register(ServiceSettings)
class ServiceSettingsAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'company_name', 'telegram_url', 'max_url', 'updated_at')


@admin.register(ServiceNotification)
class ServiceNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_enabled', 'updated_at')
    list_filter = ('is_enabled',)
    search_fields = ('title', 'text')


@admin.register(YookassaWebhookEvent)
class YookassaWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'object_id', 'is_processed', 'received_at', 'processed_at')
    list_filter = ('event_type', 'is_processed')
    search_fields = ('event_id', 'object_id')
