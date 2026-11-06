"""SSO_ONLY: passwords only for break-glass accounts (apps/accounts/backends.py)."""

import os
import subprocess
import sys

import pytest
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.management import call_command

from apps.accounts.checks import sso_only_has_break_glass

PASSWORD = "Correct-horse-battery-9"


@pytest.fixture
def sso_only(settings):
    settings.SSO_ENABLED = True
    settings.SSO_ONLY = True
    settings.SSO_BREAK_GLASS_USERS = ["Breakglass"]
    return settings


@pytest.fixture
def users(db):
    return {
        "normal": User.objects.create_user("anna", email="anna@fynbus.dk", password=PASSWORD),
        "admin": User.objects.create_superuser("root", email="root@fynbus.dk", password=PASSWORD),
        "glass": User.objects.create_superuser("breakglass", email="bg@fynbus.dk", password=PASSWORD),
    }


def _logged_in(client) -> bool:
    return "_auth_user_id" in client.session


# --- passwords -----------------------------------------------------------------


def test_password_login_works_without_sso_only(client, users, settings):
    settings.SSO_ONLY = False
    client.post("/accounts/login/", {"username": "anna", "password": PASSWORD})
    assert _logged_in(client)


def test_password_refused_for_normal_user(client, users, sso_only):
    response = client.post("/accounts/login/?local=1", {"username": "anna", "password": PASSWORD})
    assert response.status_code == 200  # the form again, with an error
    assert not _logged_in(client)


def test_password_refused_for_superuser_not_on_the_list(client, users, sso_only):
    client.post("/accounts/login/?local=1", {"username": "root", "password": PASSWORD})
    assert not _logged_in(client)


def test_break_glass_may_use_password_case_insensitively(client, users, sso_only):
    client.post("/accounts/login/?local=1", {"username": "breakglass", "password": PASSWORD})
    assert _logged_in(client)


def test_admin_login_obeys_sso_only(client, users, sso_only):
    client.post("/admin/login/", {"username": "root", "password": PASSWORD, "next": "/admin/"})
    assert not _logged_in(client)
    client.post("/admin/login/", {"username": "breakglass", "password": PASSWORD, "next": "/admin/"})
    assert _logged_in(client)


def test_allauth_backend_by_email_obeys_sso_only(rf, users, sso_only):
    """allauth's backend also accepts an e-mail address; same rule."""
    assert authenticate(rf.get("/"), email="anna@fynbus.dk", password=PASSWORD) is None
    assert authenticate(rf.get("/"), username="anna", password=PASSWORD) is None


# --- what keeps working ----------------------------------------------------------------


def test_existing_session_survives_switching_sso_only_on(client, users, settings):
    """The rule is checked at login only; it must not log everyone out on
    every request (Django restores the session user through the backend)."""
    client.force_login(users["normal"], backend="apps.accounts.backends.PasswordBackend")
    settings.SSO_ENABLED = True
    settings.SSO_ONLY = True
    assert client.get("/dashboard/").status_code == 200


def test_sso_session_works_under_sso_only(client, users, sso_only):
    """A Microsoft login ends with allauth logging the user in through the
    allauth backend; that session must be accepted on later requests."""
    SocialAccount.objects.create(user=users["normal"], provider="microsoft", uid="oid-anna")
    client.force_login(users["normal"], backend="apps.accounts.backends.AllauthPasswordBackend")
    assert client.get("/dashboard/").status_code == 200


# --- login page ----------------------------------------------------------------


@pytest.mark.django_db
def test_login_page_hides_password_form(client, sso_only):
    html = client.get("/accounts/login/").content.decode()
    assert 'name="password"' not in html
    assert 'action="/allauth/microsoft/login/"' in html
    assert "Eller log ind med" not in html


@pytest.mark.django_db
def test_login_page_shows_password_form_at_local(client, sso_only):
    html = client.get("/accounts/login/?local=1").content.decode()
    assert 'name="password"' in html


# --- admin overview ----------------------------------------------------------------


def test_user_admin_shows_who_is_linked(client, users, sso_only):
    SocialAccount.objects.create(user=users["normal"], provider="microsoft", uid="oid-anna")
    client.force_login(users["glass"])
    html = client.get("/admin/auth/user/").content.decode()
    assert "✓ Tilknyttet" in html
    assert "Break-glass" in html
    unlinked = client.get("/admin/auth/user/?sso=no").content.decode()
    assert "root" in unlinked and "anna" not in unlinked


# --- configuration -----------------------------------------------------------------


def test_warns_without_break_glass(settings):
    settings.SSO_ONLY = True
    settings.SSO_BREAK_GLASS_USERS = []
    assert [w.id for w in sso_only_has_break_glass(None)] == ["accounts.W001"]
    settings.SSO_BREAK_GLASS_USERS = ["breakglass"]
    assert sso_only_has_break_glass(None) == []


def test_sso_only_refuses_to_start_without_sso():
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "chronicle.settings.dev",
           "SSO_ONLY": "True", "SSO_ENABLED": "False"}
    result = subprocess.run([sys.executable, "-c", "import django; django.setup()"],
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert "SSO_ONLY" in result.stderr


def test_manage_check_is_clean_by_default(db):
    call_command("check")
