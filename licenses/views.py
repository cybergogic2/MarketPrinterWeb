from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q, Window
from django.db.models.functions import RowNumber
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import login
from .billing import (
    InsufficientBalance,
    balance_summary,
    create_or_extend_license_for_user,
    get_pricing_options,
    purchase_token_from_balance,
    purchase_token_via_external_payment,
    top_up_balance as apply_top_up_balance,
)
from .forms import (
    AdminLicenseForm,
    AdminPaymentForm,
    AdminUserForm,
    LicensePointForm,
    RegisterForm,
    RecurringTopUpForm,
    ServiceNotificationForm,
    ServiceSettingsForm,
    TopUpBalanceForm,
)

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from .models import (
    DEFAULT_CELL_SELECTORS,
    LicenseKey,
    Activation,
    Payment,
    RecurringTopUpSettings,
    ServiceNotification,
    ServiceSettings,
)
from .serializers import (
    ActivationRequestSerializer,
    CheckRequestSerializer,
    CreateLicenseSerializer,
)


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
                        "Деактивирован",
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
                            "number": "100001-01",
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
        point_comment = serializer.validated_data.get('point_comment', '').strip()

        user = User.objects.get(username=username)
        expires_at = timezone.now() + timedelta(days=days)

        license_key = LicenseKey.objects.create(
            user=user,
            point_comment=point_comment,
            expires_at=expires_at,
            is_active=True,
        )

        return Response({
            'status': 'created',
            'key': str(license_key.key),
            'number': license_key.display_number,
            'username': user.username,
            'expires_at': expires_at,
            'days': days
        }, status=status.HTTP_201_CREATED)


# ============================================================
# ЛИЧНЫЙ КАБИНЕТ
# ============================================================

def ensure_superuser(user):
    if not user.is_superuser:
        raise PermissionDenied


def parse_selector_lines(selectors_text):
    selectors = [
        line.strip()
        for line in (selectors_text or '').splitlines()
        if line.strip()
    ]
    if selectors:
        return selectors[:20]
    return [
        line.strip()
        for line in DEFAULT_CELL_SELECTORS.splitlines()
        if line.strip()
    ]


def value_or_selector(value, template):
    value = (value or '').strip()
    if not value:
        return ''
    if value.startswith(('[', '.', '#')):
        return value
    escaped = value.replace('"', '\\"')
    return template.format(value=escaped)


def get_cell_selectors(settings_obj):
    selectors = [
        value_or_selector(settings_obj.cell_number_class, '[class="{value}"]'),
        value_or_selector(settings_obj.cell_number_data_testid, '[data-testid="{value}"]'),
        value_or_selector(settings_obj.cell_number_id, '#{value}'),
        (settings_obj.cell_extra_selector or '').strip(),
    ]
    selectors = [selector for selector in selectors if selector]
    if selectors:
        return selectors[:20]
    return parse_selector_lines(settings_obj.cell_selectors)


def account_context(request, **extra):
    service_settings = ServiceSettings.load()
    billing = balance_summary(request.user)
    active_tokens_count = request.user.licenses.filter(is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).count()
    download_path = reverse('download')
    notifications = ServiceNotification.objects.filter(
        is_enabled=True,
    ).exclude(text='').order_by('-updated_at', '-created_at')
    context = {
        'service_settings': service_settings,
        'billing_account': billing['account'],
        'account_balance': billing['balance_display'],
        'account_balance_kopecks': billing['balance_kopecks'],
        'active_tokens_count': active_tokens_count,
        'download_url': download_path,
        'download_qr_url': reverse('download_qr'),
        'account_notifications': notifications,
    }
    context.update(extra)
    return context


def with_user_token_sequence(queryset):
    """Annotate licenses with their per-user display sequence."""
    return queryset.annotate(
        user_token_sequence=Window(
            expression=RowNumber(),
            partition_by=[F('user_id')],
            order_by=[F('created_at').asc(), F('id').asc()],
        )
    )


@login_required
def account_dashboard(request):
    """Личный кабинет: список ключей."""
    licenses = with_user_token_sequence(
        request.user.licenses.all(),
    ).order_by('-created_at', '-id')
    return render(request, 'licenses/account/dashboard.html', account_context(
        request,
        licenses=licenses,
        account_nav='tokens',
    ))


@login_required
def payment_history(request):
    """История операций по внутреннему счёту."""
    ledger_entries = request.user.ledger_entries.select_related(
        'license_key',
        'payment',
    ).order_by('-created_at', '-id')
    return render(request, 'licenses/account/payments.html', account_context(
        request,
        ledger_entries=ledger_entries,
        account_nav='payments',
    ))


