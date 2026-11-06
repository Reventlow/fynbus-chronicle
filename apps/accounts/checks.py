"""System checks for the account settings (run by ``manage.py check``
and at start-up)."""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def sso_only_has_break_glass(app_configs, **kwargs):
    """SSO_ONLY without break-glass accounts locks everyone out if Entra
    is unavailable. Allowed, but worth a warning."""
    if settings.SSO_ONLY and not [n for n in settings.SSO_BREAK_GLASS_USERS if n.strip()]:
        return [Warning(
            "SSO_ONLY is on but SSO_BREAK_GLASS_USERS is empty.",
            hint="Name one or two local superusers who may still use a password "
                 "(at /accounts/login/?local=1) if Microsoft sign-in is down.",
            id="accounts.W001",
        )]
    return []
