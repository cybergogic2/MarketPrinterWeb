from rest_framework import serializers
from .models import LicenseKey, Activation


class ActivationRequestSerializer(serializers.Serializer):
    """Входные данные для активации."""
    license_key = serializers.CharField(max_length=64)
    hardware_id = serializers.CharField(max_length=255)


class CheckRequestSerializer(serializers.Serializer):
    """Входные данные для проверки."""
    license_key = serializers.CharField(max_length=64)
    hardware_id = serializers.CharField(max_length=255)


class LicenseKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = LicenseKey
        fields = ['key', 'is_active', 'created_at', 'expires_at']

class CreateLicenseSerializer(serializers.Serializer):
    """Входные данные для создания лицензии."""
    username = serializers.CharField(max_length=150)
    days = serializers.IntegerField(min_value=1, max_value=3650)

    def validate_username(self, value):
        from django.contrib.auth.models import User
        if not User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Пользователь не найден')
        return value