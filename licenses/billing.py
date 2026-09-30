from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .models import (
    BillingAccount,
    BillingOperation,
    LedgerEntry,
    LicenseKey,
    Payment,
    ServiceSettings,
    format_kopecks,
)
from .pricing import PRICING


class InsufficientBalance(ValueError):
    """Raised when the internal account cannot cover a debit operation."""


def rubles_to_kopecks(value):
    amount = Decimal(str(value or 0))
    return int((amount * Decimal('100')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def kopecks_to_rubles(value):
    return Decimal(value or 0) / Decimal('100')


def get_billing_account(user):
    account, _ = BillingAccount.objects.get_or_create(user=user)
    return account


def get_pricing_options():
    """Return tariffs, using service token price for a monthly token when configured."""
    settings_obj = ServiceSettings.load()
    pricing = {}
    for days, info in PRICING.items():
        price = info['price']
        if days == 30 and settings_obj.token_price:
            price = settings_obj.token_price
        pricing[days] = {
            **info,
            'price': price,
            'price_kopecks': rubles_to_kopecks(price),
        }
    return pricing


def get_price_for_days(days):
    pricing = get_pricing_options()
    if days not in pricing:
        raise ValueError('Unknown tariff')
    return pricing[days]['price_kopecks']


def create_or_extend_license_for_user(user, days, license_key=None, point_comment=None):
    if license_key:
        base_date = max(license_key.expires_at or timezone.now(), timezone.now())
        license_key.expires_at = base_date + timedelta(days=days)
        license_key.is_active = True
        license_key.save(update_fields=['expires_at', 'is_active'])
        return license_key

    return LicenseKey.objects.create(
        user=user,
        point_comment=point_comment or '',
        expires_at=timezone.now() + timedelta(days=days),
        is_active=True,
    )


def create_ledger_entry(
    *,
    account,
    user,
    entry_type,
    amount_kopecks,
    operation=None,
    payment=None,
    license_key=None,
    comment='',
):
    account.balance_kopecks += amount_kopecks
    if account.balance_kopecks < 0:
        raise InsufficientBalance('Недостаточно средств на балансе.')
    account.save(update_fields=['balance_kopecks', 'updated_at'])
    return LedgerEntry.objects.create(
        account=account,
        user=user,
        operation=operation,
        payment=payment,
        license_key=license_key,
        entry_type=entry_type,
        amount_kopecks=amount_kopecks,
        balance_after_kopecks=account.balance_kopecks,
        comment=comment,
    )


@transaction.atomic
def top_up_balance(user, amount_kopecks, *, payment=None, operation_type='top_up', comment=''):
    account, _ = BillingAccount.objects.select_for_update().get_or_create(user=user)
    operation = BillingOperation.objects.create(
        user=user,
        payment=payment,
        operation_type=operation_type,
        status='pending',
        amount_kopecks=amount_kopecks,
        external_payment_kopecks=amount_kopecks,
        description=comment,
        idempotency_key=f'{operation_type}:{uuid4()}',
    )
    if operation_type == 'recurring_top_up':
        entry_type = 'recurring_top_up'
    elif operation_type == 'manual':
        entry_type = 'manual_credit'
    else:
        entry_type = 'external_top_up'
    entry = create_ledger_entry(
        account=account,
        user=user,
        entry_type=entry_type,
        amount_kopecks=amount_kopecks,
        operation=operation,
        payment=payment,
        comment=comment or 'Пополнение баланса',
    )
    operation.status = 'succeeded'
    operation.completed_at = timezone.now()
    operation.save(update_fields=['status', 'completed_at'])
    return operation, entry


@transaction.atomic
def purchase_token_from_balance(user, *, days, license_key=None, point_comment=None):
    price_kopecks = get_price_for_days(days)
    account, _ = BillingAccount.objects.select_for_update().get_or_create(user=user)
    operation_type = 'token_renewal' if license_key else 'token_purchase'
    operation = BillingOperation.objects.create(
        user=user,
        license_key=license_key,
        operation_type=operation_type,
        status='pending',
        amount_kopecks=price_kopecks,
        balance_used_kopecks=price_kopecks,
        description='Списание с внутреннего счёта',
        idempotency_key=f'{operation_type}:balance:{uuid4()}',
    )
    purchased_license = create_or_extend_license_for_user(
        user,
        days,
        license_key=license_key,
        point_comment=point_comment,
    )
    create_ledger_entry(
        account=account,
        user=user,
        entry_type=operation_type,
        amount_kopecks=-price_kopecks,
        operation=operation,
        license_key=purchased_license,
        comment='Списание за токен',
    )
    operation.license_key = purchased_license
    operation.status = 'succeeded'
    operation.completed_at = timezone.now()
    operation.save(update_fields=['license_key', 'status', 'completed_at'])
    return operation, purchased_license


@transaction.atomic
def purchase_token_via_external_payment(user, *, days, license_key=None, point_comment=None, save_payment_method=False):
    price_kopecks = get_price_for_days(days)
    amount_rubles = kopecks_to_rubles(price_kopecks)
    operation_type = 'token_renewal' if license_key else 'token_purchase'
    payment = Payment.objects.create(
        user=user,
        license_key=license_key,
        amount=amount_rubles,
        days=days,
        operation_type=operation_type,
        status='pending',
        provider='yookassa',
        save_payment_method=save_payment_method,
        metadata={
            'mock_checkout': True,
            'accounting': 'credit_then_debit',
        },
    )
    payment.gateway_payment_id = f'mock-yookassa-{payment.id}'
    payment.status = 'succeeded'
    payment.paid_at = timezone.now()
    payment.save(update_fields=['gateway_payment_id', 'status', 'paid_at'])

    account, _ = BillingAccount.objects.select_for_update().get_or_create(user=user)
    operation = BillingOperation.objects.create(
        user=user,
        license_key=license_key,
        payment=payment,
        operation_type=operation_type,
        status='pending',
        amount_kopecks=price_kopecks,
        balance_used_kopecks=price_kopecks,
        external_payment_kopecks=price_kopecks,
        description='Оплата через ЮKassa с зачислением на баланс и списанием',
        idempotency_key=f'{operation_type}:provider:{payment.id}',
    )
    create_ledger_entry(
        account=account,
        user=user,
        entry_type='external_top_up',
        amount_kopecks=price_kopecks,
        operation=operation,
        payment=payment,
        license_key=license_key,
        comment='Зачисление оплаты через ЮKassa',
    )
    purchased_license = create_or_extend_license_for_user(
        user,
        days,
        license_key=license_key,
        point_comment=point_comment,
    )
    create_ledger_entry(
        account=account,
        user=user,
        entry_type=operation_type,
        amount_kopecks=-price_kopecks,
        operation=operation,
        payment=payment,
        license_key=purchased_license,
        comment='Списание за токен',
    )
    payment.license_key = purchased_license
    payment.save(update_fields=['license_key'])
    operation.license_key = purchased_license
    operation.status = 'succeeded'
    operation.completed_at = timezone.now()
    operation.save(update_fields=['license_key', 'status', 'completed_at'])
    return operation, purchased_license, payment


def balance_summary(user):
    account = get_billing_account(user)
    return {
        'account': account,
        'balance_kopecks': account.balance_kopecks,
        'balance_display': format_kopecks(account.balance_kopecks),
    }
