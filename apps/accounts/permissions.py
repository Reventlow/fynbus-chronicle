"""
Permission utilities for role-based access control.

The "Viewer" group is the restricted group. Users in this group can only
read data. All other authenticated users have full access by default.
Staff users always have full access regardless of group membership.
"""

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin


def is_editor(user) -> bool:
    """Return False if user is in the Viewer group, True otherwise.

    Staff users always return True regardless of group membership.
    """
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return not user.groups.filter(name="Viewer").exists()


def editor_required(view_func):
    """Decorator for function-based views that raises 403 for viewers."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_editor(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped


class EditorRequiredMixin(LoginRequiredMixin):
    """CBV mixin that raises 403 for users in the Viewer group.

    The check runs *before* the view body. An earlier version called
    ``super().dispatch()`` first and only then tested the role, which meant
    a viewer's POST was executed — object created, updated or deleted — and
    the 403 was returned after the write had already landed.

    Anonymous users fall through to ``LoginRequiredMixin``, which redirects
    them to the login page rather than showing a 403.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_editor(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
