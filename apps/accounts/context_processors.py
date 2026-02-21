"""
Template context processors for the accounts app.
"""

from .permissions import is_editor as _is_editor


def editor_context(request):
    """Add is_editor boolean to every template context."""
    if hasattr(request, "user") and request.user.is_authenticated:
        return {"is_editor": _is_editor(request.user)}
    return {"is_editor": False}
