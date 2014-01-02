"""
Template tags for message templates
"""
from django import template

from airport.context_processors import externals

register = template.Library()
EXTERNALS = externals(None)
DEFAULT_SOUND = EXTERNALS['message_DEFAULT_sound']
DEFAULT_ICON = EXTERNALS['message_DEFAULT_icon']


@register.filter
def sound(message):
    """return the sound url for a given message"""
    message_sound = 'message_{0}_sound'.format(message.message_type)
    return EXTERNALS.get(message_sound, DEFAULT_SOUND)


@register.filter
def icon(message):
    """Return the icon url for a given message"""
    message_icon = 'message_{0}_icon'.format(message.message_type)
    return EXTERNALS.get(message_icon, DEFAULT_ICON)
