# staff/templatetags/staff_extras.py

from django import template

register = template.Library()


@register.filter
def getattr(obj, attr):
    """Получение атрибута объекта по имени"""
    try:
        return getattr(obj, attr, '')
    except:
        return ''


@register.filter
def add_str(value, arg):
    """Конкатенация строк"""
    return str(value) + str(arg)


@register.filter
def get_item(dictionary, key):
    """Получение значения из словаря по ключу"""
    try:
        if dictionary is None:
            return ''
        if key is None:
            return ''
        # Преобразуем key в строку для сравнения
        key_str = str(key)
        return dictionary.get(key_str, '')
    except Exception:
        return ''


@register.filter
def get_attendance_code(entry, day):
    """Фильтр для получения кода явки по дню"""
    try:
        if entry and day:
            field_name = f'day_{day}'
            return getattr(entry, field_name, 'V')
        return 'V'
    except Exception as e:
        print(f"Error in get_attendance_code: {e}")
        return 'V'


@register.filter
def get_attendance_display(entry, day):
    """Фильтр для получения отображаемого названия кода"""
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
            'DD': 'Диспансеризация',
            'G': 'Прогул',
            'NN': 'Неявка',
            'V': 'Выходной',
        }
        return codes.get(code, code)
    except Exception as e:
        print(f"Error in get_attendance_display: {e}")
        return ''