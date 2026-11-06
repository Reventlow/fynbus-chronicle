"""Authentication backends: password logins obey ``SSO_ONLY``.

With ``SSO_ONLY=True``, Chronicle accepts passwords only from the
break-glass accounts named in ``SSO_BREAK_GLASS_USERS`` (local accounts
kept for when Microsoft sign-in is unavailable). Everyone else signs in
with Microsoft, so MFA, Conditional Access and disabling an account in
Entra apply to Chronicle too.

The check sits in ``authenticate()``, which runs only when a password is
checked: Chronicle's login page, allauth's login, and the Django admin
login. It deliberately does *not* use ``user_can_authenticate()``: Django
also calls that on every request to restore the session's user, so a
check there would log out SSO users as well.

Microsoft SSO logins never pass through here (allauth logs the user in
directly after Entra has authenticated them), and API keys have their own
authentication (``apps/accounts/api_auth.py``).
"""

from __future__ import annotations

import logging

from allauth.account.auth_backends import AuthenticationBackend as AllauthBackend
from django.conf import settings
from django.contrib.auth.backends import ModelBackend

logger = logging.getLogger(__name__)


def is_break_glass(user) -> bool:
    """True for a user named in SSO_BREAK_GLASS_USERS (case-insensitive)."""
    names = {n.strip().lower() for n in settings.SSO_BREAK_GLASS_USERS if n.strip()}
    return user.get_username().lower() in names


def password_login_allowed(user) -> bool:
    """Whether this user may sign in with a password at all."""
    return not settings.SSO_ONLY or is_break_glass(user)


class _SSOOnlyMixin:
    """Refuse a correct password from anyone but break-glass under SSO_ONLY."""

    def authenticate(self, request, *args, **kwargs):
        user = super().authenticate(request, *args, **kwargs)
        if user is None:
            return None
        if not password_login_allowed(user):
            logger.warning("Password login refused for %s: SSO_ONLY is on", user.get_username())
            return None
        if settings.SSO_ONLY:
            logger.warning("Break-glass password login by %s", user.get_username())
        return user


class PasswordBackend(_SSOOnlyMixin, ModelBackend):
    """Django's username/password backend, under the SSO_ONLY rule."""


class AllauthPasswordBackend(_SSOOnlyMixin, AllauthBackend):
    """allauth's username/e-mail + password backend, under the SSO_ONLY rule."""
