from django.urls import path
from .views import (
    # API
    ActivateView,
    CheckView,
    DeactivateView,
    CreateLicenseView,
    # Личный кабинет
    account_dashboard,
    payment_history,
    buy_license,
    deactivate_license,
    service_settings,
    account_admin_users,
    account_admin_user_create,
    account_admin_user_edit,
    account_admin_user_delete,
    account_admin_licenses,
    account_admin_license_create,
    account_admin_license_edit,
    account_admin_license_delete,
    account_admin_payments,
    account_admin_payment_create,
    account_admin_payment_edit,
    account_admin_payment_delete,
    service_notifications,
    notification_create,
    notification_edit,
    notification_delete,
    notification_toggle,
    extension_config,
    download_qr,
    # Аутентификация
    register,
)

urlpatterns = [
    # API
    path('activate/', ActivateView.as_view(), name='activate'),
    path('check/', CheckView.as_view(), name='check'),
    path('deactivate/', DeactivateView.as_view(), name='deactivate'),
    path('create-license/', CreateLicenseView.as_view(), name='create-license'),

    # Личный кабинет
    path('account/', account_dashboard, name='account_dashboard'),
    path('account/payments/', payment_history, name='payment_history'),
    path('account/buy/', buy_license, name='buy_new_license'),
    path('account/buy/<int:key_id>/', buy_license, name='buy_license'),
    path('account/deactivate/<int:key_id>/', deactivate_license, name='deactivate_license'),
    path('account/admin/users/', account_admin_users, name='account_admin_users'),
    path('account/admin/users/new/', account_admin_user_create, name='account_admin_user_create'),
    path('account/admin/users/<int:user_id>/edit/', account_admin_user_edit, name='account_admin_user_edit'),
    path('account/admin/users/<int:user_id>/delete/', account_admin_user_delete, name='account_admin_user_delete'),
    path('account/admin/licenses/', account_admin_licenses, name='account_admin_licenses'),
    path('account/admin/licenses/new/', account_admin_license_create, name='account_admin_license_create'),
    path('account/admin/licenses/<int:license_id>/edit/', account_admin_license_edit, name='account_admin_license_edit'),
    path('account/admin/licenses/<int:license_id>/delete/', account_admin_license_delete, name='account_admin_license_delete'),
    path('account/admin/payments/', account_admin_payments, name='account_admin_payments'),
    path('account/admin/payments/new/', account_admin_payment_create, name='account_admin_payment_create'),
    path('account/admin/payments/<int:payment_id>/edit/', account_admin_payment_edit, name='account_admin_payment_edit'),
    path('account/admin/payments/<int:payment_id>/delete/', account_admin_payment_delete, name='account_admin_payment_delete'),
    path('account/settings/', service_settings, name='service_settings'),
    path('account/notifications/', service_notifications, name='service_notifications'),
    path('account/notifications/new/', notification_create, name='notification_create'),
    path('account/notifications/<int:notification_id>/edit/', notification_edit, name='notification_edit'),
    path('account/notifications/<int:notification_id>/delete/', notification_delete, name='notification_delete'),
    path('account/notifications/<int:notification_id>/toggle/', notification_toggle, name='notification_toggle'),
    path('account/download-qr.svg', download_qr, name='download_qr'),
    path('extension/config/', extension_config, name='extension_config'),

    # Аутентификация
    path('register/', register, name='register'),
]
