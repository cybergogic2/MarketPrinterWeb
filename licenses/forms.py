from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q
from django.utils import timezone
import re

from .billing import rubles_to_kopecks
from .models import (
    LicenseKey,
    Payment,
    RecurringTopUpSettings,
    ServiceNotification,
    ServiceSettings,
)


DATETIME_INPUT_FORMAT = '%Y-%m-%dT%H:%M'


def format_user_search_option(user):
    label = user.get_username()
    if user.email:
        label = f'{label} — {user.email}'
    return f'{label} (#{user.id})'


def resolve_user_search_query(query):
    query = (query or '').strip()
    if not query:
        raise forms.ValidationError('Выберите пользователя.')

    id_match = re.search(r'#(\d+)\)?$', query)
    if id_match:
        user = User.objects.filter(id=int(id_match.group(1))).first()
        if user:
            return user

    users = User.objects.filter(Q(username__iexact=query) | Q(email__iexact=query))
    if users.count() == 1:
        return users.first()

    username = query.split(' — ', 1)[0].strip()
    user = User.objects.filter(username__iexact=username).first()
    if user:
        return user

    raise forms.ValidationError('Пользователь не найден. Выберите вариант из подсказки.')


def user_search_field():
    return forms.CharField(
        label='Пользователь',
        widget=forms.TextInput(attrs={
            'class': 'account-input',
            'autocomplete': 'off',
            'placeholder': 'Начните вводить логин или email',
        }),
    )


class SearchableUserFieldMixin:
    user_datalist_id = 'account-user-options'

    def setup_user_search_field(self, selected_user=None):
        self.user_options = list(User.objects.order_by('username', 'id'))
        self.fields['user_query'].widget.attrs['list'] = self.user_datalist_id
        if selected_user and not self.is_bound:
            self.fields['user_query'].initial = format_user_search_option(selected_user)

    def clean_user_query(self):
        user = resolve_user_search_query(self.cleaned_data.get('user_query'))
        self.cleaned_data['user'] = user
        return self.cleaned_data['user_query']


class RegisterForm(UserCreationForm):
    """Форма регистрации нового пользователя."""
    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 focus:border-brand-500 outline-none'
        })
    )
    username = forms.CharField(
        label='Логин',
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 focus:border-brand-500 outline-none'
        })
    )
    password1 = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 focus:border-brand-500 outline-none'
        })
    )
    password2 = forms.CharField(
        label='Повторите пароль',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 focus:border-brand-500 outline-none'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Пользователь с таким email уже существует')
        return email


class ServiceSettingsForm(forms.ModelForm):
    """Форма настроек, доступная только суперпользователю."""

    class Meta:
        model = ServiceSettings
        fields = (
            'service_name',
            'token_price',
            'company_name',
            'ogrnip',
            'inn',
            'bank_name',
            'bik',
            'bank_account',
            'telegram_url',
            'max_url',
            'support_email',
            'support_phone',
            'cell_number_class',
            'cell_number_data_testid',
            'cell_number_id',
            'cell_extra_selector',
        )
        labels = {
            'service_name': 'Название сервиса',
            'token_price': 'Стоимость токена',
            'company_name': 'ИП',
            'ogrnip': 'ОГРНИП',
            'inn': 'ИНН',
            'bank_name': 'Банк',
            'bik': 'БИК',
            'bank_account': 'Счёт',
            'telegram_url': 'Telegram',
            'max_url': 'MAX',
            'support_email': 'E-mail',
            'support_phone': 'Телефон',
            'cell_number_class': 'Класс элемента с номером ячейки',
            'cell_number_data_testid': 'data-testid элемента с номером ячейки',
            'cell_number_id': 'ID элемента с номером ячейки',
            'cell_extra_selector': 'Дополнительный CSS-селектор',
        }
        help_texts = {
            'cell_number_class': (
                'Например: _shelfTag_1tkm1_2 ozi-heading-500 _shelfTag_jn3ur_21.'
            ),
            'cell_number_data_testid': (
                'Например: logItemPlace.'
            ),
            'cell_number_id': (
                'Если у элемента есть id, укажите его без #.'
            ),
            'cell_extra_selector': (
                'Для нестандартного случая можно указать полный CSS-селектор.'
            ),
        }
        widgets = {
            'service_name': forms.TextInput(attrs={'class': 'account-input'}),
            'token_price': forms.NumberInput(attrs={
                'class': 'account-input',
                'min': '0',
                'step': '1',
                'inputmode': 'numeric',
            }),
            'company_name': forms.TextInput(attrs={'class': 'account-input'}),
            'ogrnip': forms.TextInput(attrs={'class': 'account-input'}),
            'inn': forms.TextInput(attrs={'class': 'account-input'}),
            'bank_name': forms.TextInput(attrs={'class': 'account-input'}),
            'bik': forms.TextInput(attrs={'class': 'account-input'}),
            'bank_account': forms.TextInput(attrs={'class': 'account-input'}),
            'telegram_url': forms.URLInput(attrs={'class': 'account-input'}),
            'max_url': forms.URLInput(attrs={'class': 'account-input'}),
            'support_email': forms.EmailInput(attrs={'class': 'account-input'}),
            'support_phone': forms.TextInput(attrs={'class': 'account-input'}),
            'cell_number_class': forms.TextInput(attrs={'class': 'account-input account-code-input'}),
            'cell_number_data_testid': forms.TextInput(attrs={'class': 'account-input account-code-input'}),
            'cell_number_id': forms.TextInput(attrs={'class': 'account-input account-code-input'}),
            'cell_extra_selector': forms.TextInput(attrs={'class': 'account-input account-code-input'}),
        }


