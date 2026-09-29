from django.contrib.auth import views as auth_views
from django.urls import path
from licenses.views import extension_config
from . import views

urlpatterns = [
    path('static/extension/pvz-extension-config.json', extension_config, name='extension_config_legacy'),
    path('', auth_views.LoginView.as_view(template_name='licenses/auth/login.html'), name='index'),
    path('download/', views.download_app, name='download'),
]
