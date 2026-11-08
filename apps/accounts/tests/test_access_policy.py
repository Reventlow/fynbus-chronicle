"""Access policy: every route refuses anonymous visitors unless listed here.

The rules themselves are in ``apps/accounts/permissions.py`` (editor vs.
Viewer) and ``apps/accounts/api_auth.py`` (API key scopes); see
docs/DEVELOPMENT.md, "Permissions". This test is the guard that keeps the
first rule — *you must be signed in* — true for every URL, including ones
added later. A new view that forgets ``@login_required`` /
``LoginRequiredMixin`` fails here instead of shipping open.

The test walks the whole URL conf, fills every path converter with a
placeholder, and sends an anonymous GET and POST. A route counts as refused
when it answers with a redirect to the login page, 401, 403 or 405. A 404 is
*not* accepted: the test database is empty, so an unprotected detail view
would 404 too, and that must not pass as "protected".
"""

import re

import pytest
from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse

# Route prefixes owned by other access rules, not by Chronicle's views.
EXCLUDED_PREFIXES = (
    "admin/",  # Django admin: its own staff-only login
    "__debug__/",  # debug toolbar, DEBUG only
    "__reload__/",  # browser reload, DEBUG only
    "^media/",  # uploaded files served by runserver, DEBUG only
)

# Chronicle routes that anonymous users may reach, and why. Each one must
# give an unknown key and a revoked/private one the same answer, so the
# response never confirms what exists (see the tests below and in
# apps/reports/tests/test_reports.py).
PUBLIC_ROUTES = {
    "accounts/login/": "the sign-in page itself",
    "reports/<slug:slug>/": "a report its editor made public (else login)",
    "reports/<slug:slug>/video/": "the video of a public report (else login)",
    "reports/p/<str:token>/": "token link to a public report (else 404)",
    "reports/p/<str:token>/video/": "token link to a public report's video (else 404)",
    # Kursusmateriale is readable without login by design (1.20.0); every
    # write route under kursus/ still needs an editor (apps/courses tests).
    "kursus/": "course material overview (folder creation still needs an editor)",
    "kursus/<slug:slug>/": "a course material folder",
    "kursus/fil/<str:key>/": "a course material file; the key is random",
    "dashboard/statistik/delt/<str:token>/data.json": "statistics share link; token is the key (else 404)",
    "dashboard/statistik/delt/<str:token>/vejledning.md": "guide for a statistics share link (else 404)",
    # Microsoft SSO, only reachable with SSO_ENABLED (otherwise these lead
    # to accounts:login like every other allauth page, see chronicle/urls.py).
    # Who gets in is decided by apps/accounts/adapters.py and test_sso.py.
    "allauth/microsoft/login/": "starts the Microsoft sign-in",
    "allauth/microsoft/login/callback/": "Microsoft returns here after sign-in",
    "allauth/3rdparty/signup/": "allauth's SSO sign-up step; the adapter decides",
    "allauth/3rdparty/login/cancelled/": "message page: sign-in was cancelled",
    "allauth/3rdparty/login/error/": "message page: sign-in failed",
}

REFUSED_STATUS = {401, 403, 405}


def _walk(resolver, prefix=""):
    """Yield the full route string of every URL pattern, depth first."""
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            yield from _walk(pattern, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            yield prefix + str(pattern.pattern)


def _concrete(route: str) -> str:
    """Turn ``logbook/<int:year>/<int:week>/`` into ``/logbook/1/1/``."""
    route = re.sub(r"<int:[^>]+>", "1", route)
    route = re.sub(r"<[^>]+>", "x", route)
    # Regex routes (re_path, allauth): named groups become "x", a
    # non-capturing alternation becomes its first branch, anchors go.
    route = re.sub(r"\(\?P<[^>]+>[^)]*\)", "x", route)
    route = re.sub(r"\(\?:([^|)]*)[^)]*\)", r"\1", route)
    return "/" + route.replace("^", "").replace("$", "")


ROUTES = sorted(
    route
    for route in set(_walk(get_resolver()))
    if not route.startswith(EXCLUDED_PREFIXES) and route not in PUBLIC_ROUTES
)


def test_routes_were_found():
    """Guard against the walk silently finding nothing."""
    assert len(ROUTES) > 50


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("route", ROUTES)
def test_anonymous_is_refused(client, route, method):
    url = _concrete(route)
    response = getattr(client, method)(url)

    if response.status_code in REFUSED_STATUS:
        return
    login_url = reverse(settings.LOGIN_URL) if ":" in settings.LOGIN_URL else settings.LOGIN_URL
    location = response.get("Location", "")
    assert response.status_code in (301, 302) and location.startswith(login_url), (
        f"anonymous {method.upper()} {url} answered {response.status_code}"
        f"{' -> ' + location if location else ''}; protect the view or add it to"
        " PUBLIC_ROUTES with a reason"
    )


def test_public_routes_still_exist():
    """An allowlist entry for a route that is gone would hide nothing, but
    it would also stop documenting anything; keep the list honest."""
    all_routes = set(_walk(get_resolver()))
    assert set(PUBLIC_ROUTES) <= all_routes


@pytest.mark.django_db
def test_private_report_slug_looks_like_unknown_slug(client):
    """Anonymous: a private report and a missing one answer identically."""
    from apps.reports.models import Report

    Report.objects.create(title="Privat rapport", html="<p>x</p>", is_public=False)
    private = Report.objects.get()
    for suffix in ("", "video/"):
        known = client.get(f"/reports/{private.slug}/{suffix}")
        unknown = client.get(f"/reports/findes-ikke/{suffix}")
        assert known.status_code == unknown.status_code == 302
        assert known["Location"].split("?")[0] == unknown["Location"].split("?")[0]
