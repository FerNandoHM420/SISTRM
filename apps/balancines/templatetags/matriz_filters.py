from django import template

register = template.Library()

@register.filter
def get_range(value):
    """Convierte un número en un rango para iterar"""
    try:
        return range(1, int(value) + 1)
    except (ValueError, TypeError):
        return range(0)

@register.filter
def multiply(value, arg):
    """Multiplica dos números"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def add(value, arg):
    """Suma dos números"""
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return 0