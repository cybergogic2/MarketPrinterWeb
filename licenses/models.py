from django.db import models

# Create your models here.from django.db import models
from django.contrib.auth.models import User
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


class Activation(models.Model):
    """Активация ключа на конкретном компьютере."""
    license_key = models.ForeignKey(LicenseKey, on_delete=models.CASCADE, related_name='activations')
    hardware_id = models.CharField(max_length=255)
    activated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Один ключ — одна активация (один компьютер)
        unique_together = ('license_key', 'hardware_id')

    def __str__(self):
        return f"{self.license_key.key} on {self.hardware_id[:16]}..."
