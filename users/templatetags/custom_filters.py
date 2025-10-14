from django import template

register = template.Library()

@register.filter
def index(value, arg):
    """
    Returns the item at the given index in a list.
    Usage: {{ list|index:index }}
    """
    try:
        return value[arg]
    except (IndexError, TypeError):
        return None
