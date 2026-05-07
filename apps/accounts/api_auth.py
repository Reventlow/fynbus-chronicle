"""HTTP API key authentication for the Chronicle JSON API.

Usage:

    from apps.accounts.api_auth import api_auth

    @api_auth(scope="read")
    def my_view(request):
        # request.api_user / request.api_scope are set
        ...

The decorator checks the ``Authorization: Bearer <key>`` header, looks the
key up by prefix, verifies the SHA-256 hash, and attaches ``api_user`` and
``api_scope`` to the request. CSRF is exempt because keys *are* the auth.
"""

from functools import wraps
from typing import Callable

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import APIKey


def _extract_bearer(request: HttpRequest) -> str | None:
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.lower().startswith("bearer "):
        return None
    return auth[7:].strip() or None


def api_auth(*, scope: str = "read"):
    """Decorator factory.

    ``scope='read'`` accepts both read and write keys.
    ``scope='write'`` accepts write keys only.
    """
    if scope not in {"read", "write"}:
        raise ValueError(f"Invalid scope: {scope!r}")

    def decorator(view: Callable) -> Callable:
        @csrf_exempt
        @wraps(view)
        def wrapped(request: HttpRequest, *args, **kwargs):
            raw = _extract_bearer(request)
            if raw is None:
                return JsonResponse(
                    {"error": "missing_credentials", "detail": "Authorization: Bearer <key> required"},
                    status=401,
                )
            api_key = APIKey.authenticate(raw)
            if api_key is None:
                return JsonResponse(
                    {"error": "invalid_credentials", "detail": "Unknown or revoked key"},
                    status=401,
                )
            if scope == "write" and api_key.scope != APIKey.Scope.WRITE:
                return JsonResponse(
                    {"error": "insufficient_scope", "detail": "This key is read-only"},
                    status=403,
                )
            request.api_user = api_key.user
            request.api_scope = api_key.scope
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
