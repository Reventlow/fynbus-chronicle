"""
Views for the accounts application.

Provides custom login and logout views with HTMX support
and Office 365 SSO integration.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import APIKey


class CustomLoginView(auth_views.LoginView):
    """
    Custom login view with Scandinavian styling and SSO support.

    Features:
    - HTMX-enhanced form validation
    - Office 365 SSO button (when enabled)
    - Remember me functionality
    - Redirects authenticated users to dashboard
    """

    template_name = "accounts/login.html"

    def dispatch(self, request, *args, **kwargs):
        """Redirect authenticated users to dashboard."""
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs) -> dict:
        """Add SSO configuration to context."""
        context = super().get_context_data(**kwargs)
        context["sso_enabled"] = settings.SSO_ENABLED
        return context

    def form_invalid(self, form) -> HttpResponse:
        """Handle HTMX form submission with inline errors."""
        if self.request.htmx:
            return TemplateResponse(
                self.request,
                "accounts/partials/login_form.html",
                {"form": form, "sso_enabled": settings.SSO_ENABLED},
            )
        return super().form_invalid(form)


def logout_view(request):
    """Log out the user and redirect to login page."""
    from django.contrib.auth import logout
    logout(request)
    return redirect("accounts:login")


# ---------------------------------------------------------------------------
# Self-service API-key management
# ---------------------------------------------------------------------------

# Session key the freshly minted raw key is parked under, so it survives the
# redirect-after-POST exactly once. The detail template pops it on render.
_RAW_KEY_SESSION_KEY = "_fynbus_chronicle_new_api_key"


def _stash_new_key(request, raw_key: str, scope: str, label: str) -> None:
    request.session[_RAW_KEY_SESSION_KEY] = {
        "raw": raw_key,
        "scope": scope,
        "label": label,
    }


def _pop_new_key(request) -> dict | None:
    return request.session.pop(_RAW_KEY_SESSION_KEY, None)


@login_required
def api_keys_list(request):
    """List the current user's API keys + form to mint a new one."""
    keys = request.user.api_keys.all()
    return render(
        request,
        "accounts/api_keys.html",
        {
            "api_keys": keys,
            "scopes": APIKey.Scope.choices,
            "new_key": _pop_new_key(request),
        },
    )


@login_required
@require_POST
def api_keys_create(request):
    """Mint a new key for the current user."""
    label = (request.POST.get("label") or "").strip()[:80]
    scope = request.POST.get("scope") or APIKey.Scope.READ
    if scope not in {APIKey.Scope.READ, APIKey.Scope.WRITE}:
        messages.error(request, "Ukendt adgangsniveau.")
        return redirect("accounts:api-keys")
    _, raw = APIKey.generate(user=request.user, scope=scope, label=label)
    _stash_new_key(request, raw, scope, label)
    messages.success(request, "Ny API-nøgle oprettet. Kopiér den nu — den vises kun denne ene gang.")
    return redirect("accounts:api-keys")


@login_required
@require_POST
def api_keys_revoke(request, key_id: int):
    """Revoke one of the current user's keys."""
    api_key = get_object_or_404(APIKey, pk=key_id, user=request.user)
    api_key.revoke()
    messages.success(request, f"Nøgle {api_key.prefix}… tilbagekaldt.")
    return redirect("accounts:api-keys")


@login_required
@require_POST
def api_keys_reroll(request, key_id: int):
    """Atomic reroll: revoke the old key, mint a new one with same label/scope."""
    api_key = get_object_or_404(APIKey, pk=key_id, user=request.user)
    api_key.revoke()
    _, raw = APIKey.generate(user=request.user, scope=api_key.scope, label=api_key.label)
    _stash_new_key(request, raw, api_key.scope, api_key.label)
    messages.success(request, "Nøgle rerolled. Kopiér den nye værdi nu — den vises kun denne ene gang.")
    return redirect("accounts:api-keys")
