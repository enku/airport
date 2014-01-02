"""
Context processors for the Airport app
"""

from .conf import settings


def externals(request):
    """External files, like javascript and images.  Stuff we want to use but
    not host ourselves"""
    context_extras = {}
    for external in settings.EXTERNALS:
        context_extras[external] = settings.EXTERNALS[external]

    return context_extras
