"""Airport Library package"""
from django.contrib.sessions.models import Session
from django.contrib.auth.models import User


def get_user_from_session_id(session_id):
    """Given the session_id, return the user associated with it.

    Raise User.DoesNotExist if session_id does not associate with a user.
    """
    try:
        session = Session.objects.get(session_key=session_id)
    except Session.DoesNotExist:
        raise User.DoesNotExist

    try:
        user_id = session.get_decoded().get('_auth_user_id')
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise
    return user
