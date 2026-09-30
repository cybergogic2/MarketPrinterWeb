from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


DEFAULT_CELL_CLASS_NAME = '_shelfTag_1tkm1_2 ozi-heading-500 _shelfTag_jn3ur_21'
DEFAULT_CELL_DATA_TESTID = 'logItemPlace'
DEFAULT_CELL_SELECTORS = '\n'.join([
    f'[class="{DEFAULT_CELL_CLASS_NAME}"]',
    f'[data-testid="{DEFAULT_CELL_DATA_TESTID}"]',
])


class LicenseKey(models.Model):
    """Лицензионный ключ, привязанный к пользователю."""
    key = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='licenses')
    point_comment = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    auto_renew_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.key} ({self.user.username})"

    @property
    def display_number(self):
        """Human-friendly token number: user-based prefix plus per-user sequence."""
        sequence = getattr(self, 'user_token_sequence', None)
        if sequence is None:
            if not self.pk or not self.user_id or not self.created_at:
                sequence = 1
            else:
                sequence = LicenseKey.objects.filter(
                    user_id=self.user_id,
                ).filter(
                    models.Q(created_at__lt=self.created_at)
                    | models.Q(created_at=self.created_at, id__lte=self.id)
                ).count()
        return f"{100000 + int(self.user_id)}-{int(sequence):02d}"

    @property
    def status(self):
        """Возвращает статус лицензии для отображения."""
        if not self.is_active:
            return 'deactivated'
        if self.expires_at and self.expires_at < timezone.now():
            return 'expired'
        if not self.activations.exists():
            return 'pending'  # ожидает активации
        return 'active'

    @property
    def status_label(self):
        return {
            'pending': 'Ожидает активации',
            'active': 'Активирован',
            'expired': 'Истёк',
            'deactivated': 'Деактивирован',
        }.get(self.status, 'Неизвестно')

    @property
    def activated_on(self):
        """Hardware ID, к которому привязан ключ (если есть)."""
        activation = self.activations.first()
        return activation.hardware_id if activation else None


class Activation(models.Model):
    """Активация ключа на конкретном компьютере."""
    license_key = models.ForeignKey(
        LicenseKey, on_delete=models.CASCADE, related_name='activations'
    )
    hardware_id = models.CharField(max_length=255)
    activated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('license_key', 'hardware_id')

    def __str__(self):
        return f"{self.license_key.key} on {self.hardware_id[:16]}..."


