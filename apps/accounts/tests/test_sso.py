"""Who may get a Chronicle account (apps/accounts/adapters.py).

Covers the 1.15.5 fix: allauth's self sign-up was open and every account
it made was an editor. Now local sign-up is closed, and Microsoft SSO
admits only FynBus accounts, linked by Entra object id.
"""

import os
import subprocess
import sys

import pytest
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth.models import User
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware

from apps.accounts.adapters import AccountAdapter, SocialAccountAdapter
from apps.accounts.permissions import is_editor

TENANT = "61f8f8f1-9274-4b15-8393-68dc1d89f250"


# --- local sign-up -----------------------------------------------------------


@pytest.mark.django_db
def test_signup_creates_no_account(client):
    """The old hole: a POST to allauth's sign-up made an active editor."""
    response = client.post(
        "/allauth/signup/",
        {"email": "x@evil.example", "username": "intruder",
         "password1": "Very-long-pass-123!", "password2": "Very-long-pass-123!"},
    )
    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/")
    assert not User.objects.filter(username="intruder").exists()


def test_account_adapter_is_closed(rf):
    assert AccountAdapter().is_open_for_signup(rf.get("/")) is False


# --- Microsoft SSO -----------------------------------------------------------


def _request(rf):
    """A request with session and messages, as allauth's views have."""
    request = rf.get("/allauth/microsoft/login/callback/")
    SessionMiddleware(lambda r: None).process_request(request)
    MessageMiddleware(lambda r: None).process_request(request)
    request.user = None
    return request


def _login(upn: str, mail: str | None = None, uid: str = "oid-1") -> SocialLogin:
    """A sociallogin as the Microsoft provider builds it from Graph /me."""
    data = {"id": uid, "userPrincipalName": upn, "mail": mail if mail is not None else upn,
            "mailNickname": upn.split("@")[0]}
    account = SocialAccount(provider="microsoft", uid=uid, extra_data=data)
    user = User(username=data["mailNickname"], email=data["mail"])
    return SocialLogin(account=account, user=user)


@pytest.fixture
def sso(settings):
    settings.SSO_ALLOWED_EMAIL_DOMAINS = ["fynbus.dk"]
    settings.SSO_ALLOW_GUESTS = False
    settings.SSO_AUTO_CREATE_USERS = True
    # As in production with SSO on (allauth looks the app up when linking).
    settings.SOCIALACCOUNT_PROVIDERS = {
        "microsoft": {"APP": {"client_id": "id", "secret": "secret"}, "TENANT": TENANT},
    }
    return SocialAccountAdapter()


@pytest.mark.django_db
def test_guest_is_refused(rf, sso):
    login = _login("someone_partner.dk#EXT#@fynbus.onmicrosoft.com", mail="someone@fynbus.dk")
    with pytest.raises(ImmediateHttpResponse):
        sso.pre_social_login(_request(rf), login)


@pytest.mark.django_db
def test_guest_allowed_when_switched_on(rf, sso, settings):
    settings.SSO_ALLOW_GUESTS = True
    login = _login("someone_partner.dk#EXT#@fynbus.onmicrosoft.com", mail="someone@fynbus.dk")
    sso.pre_social_login(_request(rf), login)  # no exception


@pytest.mark.django_db
def test_foreign_domain_is_refused(rf, sso):
    with pytest.raises(ImmediateHttpResponse):
        sso.pre_social_login(_request(rf), _login("mallory@evil.example"))


@pytest.mark.django_db
def test_first_login_links_existing_user_by_address(rf, sso):
    gorm = User.objects.create_user("gre", email="GRE@fynbus.dk", password="x")
    login = _login("gre@fynbus.dk", uid="oid-gorm")
    sso.pre_social_login(_request(rf), login)
    account = SocialAccount.objects.get(provider="microsoft", uid="oid-gorm")
    assert account.user == gorm


@pytest.mark.django_db
def test_later_logins_use_the_object_id_not_the_address(rf, sso):
    """Once linked, the address no longer matters: a second user with the
    same address is not picked, the linked account is."""
    gorm = User.objects.create_user("gre", email="gre@fynbus.dk", password="x")
    SocialAccount.objects.create(provider="microsoft", uid="oid-gorm", user=gorm)
    login = _login("gre@fynbus.dk", uid="oid-gorm")
    login.lookup()
    assert login.is_existing and login.user == gorm
    sso.pre_social_login(_request(rf), login)  # no exception, no re-link


@pytest.mark.django_db
def test_ambiguous_address_is_refused(rf, sso):
    User.objects.create_user("a", email="shared@fynbus.dk", password="x")
    User.objects.create_user("b", email="shared@fynbus.dk", password="x")
    with pytest.raises(ImmediateHttpResponse):
        sso.pre_social_login(_request(rf), _login("shared@fynbus.dk"))


@pytest.mark.django_db
def test_new_user_is_created_read_only(rf, sso):
    request = _request(rf)
    login = _login("new.person@fynbus.dk", uid="oid-new")
    sso.pre_social_login(request, login)
    assert sso.is_open_for_signup(request, login) is True
    user = sso.save_user(request, login)
    assert user.groups.filter(name="Viewer").exists()
    assert is_editor(user) is False


def test_no_new_users_when_auto_create_is_off(rf, sso, settings):
    settings.SSO_AUTO_CREATE_USERS = False
    assert sso.is_open_for_signup(rf.get("/"), _login("new.person@fynbus.dk")) is False


# --- settings guard ----------------------------------------------------------


def _import_settings(**env) -> subprocess.CompletedProcess:
    """Load the settings in a fresh interpreter with these variables."""
    full_env = {**os.environ, "DJANGO_SETTINGS_MODULE": "chronicle.settings.dev", **env}
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        env=full_env, capture_output=True, text=True, timeout=60,
    )


@pytest.mark.parametrize("tenant", ["", "common", "organizations", "fynbus.dk"])
def test_sso_refuses_to_start_without_a_tenant_guid(tenant):
    result = _import_settings(SSO_ENABLED="True", MICROSOFT_TENANT_ID=tenant,
                              SSO_CLIENT_ID="id", SSO_CLIENT_SECRET="secret")
    assert result.returncode != 0
    assert "MICROSOFT_TENANT_ID" in result.stderr


def test_sso_starts_with_a_tenant_guid():
    result = _import_settings(SSO_ENABLED="True", MICROSOFT_TENANT_ID=TENANT,
                              SSO_CLIENT_ID="id", SSO_CLIENT_SECRET="secret")
    assert result.returncode == 0, result.stderr


# --- login page ----------------------------------------------------------------


@pytest.mark.django_db
def test_login_page_renders_with_sso_on(client, settings):
    """Before 1.15.5 the Office 365 button reversed a URL name that allauth
    no longer has, so the login page crashed as soon as SSO was switched on."""
    settings.SSO_ENABLED = True
    response = client.get("/accounts/login/?next=/logbook/")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'action="/allauth/microsoft/login/"' in html
    assert 'name="next" value="/logbook/"' in html
