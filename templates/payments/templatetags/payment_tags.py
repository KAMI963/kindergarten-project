from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу в шаблоне"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, None)
    return None