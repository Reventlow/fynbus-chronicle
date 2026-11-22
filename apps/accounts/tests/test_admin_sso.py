"""Django admin with Microsoft sign-in: staff who signed in with Microsoft
have the admin pages, and a signed-out visit to /admin/ leads to
Chronicle's login page (Microsoft button) rather than Django admin's
password-only page (chronicle/urls.py, admin_login).

Vagt deliberately does the opposite (SSO sessions never reach its admin);
these tests keep Chronicle's rule from being copied over by mistake.
"""

import pytest
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User

PASSWORD = "Correct-horse-battery-9"
SSO_BACKEND = "apps.accounts.backends.AllauthPasswordBackend"


@pytest.fixture
def sso_only(settings):
    settings.SSO_ENABLED = True
    settings.SSO_ONLY = True
    settings.SSO_BREAK_GLASS_USERS = ["breakglass"]
    return settings


@pytest.fixture
def staff(db):
    user = User.objects.create_superuser("root", email="root@fynbus.dk", password=PASSWORD)
    SocialAccount.objects.create(user=user, provider="microsoft", uid="oid-root")
    return user


def test_sso_staff_has_the_admin_pages(client, staff, sso_only):
    client.force_login(staff, backend=SSO_BACKEND)
    for url in ("/admin/", "/admin/auth/user/", "/admin/auth/user/add/"):
        assert client.get(url).status_code == 200, url
    assert 'href="/admin/"' in client.get("/dashboard/").content.decode()


def test_signed_out_admin_visit_leads_to_chronicles_login(client, staff, sso_only):
    response = client.get("/admin/", follow=True)
    assert response.redirect_chain[-1][0] in ("/accounts/login/?next=/admin/", "/accounts/login/?next=%2Fadmin%2F")
    assert "/allauth/microsoft/login/" in response.content.decode()


def test_admin_login_page_itself_leads_to_chronicles_login(client, db, sso_only):
    response = client.get("/admin/login/?next=/admin/auth/user/")
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/?next=/admin/auth/user/"


def test_break_glass_still_reaches_admin_through_local_login(client, db, sso_only):
    User.objects.create_superuser("breakglass", email="bg@fynbus.dk", password=PASSWORD)
    client.post("/accounts/login/?local=1", {"username": "breakglass", "password": PASSWORD})
    assert client.get("/admin/").status_code == 200


def test_signed_in_non_staff_gets_djangos_not_authorised_page(client, db, sso_only):
    user = User.objects.create_user("anna", email="anna@fynbus.dk", password=PASSWORD)
    client.force_login(user, backend=SSO_BACKEND)
    response = client.get("/admin/", follow=True)
    assert response.status_code == 200
    assert response.redirect_chain[-1][0].startswith("/admin/login/")
    assert "_auth_user_id" in client.session  # no redirect loop, still signed in


def test_without_sso_admin_keeps_its_own_login_page(client, db, settings):
    settings.SSO_ENABLED = False
    settings.SSO_ONLY = False
    assert client.get("/admin/login/").status_code == 200
