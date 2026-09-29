from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


DEFAULT_CELL_SELECTORS = '\n'.join([
    '[class="_shelfTag_1tkm1_2 ozi-heading-500 _shelfTag_jn3ur_21"]',
    '[data-testid="logItemPlace"]',
])


class LicenseKey(models.Model):
    """Лицензионный ключ, привязанный к пользователю."""
    key = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='licenses')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.key} ({self.user.username})"

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
            'active': 'Активирована',
            'expired': 'Истекла',
            'deactivated': 'Деактивирована',
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
    STATUS_CHOICES = [
        ('pending', 'Ожидание'),
        ('succeeded', 'Успешно'),
        ('failed', 'Ошибка'),
        ('refunded', 'Возврат'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    license_key = models.ForeignKey(
        LicenseKey, on_delete=models.SET_NULL, null=True, related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    days = models.IntegerField()  # сколько дней покупается
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    gateway_payment_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Платёж {self.id} — {self.amount}₽ ({self.status})"


class ServiceSettings(models.Model):
    """Настройки сервиса, которые редактирует суперпользователь."""
    singleton_id = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    service_name = models.CharField(max_length=120, default='Magic ПВЗ')
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
