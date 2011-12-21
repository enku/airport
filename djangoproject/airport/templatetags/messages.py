"""
Template tags for message templates
"""
from django import template

from airport.context_processors import externals

register = template.Library()

@register.filter
def sound(message):
    """return the sound url for a given message"""
    ext = externals(None)
    return ext.get('message_%s_sound' % message.message_type,
        ext['message_DEFAULT_sound'])

