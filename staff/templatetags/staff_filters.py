# staff/templatetags/staff_filters.py
from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def get_attendance_code(entry, day):
    """
    Фильтр для получения кода явки из записи табеля
    Использование: {{ entry|get_attendance_code:day }}
    """
    try:
        # Пытаемся получить атрибут day_N
        day_field = f'day_{day}'
        if hasattr(entry, day_field):
            return getattr(entry, day_field)
        return 'V'  # По умолчанию выходной
    except (AttributeError, ValueError):
        return 'V'

@register.filter
def get_attendance_display(entry, day):
    """
    Фильтр для получения отображаемого названия кода
    """
    try:
        code = get_attendance_code(entry, day)
        codes = {
            'I': 'Явка',
            'N': 'Ночная',
            'RV': 'Выходной/праздник',
            'C': 'Сверхурочно',
            'B': 'Больничный',
            'OT': 'Отпуск',
            'OZ': 'Отпуск за свой счет',
            'UO': 'Учебный отпуск',
            'DO': 'Уход за ребенком',
            'K': 'Командировка',
            'G': 'Прогул',
            'NN': 'Неявка',
            'PR': 'Отстранение',
            'V': 'Выходной',
        }
        return codes.get(code, code)
    except:
        return ''

@register.filter
def get_attendance_color_class(code):
    """
    Фильтр для получения CSS класса по коду
    """
    colors = {
        'I': 'attendance-I',
        'N': 'attendance-N',
        'RV': 'attendance-RV',
        'C': 'attendance-C',
        'B': 'attendance-B',
        'OT': 'attendance-OT',
        'OZ': 'attendance-OZ',
        'G': 'attendance-G',
        'NN': 'attendance-NN',
        'V': 'attendance-V',
    }
    return colors.get(code, 'attendance-V')
