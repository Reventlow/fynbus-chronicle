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
    """CBV mixin that raises 403 for users in the Viewer group."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if hasattr(response, 'status_code') and response.status_code == 302:
            # LoginRequiredMixin redirect — let it pass through
            return response
        if not is_editor(request.user):
            raise PermissionDenied
        return response