class ServiceNotificationForm(forms.ModelForm):
    """Форма уведомления, доступная только суперпользователю."""

    class Meta:
        model = ServiceNotification
        fields = ('title', 'text', 'is_enabled')
        labels = {
            'title': 'Заголовок',
            'text': 'Текст уведомления',
            'is_enabled': 'Показывать пользователям',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'account-input'}),
            'text': forms.Textarea(attrs={'class': 'account-input account-textarea', 'rows': 5}),
            'is_enabled': forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
        }


class LicensePointForm(forms.ModelForm):
    """Форма адреса пункта выдачи или комментария к токену."""

    class Meta:
        model = LicenseKey
        fields = ('point_comment',)
        labels = {
            'point_comment': 'Адрес пункта выдачи / комментарий',
        }
        widgets = {
            'point_comment': forms.Textarea(attrs={
                'class': 'account-input account-textarea',
                'rows': 3,
                'placeholder': 'Например: ПВЗ на Ленина, 12 или внутренний комментарий',
            }),
        }


class TopUpBalanceForm(forms.Form):
    """Форма пополнения внутреннего счёта."""
    amount_rubles = forms.IntegerField(
        label='Сумма пополнения',
        min_value=1,
        max_value=500000,
        widget=forms.NumberInput(attrs={
            'class': 'account-input',
            'min': '1',
            'step': '1',
            'inputmode': 'numeric',
        }),
    )
    save_payment_method = forms.BooleanField(
        label='Сохранить способ оплаты для автоплатежей',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
    )

    @property
    def amount_kopecks(self):
        return rubles_to_kopecks(self.cleaned_data['amount_rubles'])


