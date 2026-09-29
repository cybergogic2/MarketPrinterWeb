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
            'cell_selectors',
        )
        labels = {
            'service_name': 'Название сервиса',
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
            'cell_selectors': 'Идентификаторы или классы ячейки',
        }
        help_texts = {
            'cell_selectors': (
                'Укажите CSS-селекторы по одному в строке. '
                'Они попадут в конфиг браузерного расширения.'
            ),
        }
        widgets = {
            'service_name': forms.TextInput(attrs={'class': 'account-input'}),
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
            'cell_selectors': forms.Textarea(attrs={
                'class': 'account-input account-textarea account-code-textarea',
                'rows': 5,
            }),
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
