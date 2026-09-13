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
]