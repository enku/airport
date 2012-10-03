"""
Template tags for message templates
"""
from __future__ import unicode_literals

from django import template

from airport.context_processors import externals

register = template.Library()


@register.filter
def sound(message):
    """return the sound url for a given message"""
    ext = externals(None)
    return ext.get(
        'message_{mtype}_sound'.format(mtype=message.message_type),
        ext['message_DEFAULT_sound']
    )


@register.filter
def icon(message):
    """Return the icon url for a given message"""
    ext = externals(None)
    return ext.get(
        'message_{mtype}_icon'.format(mtype=message.message_type),
        ext['message_DEFAULT_icon']
    )
