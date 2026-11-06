"""
URL configuration for FynBus Chronicle.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path, re_path
from django.views.generic import RedirectView


def root_redirect(request):
    """Redirect root URL based on authentication status."""
    if request.user.is_authenticated:
        return redirect("dashboard:index")
    return redirect("accounts:login")


# allauth is mounted for Microsoft SSO only. Its own account pages (login,
# sign-up, password reset, e-mail confirmation, …) are not part of
# Chronicle: users sign in at accounts:login and staff create accounts.
# Left reachable they were a second, unadvertised way in (the open sign-up
# made editors until 1.15.5), so they all lead to Chronicle's login page.
# With SSO off, the Microsoft routes go there too instead of erroring.
_UNUSED_ALLAUTH = r"login|signup|password|confirm-email|inactive|email|reauthenticate|account"
if not settings.SSO_ENABLED:
    _UNUSED_ALLAUTH += r"|microsoft|3rdparty|social"
_to_login = RedirectView.as_view(pattern_name="accounts:login", query_string=True)

urlpatterns = [
    re_path(rf"^allauth/(?:{_UNUSED_ALLAUTH})(?:/|$)", _to_login),
    path("", root_redirect, name="root"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("logbook/", include("apps.logbook.urls")),
    path("oncall/", include("apps.oncall.urls")),
    path("tasks/", include("apps.tasks.urls")),
    path("feedback/", include("apps.feedback.urls")),
    path("cves/", include("apps.cves.urls")),
    path("themes/", include("apps.themes.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("reports/", include("apps.reports.urls")),
    path("images/", include("apps.images.urls")),
    path("api/v1/", include("apps.api.urls")),
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
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
