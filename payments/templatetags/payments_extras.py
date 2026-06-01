from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Получение значения из словаря по ключу
    Использование в шаблоне: {{ dictionary|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def get_attribute(obj, attr_name):
    """
    Получение атрибута объекта по имени
    Использование: {{ object|get_attribute:"field_name" }}
    """
    if obj is None:
        return None
    return getattr(obj, attr_name, None)


@register.filter
def multiply(value, arg):
    """
    Умножение: {{ value|multiply:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """
    Деление: {{ value|divide:arg }}
    """
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0
    


@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу в шаблоне"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, None)
    return None