class RecurringTopUpForm(forms.ModelForm):
    """Настройки регулярного пополнения баланса."""
    amount_rubles = forms.IntegerField(
        label='Сумма автопополнения',
        required=False,
        min_value=1,
        max_value=500000,
        widget=forms.NumberInput(attrs={
            'class': 'account-input',
            'min': '1',
            'step': '1',
            'inputmode': 'numeric',
        }),
    )

    class Meta:
        model = RecurringTopUpSettings
        fields = ('is_enabled', 'amount_rubles')
        labels = {
            'is_enabled': 'Включить автопополнение',
        }
        widgets = {
            'is_enabled': forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.amount_kopecks:
            self.fields['amount_rubles'].initial = self.instance.amount_kopecks // 100

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_enabled') and not cleaned_data.get('amount_rubles'):
            self.add_error('amount_rubles', 'Укажите сумму автопополнения.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        amount_rubles = self.cleaned_data.get('amount_rubles')
        instance.amount_kopecks = rubles_to_kopecks(amount_rubles or 0)
        if commit:
            instance.save()
        return instance


class AdminUserForm(forms.ModelForm):
    """Форма управления пользователем в новом ЛК."""
    password1 = forms.CharField(
        label='Новый пароль',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'account-input', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Повторите пароль',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'account-input', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'is_staff',
            'is_superuser',
        )
        labels = {
            'username': 'Логин',
            'email': 'E-mail',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'is_active': 'Активен',
            'is_staff': 'Доступ в Django admin',
            'is_superuser': 'Суперадмин',
        }
        widgets = {
            'username': forms.TextInput(attrs={'class': 'account-input'}),
            'email': forms.EmailInput(attrs={'class': 'account-input'}),
            'first_name': forms.TextInput(attrs={'class': 'account-input'}),
            'last_name': forms.TextInput(attrs={'class': 'account-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
        }

    def __init__(self, *args, request_user=None, **kwargs):
        self.request_user = request_user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if not self.instance.pk and not password1:
            self.add_error('password1', 'Укажите пароль для нового пользователя.')

        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', 'Пароли не совпадают.')
            else:
                password_validation.validate_password(password1, self.instance)

        if self.instance.pk and self.request_user and self.instance.pk == self.request_user.pk:
            if not cleaned_data.get('is_active'):
                self.add_error('is_active', 'Нельзя отключить свой аккаунт.')
            if not cleaned_data.get('is_superuser'):
                self.add_error('is_superuser', 'Нельзя снять с себя права суперадмина.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('is_superuser'):
            user.is_staff = True
        password = self.cleaned_data.get('password1')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class AdminLicenseForm(SearchableUserFieldMixin, forms.ModelForm):
    """Форма управления лицензией."""
    user_query = user_search_field()
    expires_at = forms.DateTimeField(
        label='Истекает',
        required=False,
        input_formats=[DATETIME_INPUT_FORMAT],
        widget=forms.DateTimeInput(
            attrs={'class': 'account-input', 'type': 'datetime-local'},
            format=DATETIME_INPUT_FORMAT,
        ),
    )

    class Meta:
        model = LicenseKey
        fields = ('user_query', 'point_comment', 'is_active', 'expires_at')
        labels = {
            'point_comment': 'Адрес пункта выдачи / комментарий',
            'is_active': 'Активна',
        }
        widgets = {
            'point_comment': forms.Textarea(attrs={
                'class': 'account-input account-textarea',
                'rows': 3,
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        selected_user = self.instance.user if self.instance and self.instance.pk else None
        self.setup_user_search_field(selected_user=selected_user)

    def save(self, commit=True):
        license_key = super().save(commit=False)
        license_key.user = self.cleaned_data['user']
        if commit:
            license_key.save()
            self.save_m2m()
        return license_key


class AdminPaymentForm(SearchableUserFieldMixin, forms.ModelForm):
    """Форма управления платежом."""
    user_query = user_search_field()
    license_key = forms.ModelChoiceField(
        label='Лицензия',
        queryset=LicenseKey.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'account-input'}),
    )
    paid_at = forms.DateTimeField(
        label='Оплачен',
        required=False,
        input_formats=[DATETIME_INPUT_FORMAT],
        widget=forms.DateTimeInput(
            attrs={'class': 'account-input', 'type': 'datetime-local'},
            format=DATETIME_INPUT_FORMAT,
        ),
    )

    class Meta:
        model = Payment
        fields = (
            'user_query',
            'license_key',
            'operation_type',
            'amount',
            'days',
            'status',
            'provider',
            'gateway_payment_id',
            'confirmation_url',
            'save_payment_method',
            'paid_at',
        )
        labels = {
            'license_key': 'Лицензия',
            'operation_type': 'Тип операции',
            'amount': 'Сумма',
            'days': 'Дней',
            'status': 'Статус',
            'provider': 'Провайдер',
            'gateway_payment_id': 'ID платежа в шлюзе',
            'confirmation_url': 'Ссылка подтверждения',
            'save_payment_method': 'Сохранить способ оплаты',
        }
        widgets = {
            'license_key': forms.Select(attrs={'class': 'account-input'}),
            'operation_type': forms.Select(attrs={'class': 'account-input'}),
            'amount': forms.NumberInput(attrs={
                'class': 'account-input',
                'min': '0',
                'step': '0.01',
                'inputmode': 'decimal',
            }),
            'days': forms.NumberInput(attrs={'class': 'account-input', 'min': '1', 'step': '1'}),
            'status': forms.Select(attrs={'class': 'account-input'}),
            'provider': forms.TextInput(attrs={'class': 'account-input'}),
            'gateway_payment_id': forms.TextInput(attrs={'class': 'account-input'}),
            'confirmation_url': forms.URLInput(attrs={'class': 'account-input'}),
            'save_payment_method': forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
        }

    def save(self, commit=True):
        payment = super().save(commit=False)
        payment.user = self.cleaned_data['user']
        if payment.status == 'succeeded' and not payment.paid_at:
            payment.paid_at = timezone.now()
        if payment.status != 'succeeded':
            payment.paid_at = self.cleaned_data.get('paid_at')
        if commit:
            payment.save()
        return payment

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        selected_user = self.instance.user if self.instance and self.instance.pk else None
        self.setup_user_search_field(selected_user=selected_user)
        self.fields['license_key'].queryset = LicenseKey.objects.select_related(
            'user',
        ).order_by('-created_at', '-id')


class AdminManualTopUpForm(SearchableUserFieldMixin, forms.Form):
    """Ручное пополнение баланса пользователя суперадмином."""
    user_query = user_search_field()
    amount_rubles = forms.IntegerField(
        label='Сумма пополнения',
        min_value=1,
        max_value=500000,
        widget=forms.NumberInput(attrs={
            'class': 'account-input',
            'min': '1',
            'step': '1',
            'inputmode': 'numeric',
        }),
    )
    comment = forms.CharField(
        label='Комментарий',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'account-input account-textarea',
            'rows': 3,
            'placeholder': 'Например: оплата по счёту, корректировка баланса',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_user_search_field()

    @property
    def amount_kopecks(self):
        return rubles_to_kopecks(self.cleaned_data['amount_rubles'])
