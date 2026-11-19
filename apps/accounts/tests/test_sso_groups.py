"""Chronicle's own group check on Microsoft logins (SSO_REQUIRED_GROUPS).

Entra's "Assignment required" decides first; Chronicle repeats the rule
with Graph's checkMemberGroups at every login and refuses when the account
is in none of the groups, or when Graph cannot answer (fail closed).
Also: no "confirm your e-mail" mail for SSO accounts, and the site is no
longer named example.com.
"""

import pytest
from allauth.core import context
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.sites.models import Site

from apps.accounts.adapters import GRAPH_CHECK_MEMBER_GROUPS
from apps.accounts.checks import sso_has_required_groups

from .test_sso import TENANT, _import_settings, _login, _request

GROUP = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
OTHER = "99999999-8888-4777-8666-555555555555"


class FakeResponse:
    def __init__(self, status=200, body=None, bad_json=False):
        self.status_code = status
        self._body = body if body is not None else {"value": []}
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._body


class FakeSession:
    """Stands in for adapter.get_requests_session(); records the POSTs."""

    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


@pytest.fixture
def groups(settings, sso, monkeypatch):
    """SSO with SSO_REQUIRED_GROUPS = [GROUP]; returns (adapter, set_graph)."""
    settings.SSO_REQUIRED_GROUPS = [GROUP]
    holder = {}

    def set_graph(**kwargs):
        holder["session"] = FakeSession(**kwargs)
        return holder["session"]

    monkeypatch.setattr(sso, "get_requests_session", lambda: holder["session"])
    return sso, set_graph


@pytest.fixture
def sso(settings):
    from apps.accounts.adapters import SocialAccountAdapter

    settings.SSO_ALLOWED_EMAIL_DOMAINS = ["fynbus.dk"]
    settings.SSO_ALLOW_GUESTS = False
    settings.SSO_AUTO_CREATE_USERS = True
    settings.SSO_REQUIRED_GROUPS = []
    settings.SOCIALACCOUNT_PROVIDERS = {
        "microsoft": {"APP": {"client_id": "id", "secret": "secret"}, "TENANT": TENANT},
    }
    return SocialAccountAdapter()


def _with_token(login, token="access-token"):
    login.token = SocialToken(token=token)
    return login


def _refused_with(request) -> str:
    return " ".join(str(m) for m in get_messages(request))


@pytest.mark.django_db
def test_member_gets_in_and_graph_is_asked_with_the_users_token(rf, groups):
    adapter, set_graph = groups
    graph = set_graph(response=FakeResponse(body={"value": [GROUP.upper()]}))
    adapter.pre_social_login(_request(rf), _with_token(_login("pma@fynbus.dk")))
    (url, kwargs), = graph.calls
    assert url == GRAPH_CHECK_MEMBER_GROUPS
    assert kwargs["json"] == {"groupIds": [GROUP]}
    assert kwargs["headers"]["Authorization"] == "Bearer access-token"
    assert kwargs["timeout"]


@pytest.mark.django_db
def test_account_outside_the_groups_is_refused(rf, groups):
    adapter, set_graph = groups
    set_graph(response=FakeResponse(body={"value": []}))
    request = _request(rf)
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(request, _with_token(_login("someadmin@fynbus.dk")))
    assert "ikke adgang til Chronicle" in _refused_with(request)


@pytest.mark.django_db
def test_membership_of_an_unrelated_group_does_not_count(rf, groups):
    adapter, set_graph = groups
    set_graph(response=FakeResponse(body={"value": [OTHER]}))
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(_request(rf), _with_token(_login("someadmin@fynbus.dk")))


@pytest.mark.django_db
def test_existing_linked_user_is_checked_too(rf, groups):
    """Removing someone from the group in Entra locks them out at their
    next login, even though their Chronicle user exists and is linked."""
    adapter, set_graph = groups
    user = User.objects.create_user("mra", email="mra@fynbus.dk")
    SocialAccount.objects.create(provider="microsoft", uid="oid-mra", user=user)
    login = _with_token(_login("mra@fynbus.dk", uid="oid-mra"))
    login.lookup()
    assert login.is_existing
    set_graph(response=FakeResponse(body={"value": []}))
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(_request(rf), login)


@pytest.mark.django_db
@pytest.mark.parametrize("graph", [
    {"response": FakeResponse(status=403, body={"error": {"code": "Authorization_RequestDenied"}})},
    {"response": FakeResponse(status=503)},
    {"response": FakeResponse(bad_json=True)},
    {"error": ConnectionError("down")},
])
def test_refused_when_graph_cannot_answer(rf, groups, graph):
    adapter, set_graph = groups
    set_graph(**graph)
    request = _request(rf)
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(request, _with_token(_login("pma@fynbus.dk")))
    assert "kunne ikke tjekke din adgang" in _refused_with(request)


@pytest.mark.django_db
def test_refused_without_an_access_token(rf, groups):
    adapter, set_graph = groups
    graph = set_graph(response=FakeResponse(body={"value": [GROUP]}))
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(_request(rf), _login("pma@fynbus.dk"))
    assert graph.calls == []


@pytest.mark.django_db
def test_no_graph_call_when_no_groups_are_required(rf, sso, monkeypatch):
    monkeypatch.setattr(sso, "get_requests_session", lambda: pytest.fail("Graph was asked"))
    sso.pre_social_login(_request(rf), _with_token(_login("pma@fynbus.dk")))


