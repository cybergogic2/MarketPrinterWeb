from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import timedelta

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from .models import LicenseKey, Activation, Payment
from .serializers import (
    ActivationRequestSerializer,
    CheckRequestSerializer,
    CreateLicenseSerializer,
)
from .pricing import PRICING


# ============================================================
# API: ЛИЦЕНЗИИ
# ============================================================

class ActivateView(APIView):
    @extend_schema(
        summary="Активация лицензионного ключа",
        description="Привязывает ключ к компьютеру по hardware_id. "
                    "Если ключ уже активирован на другом ПК — возвращает 403.",
        request=ActivationRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Успешная активация или уже активирован на этом ПК",
                examples=[
                    OpenApiExample(
                        "Успех",
                        value={
                            "status": "activated",
                            "message": "Ключ успешно активирован",
                            "expires_at": "2026-10-12T10:30:00Z"
                        }
                    ),
                    OpenApiExample(
                        "Уже активирован",
                        value={
                            "status": "already_activated",
                            "message": "Ключ уже активирован на этом компьютере"
                        }
                    ),
                ]
            ),
            400: OpenApiResponse(description="Неверные данные"),
            403: OpenApiResponse(description="Ключ деактивирован, истёк или занят другим ПК"),
            404: OpenApiResponse(description="Ключ не найден"),
        },
        tags=['Licenses'],
    )
    def post(self, request):
        serializer = ActivationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        key_str = serializer.validated_data['license_key']
        hardware_id = serializer.validated_data['hardware_id']

        try:
            license_key = LicenseKey.objects.get(key=key_str)
        except LicenseKey.DoesNotExist:
            return Response({'error': 'Ключ не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not license_key.is_active:
            return Response({'error': 'Ключ деактивирован'}, status=status.HTTP_403_FORBIDDEN)

        if license_key.expires_at and license_key.expires_at < timezone.now():
            return Response({'error': 'Срок действия ключа истёк'}, status=status.HTTP_403_FORBIDDEN)

        existing = Activation.objects.filter(license_key=license_key)

        if existing.exists():
            if existing.filter(hardware_id=hardware_id).exists():
                return Response({
                    'status': 'already_activated',
                    'message': 'Ключ уже активирован на этом компьютере'
                })
            return Response(
                {'error': 'Ключ уже активирован на другом компьютере'},
                status=status.HTTP_403_FORBIDDEN
            )

        Activation.objects.create(license_key=license_key, hardware_id=hardware_id)

        return Response({
            'status': 'activated',
            'message': 'Ключ успешно активирован',
            'expires_at': license_key.expires_at
        })


class CheckView(APIView):
    @extend_schema(
        summary="Проверка активности лицензии",
        description="Вызывается при каждом запуске приложения. "
                    "Проверяет срок, статус и привязку к hardware_id.",
        request=CheckRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Результат проверки",
                examples=[
                    OpenApiExample(
                        "Валидна",
                        value={"valid": True, "expires_at": "2026-10-12T10:30:00Z"}
                    ),
                    OpenApiExample(
                        "Деактивирована",
                        value={"valid": False, "reason": "deactivated"}
                    ),
                    OpenApiExample(
                        "Срок истёк",
                        value={"valid": False, "reason": "expired"}
                    ),
                    OpenApiExample(
                        "Не активирована на этом ПК",
                        value={"valid": False, "reason": "not_activated_on_this_machine"}
                    ),
                ]
            ),
            400: OpenApiResponse(description="Неверные данные"),
            404: OpenApiResponse(description="Ключ не найден"),
        },
        tags=['Licenses'],
    )
    def post(self, request):
        serializer = CheckRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        key_str = serializer.validated_data['license_key']
        hardware_id = serializer.validated_data['hardware_id']

        try:
            license_key = LicenseKey.objects.get(key=key_str)
        except LicenseKey.DoesNotExist:
            return Response({'error': 'Ключ не найден'}, status=status.HTTP_404_NOT_FOUND)

        if not license_key.is_active:
            return Response({'valid': False, 'reason': 'deactivated'})

        if license_key.expires_at and license_key.expires_at < timezone.now():
            return Response({'valid': False, 'reason': 'expired'})

        activation = Activation.objects.filter(
            license_key=license_key, hardware_id=hardware_id
        ).first()

        if not activation:
            return Response({'valid': False, 'reason': 'not_activated_on_this_machine'})

        return Response({'valid': True, 'expires_at': license_key.expires_at})


