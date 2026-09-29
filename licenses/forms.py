from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import ServiceSettings


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
            'company_name',
            'inn',
            'ogrnip',
            'support_hours',
            'telegram_url',
            'whatsapp_url',
            'notice_enabled',
            'notice_title',
            'notice_text',
        )
        labels = {
            'company_name': 'Данные ИП',
            'inn': 'ИНН',
            'ogrnip': 'ОГРНИП',
            'support_hours': 'Время поддержки',
            'telegram_url': 'Ссылка на Telegram',
            'whatsapp_url': 'Ссылка на WhatsApp',
            'notice_enabled': 'Показывать важное уведомление',
            'notice_title': 'Заголовок уведомления',
            'notice_text': 'Текст уведомления',
        }
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'account-input'}),
            'inn': forms.TextInput(attrs={'class': 'account-input'}),
            'ogrnip': forms.TextInput(attrs={'class': 'account-input'}),
            'support_hours': forms.TextInput(attrs={'class': 'account-input'}),
            'telegram_url': forms.URLInput(attrs={'class': 'account-input'}),
            'whatsapp_url': forms.URLInput(attrs={'class': 'account-input'}),
            'notice_enabled': forms.CheckboxInput(attrs={'class': 'account-checkbox'}),
            'notice_title': forms.TextInput(attrs={'class': 'account-input'}),
            'notice_text': forms.Textarea(attrs={'class': 'account-input account-textarea', 'rows': 4}),
        }
