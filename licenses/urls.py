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