@login_required
def top_up_balance_view(request):
    """Пополнение внутреннего счёта и настройка автопополнения."""
    recurring_settings, _ = RecurringTopUpSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST' and request.POST.get('form_kind') == 'recurring':
        recurring_form = RecurringTopUpForm(request.POST, instance=recurring_settings)
        top_up_form = TopUpBalanceForm()
        if recurring_form.is_valid():
            recurring_form.save()
            return redirect('top_up_balance')
    elif request.method == 'POST':
        top_up_form = TopUpBalanceForm(request.POST)
        recurring_form = RecurringTopUpForm(instance=recurring_settings)
        if top_up_form.is_valid():
            payment = Payment.objects.create(
                user=request.user,
                amount=top_up_form.cleaned_data['amount_rubles'],
                days=0,
                operation_type='top_up',
                status='pending',
                provider='yookassa',
                save_payment_method=top_up_form.cleaned_data['save_payment_method'],
                metadata={'mock_checkout': True},
            )
            payment.gateway_payment_id = f'mock-yookassa-{payment.id}'
            payment.status = 'succeeded'
            payment.paid_at = timezone.now()
            payment.save(update_fields=['gateway_payment_id', 'status', 'paid_at'])
            apply_top_up_balance(
                request.user,
                top_up_form.amount_kopecks,
                payment=payment,
                operation_type='top_up',
                comment='Пополнение баланса через ЮKassa',
            )
            return redirect('payment_history')
    else:
        top_up_form = TopUpBalanceForm()
        recurring_form = RecurringTopUpForm(instance=recurring_settings)

    return render(request, 'licenses/account/balance.html', account_context(
        request,
        top_up_form=top_up_form,
        recurring_form=recurring_form,
        recurring_settings=recurring_settings,
        account_nav='payments',
    ))


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
        point_comment = request.POST.get('point_comment', '').strip()
        pricing = get_pricing_options()
        if days not in pricing:
            messages.error(request, 'Неверный тариф')
            return redirect('account_dashboard')
        payment_flow = request.POST.get('payment_flow', 'provider')
        save_payment_method = bool(request.POST.get('save_payment_method'))

        try:
            if payment_flow == 'balance':
                purchase_token_from_balance(
                    request.user,
                    days=days,
                    license_key=license_key,
                    point_comment=point_comment if is_new else None,
                )
            else:
                purchase_token_via_external_payment(
                    request.user,
                    days=days,
                    license_key=license_key,
                    point_comment=point_comment if is_new else None,
                    save_payment_method=save_payment_method,
                )
        except InsufficientBalance:
            messages.error(request, 'Недостаточно средств на балансе.')
            if key_id:
                return redirect('buy_license', key_id)
            return redirect('buy_new_license')

        return redirect('account_dashboard')

    pricing = get_pricing_options()
    return render(request, 'licenses/account/buy.html', account_context(
        request,
        license_key=license_key,
        is_new=is_new,
        pricing=pricing,
        account_nav='tokens',
    ))


@login_required
def edit_license_point(request, key_id):
    """Редактирование адреса пункта выдачи или комментария к токену."""
    license_key = get_object_or_404(LicenseKey, id=key_id, user=request.user)

    if request.method == 'POST':
        form = LicensePointForm(request.POST, instance=license_key)
        if form.is_valid():
            form.save()
            return redirect('account_dashboard')
    else:
        form = LicensePointForm(instance=license_key)

    return render(request, 'licenses/account/license_point_form.html', account_context(
        request,
        form=form,
        license_key=license_key,
        account_nav='tokens',
    ))


@login_required
@require_POST
def toggle_license_auto_renew(request, key_id):
    """Включение или выключение автопродления токена."""
    license_key = get_object_or_404(LicenseKey, id=key_id, user=request.user)
    license_key.auto_renew_enabled = not license_key.auto_renew_enabled
    license_key.save(update_fields=['auto_renew_enabled'])
    return redirect('account_dashboard')


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

    return render(request, 'licenses/account/deactivate.html', account_context(
        request,
        license_key=license_key,
        account_nav='tokens',
    ))


@login_required
def service_settings(request):
    """Настройки сервиса для суперпользователя."""
    ensure_superuser(request.user)

    settings_obj = ServiceSettings.load()
    if request.method == 'POST':
        form = ServiceSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Настройки сохранены.')
            return redirect('service_settings')
    else:
        form = ServiceSettingsForm(instance=settings_obj)

    return render(request, 'licenses/account/service_settings.html', account_context(
        request,
        form=form,
        account_nav='settings',
    ))