@pytest.mark.django_db
def test_domain_is_still_checked_before_graph(rf, groups):
    adapter, set_graph = groups
    graph = set_graph(response=FakeResponse(body={"value": [GROUP]}))
    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(_request(rf), _with_token(_login("mallory@evil.example")))
    assert graph.calls == []


# --- settings and checks -------------------------------------------------------


def test_warns_when_sso_is_on_without_required_groups(settings):
    settings.SSO_ENABLED, settings.SSO_REQUIRED_GROUPS = True, []
    assert [w.id for w in sso_has_required_groups(None)] == ["accounts.W002"]
    settings.SSO_REQUIRED_GROUPS = [GROUP]
    assert sso_has_required_groups(None) == []
    settings.SSO_ENABLED, settings.SSO_REQUIRED_GROUPS = False, []
    assert sso_has_required_groups(None) == []


@pytest.mark.parametrize("value", ["Chronicle-Users", f"{GROUP},nope", ",".join([GROUP] * 21)])
def test_refuses_to_start_with_bad_group_ids(value):
    result = _import_settings(SSO_ENABLED="True", MICROSOFT_TENANT_ID=TENANT, SSO_CLIENT_ID="id",
                              SSO_CLIENT_SECRET="secret", SSO_REQUIRED_GROUPS=value)
    assert result.returncode != 0
    assert "SSO_REQUIRED_GROUPS" in result.stderr


def test_starts_with_group_ids_in_any_case():
    result = _import_settings(SSO_ENABLED="True", MICROSOFT_TENANT_ID=TENANT, SSO_CLIENT_ID="id",
                              SSO_CLIENT_SECRET="secret", SSO_REQUIRED_GROUPS=f" {GROUP.upper()} , {OTHER}")
    assert result.returncode == 0, result.stderr


# --- no confirmation mail, a real site name -------------------------------------


def test_sso_accounts_get_no_confirmation_mail():
    from allauth.socialaccount import app_settings

    assert app_settings.EMAIL_VERIFICATION == "none"


@pytest.mark.django_db
def test_site_is_named_after_chronicle():
    site = Site.objects.get_current()
    assert (site.domain, site.name) == ("chronicle.fynbus.net", "FynBus Chronicle")


@pytest.mark.django_db
def test_migration_renames_only_the_placeholder():
    """Production already has example.com; an admin-edited site stays."""
    import importlib

    from django.apps import apps as global_apps
    from django.db import connection

    rename_site = importlib.import_module("apps.accounts.migrations.0004_site_domain").rename_site
    editor = connection.schema_editor()
    Site.objects.update(domain="example.com", name="example.com")
    rename_site(global_apps, editor)
    assert Site.objects.get().domain == "chronicle.fynbus.net"
    Site.objects.update(domain="intra.example.org", name="Intra")
    rename_site(global_apps, editor)
    assert Site.objects.get().domain == "intra.example.org"


# --- the whole allauth flow, not just the adapter --------------------------------


def _flow_request(rf):
    from django.contrib.auth.models import AnonymousUser

    request = _request(rf)
    request.user = AnonymousUser()
    return request


def _provider_login(request, upn, uid, process):
    """A sociallogin built by the real Microsoft provider from a Graph /me
    answer, as the OAuth callback builds it, with its token and state."""
    from allauth.socialaccount.adapter import get_adapter

    provider = get_adapter().get_provider(request, "microsoft")
    data = {"id": uid, "userPrincipalName": upn, "mail": upn, "mailNickname": upn.split("@")[0],
            "displayName": "Test Person"}
    login = _with_token(provider.sociallogin_from_response(request, data))
    login.state = {"process": process, "next": "/dashboard/"}
    return login


@pytest.mark.django_db
@pytest.mark.parametrize("process", ["login", "connect"])
def test_allauth_flow_refuses_outsiders_without_a_session_or_user(rf, groups, process, settings):
    """Through allauth's own complete_social_login, as the OAuth callback
    calls it: an outsider ends on the login page, with no user created and
    nobody logged in, for a login as well as a connect."""
    from allauth.socialaccount.helpers import complete_social_login

    adapter, set_graph = groups
    set_graph(response=FakeResponse(body={"value": []}))
    request = _flow_request(rf)
    login = _provider_login(request, "outsider@fynbus.dk", "oid-outsider", process)
    from unittest import mock

    with mock.patch("apps.accounts.adapters.SocialAccountAdapter.get_requests_session",
                    lambda self: adapter.get_requests_session()):
        with context.request_context(request):
            response = complete_social_login(request, login)
    assert response.status_code == 302 and response["Location"] == "/accounts/login/"
    assert "_auth_user_id" not in request.session
    assert not User.objects.filter(email="outsider@fynbus.dk").exists()
    assert not SocialAccount.objects.filter(uid="oid-outsider").exists()


@pytest.mark.django_db
def test_allauth_flow_lets_a_member_in_as_viewer(rf, groups, settings):
    from unittest import mock

    from allauth.socialaccount.helpers import complete_social_login

    adapter, set_graph = groups
    set_graph(response=FakeResponse(body={"value": [GROUP]}))
    request = _flow_request(rf)
    login = _provider_login(request, "new.person@fynbus.dk", "oid-new", "login")
    with mock.patch("apps.accounts.adapters.SocialAccountAdapter.get_requests_session",
                    lambda self: adapter.get_requests_session()):
        with context.request_context(request):
            complete_social_login(request, login)
    user = User.objects.get(email="new.person@fynbus.dk")
    assert str(request.session["_auth_user_id"]) == str(user.pk)
    assert user.groups.filter(name="Viewer").exists()
