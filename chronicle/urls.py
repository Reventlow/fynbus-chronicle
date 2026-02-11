"""
URL configuration for FynBus Chronicle.
"""

from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path


def root_redirect(request):
    """Redirect root URL based on authentication status."""
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    return redirect("accounts:login")


urlpatterns = [
    path("", root_redirect, name="root"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("logbook/", include("apps.logbook.urls")),
    path("oncall/", include("apps.oncall.urls")),
    path("allauth/", include("allauth.urls")),
]

# Development-only URLs
if settings.DEBUG:
    debug_urls = []

    # Only add debug toolbar if installed
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar
        debug_urls.append(path("__debug__/", include(debug_toolbar.urls)))

    # Browser reload for development
    if "django_browser_reload" in settings.INSTALLED_APPS:
        debug_urls.append(path("__reload__/", include("django_browser_reload.urls")))

    urlpatterns = debug_urls + urlpatterns