@login_required
def account_admin_users(request):
    """Управление пользователями в интерфейсе личного кабинета."""
    ensure_superuser(request.user)
    query = request.GET.get('q', '').strip()
    users = User.objects.select_related('billing_account').annotate(
        licenses_count=Count('licenses', distinct=True),
        payments_count=Count('payments', distinct=True),
    ).order_by('-date_joined', '-id')
    if query:
        user_filter = (
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
        if query.isdigit():
            user_filter |= Q(id=int(query))
        users = users.filter(user_filter)

    return render(request, 'licenses/account/admin_users.html', account_context(
        request,
        users=users,
        query=query,
        account_nav='admin_users',
    ))


@login_required
def account_admin_user_create(request):
    """Создание пользователя суперадмином."""
    ensure_superuser(request.user)
    if request.method == 'POST':
        form = AdminUserForm(request.POST, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Пользователь создан.')
            return redirect('account_admin_users')
    else:
        form = AdminUserForm(initial={'is_active': True}, request_user=request.user)

    return render(request, 'licenses/account/admin_user_form.html', account_context(
        request,
        form=form,
        form_title='Новый пользователь',
        submit_label='Создать пользователя',
        account_nav='admin_users',
    ))


@login_required
def account_admin_user_edit(request, user_id):
    """Редактирование пользователя суперадмином."""
    ensure_superuser(request.user)
    target_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = AdminUserForm(request.POST, instance=target_user, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Пользователь сохранён.')
            return redirect('account_admin_users')
    else:
        form = AdminUserForm(instance=target_user, request_user=request.user)

    return render(request, 'licenses/account/admin_user_form.html', account_context(
        request,
        form=form,
        target_user=target_user,
        form_title='Редактировать пользователя',
        submit_label='Сохранить пользователя',
        account_nav='admin_users',
    ))


@login_required
def account_admin_user_delete(request, user_id):
    """Удаление пользователя суперадмином."""
    ensure_superuser(request.user)
    target_user = get_object_or_404(User, id=user_id)
    if target_user.id == request.user.id:
        messages.error(request, 'Нельзя удалить свой аккаунт.')
        return redirect('account_admin_users')

    if request.method == 'POST':
        target_user.delete()
        messages.success(request, 'Пользователь удалён.')
        return redirect('account_admin_users')

    return render(request, 'licenses/account/admin_confirm_delete.html', account_context(
        request,
        title='Удалить пользователя?',
        object_label=target_user.get_username(),
        warning='Будут удалены связанные лицензии и платежи этого пользователя.',
        cancel_url=reverse('account_admin_users'),
        account_nav='admin_users',
    ))


@login_required
def account_admin_licenses(request):
    """Управление лицензиями в интерфейсе личного кабинета."""
    ensure_superuser(request.user)
    query = request.GET.get('q', '').strip()
    licenses = LicenseKey.objects.select_related('user').prefetch_related(
        'activations',
    ).order_by('-created_at', '-id')
    if query:
        license_filter = (
            Q(key__icontains=query)
            | Q(point_comment__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
        )
        if query.isdigit():
            license_filter |= Q(id=int(query)) | Q(user_id=int(query))
        licenses = licenses.filter(license_filter)

    return render(request, 'licenses/account/admin_licenses.html', account_context(
        request,
        licenses=licenses,
        query=query,
        account_nav='admin_licenses',
    ))


@login_required
def account_admin_license_create(request):
    """Создание лицензии суперадмином."""
    ensure_superuser(request.user)
    if request.method == 'POST':
        form = AdminLicenseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Лицензия создана.')
            return redirect('account_admin_licenses')
    else:
        form = AdminLicenseForm(initial={'is_active': True})

    return render(request, 'licenses/account/admin_license_form.html', account_context(
        request,
        form=form,
        form_title='Новая лицензия',
        submit_label='Создать лицензию',
        account_nav='admin_licenses',
    ))


@login_required
def account_admin_license_edit(request, license_id):
    """Редактирование лицензии суперадмином."""
    ensure_superuser(request.user)
    license_key = get_object_or_404(LicenseKey, id=license_id)
    if request.method == 'POST':
        form = AdminLicenseForm(request.POST, instance=license_key)
        if form.is_valid():
            form.save()
            messages.success(request, 'Лицензия сохранена.')
            return redirect('account_admin_licenses')
    else:
        form = AdminLicenseForm(instance=license_key)

    return render(request, 'licenses/account/admin_license_form.html', account_context(
        request,
        form=form,
        license_key=license_key,
        form_title='Редактировать лицензию',
        submit_label='Сохранить лицензию',
        account_nav='admin_licenses',
    ))


@login_required
def account_admin_license_delete(request, license_id):
    """Удаление лицензии суперадмином."""
    ensure_superuser(request.user)
    license_key = get_object_or_404(LicenseKey, id=license_id)
    if request.method == 'POST':
        license_key.delete()
        messages.success(request, 'Лицензия удалена.')
        return redirect('account_admin_licenses')

    return render(request, 'licenses/account/admin_confirm_delete.html', account_context(
        request,
        title='Удалить лицензию?',
        object_label=str(license_key.key),
        warning='Привязки этой лицензии будут удалены, связанные платежи останутся без лицензии.',
        cancel_url=reverse('account_admin_licenses'),
        account_nav='admin_licenses',
    ))


@login_required
def account_admin_payments(request):
    """Управление платежами в интерфейсе личного кабинета."""
    ensure_superuser(request.user)
    query = request.GET.get('q', '').strip()
    payments = Payment.objects.select_related('user', 'license_key').order_by('-created_at', '-id')
    if query:
        payment_filter = (
            Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
            | Q(gateway_payment_id__icontains=query)
            | Q(operation_type__icontains=query)
            | Q(provider__icontains=query)
            | Q(license_key__key__icontains=query)
        )
        if query.isdigit():
            payment_filter |= Q(id=int(query)) | Q(user_id=int(query))
        payments = payments.filter(payment_filter)

    return render(request, 'licenses/account/admin_payments.html', account_context(
        request,
        payments=payments,
        query=query,
        account_nav='admin_payments',
    ))


@login_required
def account_admin_payment_create(request):
    """Создание платежа суперадмином."""
    ensure_superuser(request.user)
    if request.method == 'POST':
        form = AdminPaymentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Платёж создан.')
            return redirect('account_admin_payments')
    else:
        form = AdminPaymentForm(initial={'days': 30, 'status': 'pending'})

    return render(request, 'licenses/account/admin_payment_form.html', account_context(
        request,
        form=form,
        form_title='Новый платёж',
        submit_label='Создать платёж',
        account_nav='admin_payments',
    ))


@login_required
def account_admin_payment_edit(request, payment_id):
    """Редактирование платежа суперадмином."""
    ensure_superuser(request.user)
    payment = get_object_or_404(Payment, id=payment_id)
    if request.method == 'POST':
        form = AdminPaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Платёж сохранён.')
            return redirect('account_admin_payments')
    else:
        form = AdminPaymentForm(instance=payment)

    return render(request, 'licenses/account/admin_payment_form.html', account_context(
        request,
        form=form,
        payment=payment,
        form_title='Редактировать платёж',
        submit_label='Сохранить платёж',
        account_nav='admin_payments',
    ))


@login_required
def account_admin_payment_delete(request, payment_id):
    """Удаление платежа суперадмином."""
    ensure_superuser(request.user)
    payment = get_object_or_404(Payment, id=payment_id)
    if request.method == 'POST':
        payment.delete()
        messages.success(request, 'Платёж удалён.')
        return redirect('account_admin_payments')

    return render(request, 'licenses/account/admin_confirm_delete.html', account_context(
        request,
        title='Удалить платёж?',
        object_label=f'Платёж #{payment.id}',
        warning='Запись платежа будет удалена из истории.',
        cancel_url=reverse('account_admin_payments'),
        account_nav='admin_payments',
    ))


@login_required
def service_notifications(request):
    """Список уведомлений сервиса для суперпользователя."""
    ensure_superuser(request.user)
    notifications = ServiceNotification.objects.all()
    return render(request, 'licenses/account/notifications.html', account_context(
        request,
        notifications=notifications,
        account_nav='notifications',
    ))


@login_required
def notification_create(request):
    """Создание уведомления сервиса."""
    ensure_superuser(request.user)
    if request.method == 'POST':
        form = ServiceNotificationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Уведомление добавлено.')
            return redirect('service_notifications')
    else:
        form = ServiceNotificationForm(initial={'is_enabled': True})

    return render(request, 'licenses/account/notification_form.html', account_context(
        request,
        form=form,
        form_title='Новое уведомление',
        submit_label='Добавить уведомление',
        account_nav='notifications',
    ))


@login_required
def notification_edit(request, notification_id):
    """Редактирование уведомления сервиса."""
    ensure_superuser(request.user)
    notification = get_object_or_404(ServiceNotification, id=notification_id)
    if request.method == 'POST':
        form = ServiceNotificationForm(request.POST, instance=notification)
        if form.is_valid():
            form.save()
            messages.success(request, 'Уведомление сохранено.')
            return redirect('service_notifications')
    else:
        form = ServiceNotificationForm(instance=notification)

    return render(request, 'licenses/account/notification_form.html', account_context(
        request,
        form=form,
        notification=notification,
        form_title='Редактировать уведомление',
        submit_label='Сохранить уведомление',
        account_nav='notifications',
    ))


@login_required
def notification_delete(request, notification_id):
    """Удаление уведомления сервиса."""
    ensure_superuser(request.user)
    notification = get_object_or_404(ServiceNotification, id=notification_id)
    if request.method == 'POST':
        notification.delete()
        messages.success(request, 'Уведомление удалено.')
        return redirect('service_notifications')

    return render(request, 'licenses/account/notification_confirm_delete.html', account_context(
        request,
        notification=notification,
        account_nav='notifications',
    ))


@login_required
@require_POST
def notification_toggle(request, notification_id):
    """Включение или выключение уведомления сервиса."""
    ensure_superuser(request.user)
    notification = get_object_or_404(ServiceNotification, id=notification_id)
    notification.is_enabled = not notification.is_enabled
    notification.save(update_fields=['is_enabled', 'updated_at'])
    messages.success(
        request,
        'Уведомление включено.' if notification.is_enabled else 'Уведомление отключено.'
    )
    return redirect('service_notifications')


def extension_config(request):
    """Конфиг браузерного расширения, управляемый из настроек сервиса."""
    settings_obj = ServiceSettings.load()
    return JsonResponse({
        'version': 1,
        'ttlSeconds': 21600,
        'serviceName': settings_obj.service_name or 'Magic ПВЗ',
        'minExtensionVersion': '0.1.0',
        'latestVersion': '0.1.0',
        'updateMessage': '',
        'printUrl': 'http://localhost:80/Integration/HTTPLabelPrint/Execute',
        'minCellToPrint': 1,
        'hotkey': 'Pause',
        'selectors': get_cell_selectors(settings_obj),
    })


@login_required
def download_qr(request):
    """SVG QR-code со ссылкой на скачивание программы."""
    download_url = request.build_absolute_uri(reverse('download'))
    return svg_qr_response(download_url)


@login_required
def license_token_qr(request, key_id):
    """SVG QR-code с самим токеном пользователя."""
    queryset = LicenseKey.objects.all()
    if not request.user.is_superuser:
        queryset = queryset.filter(user=request.user)
    license_key = get_object_or_404(queryset, id=key_id)
    return svg_qr_response(str(license_key.key))


@login_required
def license_token_qr_png(request, key_id):
    """PNG QR-code с самим токеном пользователя для скачивания и шаринга."""
    queryset = LicenseKey.objects.all()
    if not request.user.is_superuser:
        queryset = queryset.filter(user=request.user)
    license_key = get_object_or_404(queryset, id=key_id)
    return png_qr_response(str(license_key.key))


def svg_qr_response(value):
    """Render a compact SVG QR response for the provided value."""
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError:
        return HttpResponse(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120">'
            '<rect width="120" height="120" fill="#fff"/>'
            '<text x="60" y="64" text-anchor="middle" font-size="16" fill="#111">QR</text>'
            '</svg>',
            content_type='image/svg+xml',
        )

    image = qrcode.make(value, image_factory=SvgPathImage, box_size=10)
    response = HttpResponse(content_type='image/svg+xml')
    image.save(response)
    return response


def png_qr_response(value):
    """Render QR as PNG so mobile share dialogs receive an image file."""
    import qrcode

    image = qrcode.make(value, box_size=10, border=4)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return HttpResponse(buffer.getvalue(), content_type='image/png')


def register(request):
    """Регистрация нового пользователя."""
    if request.user.is_authenticated:
        return redirect('account_dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # сразу авторизуем
            messages.success(request, 'Регистрация успешна! Добро пожаловать.')
            return redirect('account_dashboard')
    else:
        form = RegisterForm()

    return render(request, 'licenses/auth/register.html', {'form': form})

def create_or_extend_license(payment, point_comment=None):
    """Создаёт новую лицензию или продлевает существующую по платежу."""
    license_key = create_or_extend_license_for_user(
        payment.user,
        payment.days,
        license_key=payment.license_key,
        point_comment=point_comment,
    )
    if payment.license_key_id != license_key.id:
        payment.license_key = license_key
        payment.save(update_fields=['license_key'])
    return license_key
