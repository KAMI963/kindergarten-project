# children/decorators.py
from django.views.decorators.clickjacking import xframe_options_exempt

def xframe_exempt(view_func):
    return xframe_options_exempt(view_func)