class Payment(models.Model):
    """Запись о платеже за лицензию."""
    OPERATION_CHOICES = [
        ('top_up', 'Пополнение баланса'),
        ('token_purchase', 'Покупка токена'),
        ('token_renewal', 'Продление токена'),
        ('recurring_top_up', 'Автопополнение баланса'),
        ('auto_token_renewal', 'Автопродление токена'),
        ('manual', 'Ручная операция'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('succeeded', 'Успешно'),
        ('failed', 'Ошибка'),
        ('refunded', 'Возврат'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    license_key = models.ForeignKey(
        LicenseKey, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    days = models.IntegerField(default=0)  # сколько дней покупается
    operation_type = models.CharField(
        max_length=32,
        choices=OPERATION_CHOICES,
        default='token_purchase',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField(max_length=32, default='yookassa')
    gateway_payment_id = models.CharField(max_length=255, blank=True)
    confirmation_url = models.URLField(blank=True)
    save_payment_method = models.BooleanField(default=False)
    saved_payment_method = models.ForeignKey(
        'SavedPaymentMethod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Платёж {self.id} — {self.amount}₽ ({self.status})"


class BillingAccount(models.Model):
    """Внутренний счёт пользователя."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='billing_account',
    )
    balance_kopecks = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'счёт пользователя'
        verbose_name_plural = 'счета пользователей'

    @property
    def balance_rubles(self):
        return Decimal(self.balance_kopecks) / Decimal('100')

    @property
    def balance_display(self):
        return format_kopecks(self.balance_kopecks)

    def __str__(self):
        return f'{self.user.username}: {self.balance_display} ₽'


class BillingOperation(models.Model):
    """Бизнес-операция биллинга: покупка, продление, пополнение, автоплатёж."""
    TYPE_CHOICES = Payment.OPERATION_CHOICES
    STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('succeeded', 'Выполнена'),
        ('failed', 'Ошибка'),
        ('canceled', 'Отменена'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='billing_operations')
    license_key = models.ForeignKey(
        LicenseKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='billing_operations',
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='billing_operations',
    )
    operation_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount_kopecks = models.BigIntegerField(default=0)
    balance_used_kopecks = models.BigIntegerField(default=0)
    external_payment_kopecks = models.BigIntegerField(default=0)
    idempotency_key = models.CharField(max_length=80, unique=True, null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at', '-id')
        verbose_name = 'операция биллинга'
        verbose_name_plural = 'операции биллинга'

    @property
    def amount_display(self):
        return format_kopecks(self.amount_kopecks)

    def __str__(self):
        return f'{self.get_operation_type_display()} #{self.id}'


class LedgerEntry(models.Model):
    """Проводка по внутреннему счёту пользователя."""
    ENTRY_CHOICES = [
        ('external_top_up', 'Пополнение через ЮKassa'),
        ('recurring_top_up', 'Автопополнение через ЮKassa'),
        ('manual_credit', 'Ручное зачисление'),
        ('manual_debit', 'Ручное списание'),
        ('token_purchase', 'Покупка токена'),
        ('token_renewal', 'Продление токена'),
        ('auto_token_renewal', 'Автопродление токена'),
        ('refund', 'Возврат'),
    ]

    account = models.ForeignKey(
        BillingAccount,
        on_delete=models.CASCADE,
        related_name='ledger_entries',
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ledger_entries')
    operation = models.ForeignKey(
        BillingOperation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ledger_entries',
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ledger_entries',
    )
    license_key = models.ForeignKey(
        LicenseKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ledger_entries',
    )
    entry_type = models.CharField(max_length=32, choices=ENTRY_CHOICES)
    amount_kopecks = models.BigIntegerField()
    balance_after_kopecks = models.BigIntegerField()
    comment = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        verbose_name = 'проводка по счёту'
        verbose_name_plural = 'проводки по счетам'

    @property
    def amount_display(self):
        return format_kopecks(self.amount_kopecks)

    @property
    def balance_after_display(self):
        return format_kopecks(self.balance_after_kopecks)

    @property
    def is_income(self):
        return self.amount_kopecks > 0

    def __str__(self):
        return f'{self.get_entry_type_display()} {self.amount_display} ₽'


class SavedPaymentMethod(models.Model):
    """Сохранённый в ЮKassa способ оплаты пользователя для автоплатежей."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_payment_methods')
    provider = models.CharField(max_length=32, default='yookassa')
    provider_payment_method_id = models.CharField(max_length=255, unique=True)
    method_type = models.CharField(max_length=64, blank=True)
    title = models.CharField(max_length=160, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-is_default', '-updated_at', '-id')
        verbose_name = 'сохранённый способ оплаты'
        verbose_name_plural = 'сохранённые способы оплаты'

    def __str__(self):
        return self.title or f'{self.provider}: {self.provider_payment_method_id}'


class RecurringTopUpSettings(models.Model):
    """Настройки регулярного пополнения внутреннего счёта."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='recurring_top_up_settings',
    )
    is_enabled = models.BooleanField(default=False)
    amount_kopecks = models.PositiveBigIntegerField(default=0)
    saved_payment_method = models.ForeignKey(
        SavedPaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_top_up_settings',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'настройки автопополнения'
        verbose_name_plural = 'настройки автопополнения'

    @property
    def amount_display(self):
        return format_kopecks(self.amount_kopecks)

    def __str__(self):
        return f'{self.user.username}: {self.amount_display} ₽'


class YookassaWebhookEvent(models.Model):
    """Сырой webhook ЮKassa для идемпотентной обработки."""
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=120)
    object_id = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)
    is_processed = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-received_at', '-id')
        verbose_name = 'webhook ЮKassa'
        verbose_name_plural = 'webhooks ЮKassa'

    def __str__(self):
        return f'{self.event_type}: {self.object_id or self.event_id}'


class ServiceSettings(models.Model):
    """Настройки сервиса, которые редактирует суперпользователь."""
    singleton_id = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    service_name = models.CharField(max_length=120, default='Magic ПВЗ')
    token_price = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    company_name = models.CharField(max_length=255, blank=True)
    inn = models.CharField(max_length=32, blank=True)
    ogrnip = models.CharField(max_length=32, blank=True)
    bank_name = models.CharField(max_length=255, blank=True)
    bik = models.CharField(max_length=32, blank=True)
    bank_account = models.CharField(max_length=64, blank=True)
    support_hours = models.CharField(max_length=120, blank=True)
    telegram_url = models.URLField(blank=True)
    whatsapp_url = models.URLField(blank=True)
    max_url = models.URLField(blank=True)
    support_email = models.EmailField(blank=True)
    support_phone = models.CharField(max_length=64, blank=True)
    cell_number_class = models.CharField(
        max_length=255,
        default=DEFAULT_CELL_CLASS_NAME,
        blank=True,
    )
    cell_number_data_testid = models.CharField(
        max_length=120,
        default=DEFAULT_CELL_DATA_TESTID,
        blank=True,
    )
    cell_number_id = models.CharField(max_length=120, blank=True)
    cell_extra_selector = models.CharField(max_length=255, blank=True)
    cell_selectors = models.TextField(default=DEFAULT_CELL_SELECTORS, blank=True)
    notice_enabled = models.BooleanField(default=False)
    notice_title = models.CharField(max_length=160, blank=True)
    notice_text = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'настройки сервиса'
        verbose_name_plural = 'настройки сервиса'

    def __str__(self):
        return self.service_name or 'Magic ПВЗ'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(singleton_id=1)
        return obj


class ServiceNotification(models.Model):
    """Важные уведомления, которые показываются в личном кабинете."""
    title = models.CharField(max_length=160, blank=True)
    text = models.TextField()
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-updated_at', '-created_at')
        verbose_name = 'уведомление сервиса'
        verbose_name_plural = 'уведомления сервиса'

    def __str__(self):
        return self.title or 'Важное уведомление'


def format_kopecks(value):
    sign = '-' if value < 0 else ''
    abs_value = abs(int(value or 0))
    rubles, kopecks = divmod(abs_value, 100)
    if kopecks:
        return f'{sign}{rubles},{kopecks:02d}'
    return f'{sign}{rubles}'
