from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


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