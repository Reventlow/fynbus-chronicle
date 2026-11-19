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


@register()
def sso_has_required_groups(app_configs, **kwargs):
    """With SSO on and no SSO_REQUIRED_GROUPS, the enterprise app's
    "Assignment required" in Entra is the only thing deciding who gets in."""
    if settings.SSO_ENABLED and not settings.SSO_REQUIRED_GROUPS:
        return [Warning(
            "SSO is on but SSO_REQUIRED_GROUPS is empty.",
            hint="Set it to the object id of the Entra group(s) that may use Chronicle, "
                 "so Chronicle checks membership at every Microsoft login too.",
            id="accounts.W002",
        )]
    return []
