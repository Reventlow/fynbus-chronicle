"""Signal handlers for login/logout tracking."""

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.http import HttpRequest

from .models import LoginLog


def _get_client_ip(request: HttpRequest) -> str | None:
    """Extract client IP, respecting X-Forwarded-For for reverse proxies."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _create_log(user, event: str, request: HttpRequest | None) -> None:
    """Create a LoginLog entry from a signal."""
    ip = _get_client_ip(request) if request else None
    user_agent = (request.META.get("HTTP_USER_AGENT", "") if request else "")[:512]
    LoginLog.objects.create(
        user=user,
        event=event,
        ip_address=ip,
        user_agent=user_agent,
    )


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    """Log successful login events."""
    _create_log(user, LoginLog.Event.LOGIN, request)


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    """Log logout events."""
    _create_log(user, LoginLog.Event.LOGOUT, request)
