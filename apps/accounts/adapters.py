"""django-allauth adapters: who may get a Chronicle account, and how.

Chronicle is an internal tool. Nobody signs themselves up:

* **Local accounts** are created by staff in Django Admin. allauth's own
  sign-up page (``/allauth/signup/``) stays mounted, because the package
  ships it, but :class:`AccountAdapter` closes it. Before 1.15.5 it was
  open, and every account it created was an editor.

* **Microsoft SSO** (when ``SSO_ENABLED``) is the only other way in, and
  :class:`SocialAccountAdapter` decides who passes:

  - The login authority is pinned to the FynBus tenant
    (``MICROSOFT_TENANT_ID`` must be a tenant GUID, see settings), so only
    accounts in that directory can authenticate at all.
  - Guest accounts (``#EXT#`` in the UPN) are refused unless
    ``SSO_ALLOW_GUESTS`` is on.
  - The account's address must be in ``SSO_ALLOWED_EMAIL_DOMAINS``.
  - The Microsoft account is tied to a Chronicle user by its Entra object
    id (allauth's uid for this provider). On the *first* SSO login of an
    existing user, the link is made once by e-mail address — safe here only
    because the tenant is pinned and addresses in it are set by our own
    admins (the "nOAuth" attack relies on a foreign tenant choosing any
    address). After that the object id alone decides.
  - A FynBus account with no Chronicle user yet is created in the
    **Viewer** group (read-only) when ``SSO_AUTO_CREATE_USERS`` is on;
    staff promote it. With the setting off, staff must create it first.

Who may sign in with Microsoft at all is decided in Entra: the enterprise
app has "Assignment required" on, with only the assigned groups allowed.
"""

from __future__ import annotations

import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.shortcuts import redirect

logger = logging.getLogger(__name__)

VIEWER_GROUP = "Viewer"


class AccountAdapter(DefaultAccountAdapter):
    """Local accounts: self sign-up is closed; staff create accounts."""

    def is_open_for_signup(self, request) -> bool:
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Microsoft SSO: only FynBus accounts, linked by Entra object id."""

    def pre_social_login(self, request, sociallogin) -> None:
        """Refuse foreign accounts; link an existing user on first login."""
        data = sociallogin.account.extra_data or {}
        upn = (data.get("userPrincipalName") or "").lower()
        email = (data.get("mail") or data.get("userPrincipalName") or "").strip().lower()

        if "#ext#" in upn and not settings.SSO_ALLOW_GUESTS:
            self._refuse(request, sociallogin, "guest account",
                         "Gæstekonti kan ikke logge ind i Chronicle.")
        if not _domain_allowed(email):
            self._refuse(request, sociallogin, f"address outside allowed domains: {email!r}",
                         "Din Microsoft-konto hører ikke til en tilladt organisation.")

        if sociallogin.is_existing:
            return  # already tied to a user by its object id

        # First SSO login: tie it to the existing user with that address,
        # if there is exactly one active one.
        matches = list(User.objects.filter(email__iexact=email, is_active=True)[:2])
        if len(matches) == 1:
            sociallogin.connect(request, matches[0])
            logger.info("SSO: linked Microsoft account %s to existing user %s",
                        sociallogin.account.uid, matches[0].username)
        elif len(matches) > 1:
            self._refuse(request, sociallogin, f"{len(matches)} users share {email!r}",
                         "Flere brugere har den samme mailadresse. Kontakt IT.")

    def is_open_for_signup(self, request, sociallogin) -> bool:
        """A new user from SSO only when auto-creation is switched on."""
        return bool(settings.SSO_AUTO_CREATE_USERS)

    def save_user(self, request, sociallogin, form=None):
        """New SSO users start read-only, in the Viewer group."""
        user = super().save_user(request, sociallogin, form)
        group, _ = Group.objects.get_or_create(name=VIEWER_GROUP)
        user.groups.add(group)
        logger.info("SSO: created user %s (Viewer) for Microsoft account %s",
                    user.username, sociallogin.account.uid)
        return user

    def _refuse(self, request, sociallogin, reason: str, message: str) -> None:
        """Stop the login: log why, tell the user, go back to the login page."""
        logger.warning("SSO login refused (%s) for Microsoft account %s",
                       reason, sociallogin.account.uid)
        messages.error(request, message)
        raise ImmediateHttpResponse(redirect("accounts:login"))


def _domain_allowed(email: str) -> bool:
    """True when the address's domain is in SSO_ALLOWED_EMAIL_DOMAINS."""
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1]
    return domain in {d.strip().lower() for d in settings.SSO_ALLOWED_EMAIL_DOMAINS if d.strip()}
