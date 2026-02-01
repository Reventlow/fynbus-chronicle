"""
Views for the accounts application.

Provides custom login and logout views with HTMX support
and Office 365 SSO integration.
"""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse


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
