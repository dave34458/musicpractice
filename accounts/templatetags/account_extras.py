import math
from django import template

register = template.Library()


@register.filter
def duration_display(seconds):
    if not seconds:
        return '—'
    seconds = int(seconds)
    m = seconds // 60
    s = seconds % 60
    return f'{m}:{s:02d}'


@register.filter
def percentage(value, total):
    if not total:
        return 0
    return round(value / total * 100)
