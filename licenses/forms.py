from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import ServiceNotification, ServiceSettings


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
