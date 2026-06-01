# attendance/templatetags/attendance_tags.py
from django import template

register = template.Library()

@register.filter
def dict_key(d, key):
    """Получить значение из словаря по ключу"""
    return d.get(key)
