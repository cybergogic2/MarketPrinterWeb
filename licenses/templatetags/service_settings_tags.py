from types import SimpleNamespace

from django import template

from licenses.models import ServiceSettings


register = template.Library()


@register.simple_tag
def current_service_settings():
    try:
        return ServiceSettings.load()
    except Exception:
        return SimpleNamespace(service_name='Magic ПВЗ')