class DeactivateView(APIView):
    @extend_schema(
        summary="Деактивация ключа (из программы)",
        description="Снимает привязку ключа к hardware_id. "
                    "Используется при переносе лицензии на другой ПК.",
        request=ActivationRequestSerializer,
        responses={
            200: OpenApiResponse(
                description="Привязка снята",
                examples=[
                    OpenApiExample("Успех", value={"status": "deactivated", "message": "Привязка снята"})
                ]
            ),
            400: OpenApiResponse(description="Неверные данные"),
            404: OpenApiResponse(description="Ключ или активация не найдены"),
        },
        tags=['Licenses'],
    )
    def post(self, request):
        serializer = ActivationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        key_str = serializer.validated_data['license_key']
        hardware_id = serializer.validated_data['hardware_id']

        try:
            license_key = LicenseKey.objects.get(key=key_str)
        except LicenseKey.DoesNotExist:
            return Response({'error': 'Ключ не найден'}, status=status.HTTP_404_NOT_FOUND)

        deleted, _ = Activation.objects.filter(
            license_key=license_key, hardware_id=hardware_id
        ).delete()

        if deleted:
            return Response({'status': 'deactivated', 'message': 'Привязка снята'})
        return Response({'error': 'Активация не найдена'}, status=status.HTTP_404_NOT_FOUND)


class CreateLicenseView(APIView):
    @extend_schema(
        summary="Создание лицензионного ключа",
        description="Только для внутреннего API. Требует заголовок X-API-Key. "
                    "Создаёт ключ для пользователя на указанное количество дней.",
        request=CreateLicenseSerializer,
        responses={
            201: OpenApiResponse(
                description="Ключ создан",
                examples=[
                    OpenApiExample(
                        "Успех",
                        value={
                            "status": "created",
                            "key": "f7e8d9c0-1234-5678-90ab-cdef12345678",
                            "username": "ivan_petrov",
                            "expires_at": "2026-10-12T10:30:00Z",
                            "days": 30
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description="Неверные данные"),
            401: OpenApiResponse(description="Неверный или отсутствующий X-API-Key"),
        },
        tags=['Licenses'],
    )
    def post(self, request):
        api_key = request.headers.get('X-API-Key')
        if api_key != settings.INTERNAL_API_KEY:
            return Response({'error': 'Неавторизованный запрос'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = CreateLicenseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data['username']
        days = serializer.validated_data['days']

        user = User.objects.get(username=username)
        expires_at = timezone.now() + timedelta(days=days)

        license_key = LicenseKey.objects.create(
            user=user, expires_at=expires_at, is_active=True
        )

        return Response({
            'status': 'created',
            'key': str(license_key.key),
            'username': user.username,
            'expires_at': expires_at,
            'days': days
        }, status=status.HTTP_201_CREATED)


# ============================================================
# ЛИЧНЫЙ КАБИНЕТ
# ============================================================

@login_required
def account_dashboard(request):
    """Личный кабинет: список ключей."""
    licenses = request.user.licenses.all().order_by('-created_at')
    return render(request, 'licenses/account/dashboard.html', {'licenses': licenses})


@login_required
def payment_history(request):
    """История платежей."""
    payments = request.user.payments.all().order_by('-created_at')
    return render(request, 'licenses/account/payments.html', {'payments': payments})


@login_required
def buy_license(request, key_id=None):
    """Покупка новой лицензии или продление существующей."""
    if key_id:
        license_key = get_object_or_404(LicenseKey, id=key_id, user=request.user)
        is_new = False
    else:
        license_key = None
        is_new = True

    if request.method == 'POST':
        days = int(request.POST.get('days', 30))
        if days not in PRICING:
            messages.error(request, 'Неверный тариф')
            return redirect('account_dashboard')

        payment = Payment.objects.create(
            user=request.user,
            license_key=license_key,
            amount=PRICING[days]['price'],
            days=days,
            status='pending'
        )

        # TODO: интеграция с ЮKassa — редирект на платёжную страницу
        messages.info(request, f'Платёж создан на {PRICING[days]["price"]}₽. Интеграция с ЮKassa — следующий шаг.')
        return redirect('account_dashboard')

    return render(request, 'licenses/account/buy.html', {
        'license_key': license_key,
        'is_new': is_new,
        'pricing': PRICING,
    })


@login_required
def deactivate_license(request, key_id):
    """Деактивация лицензии из ЛК — снимает все привязки к железу."""
    license_key = get_object_or_404(LicenseKey, id=key_id, user=request.user)

    if request.method == 'POST':
        deleted_count, _ = license_key.activations.all().delete()

        if deleted_count:
            messages.success(
                request,
                'Лицензия деактивирована. Теперь её можно активировать на другом компьютере.'
            )
        else:
            messages.info(request, 'У лицензии не было активных привязок.')

        return redirect('account_dashboard')

    return render(request, 'licenses/account/deactivate.html', {
        'license_key': license_key,
    })