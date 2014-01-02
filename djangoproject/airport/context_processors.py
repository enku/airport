"""
Context processors for the Airport app
"""

from .conf import settings


def game_name(request):
    return {'game_name': settings.GAME_NAME}


def externals(request):
    """External files, like javascript and images.  Stuff we want to use but
    not host ourselves"""
    context_extras = {}
    for external in settings.EXTERNALS:
        context_extras[external] = settings.EXTERNALS[external]

    return context_extras
