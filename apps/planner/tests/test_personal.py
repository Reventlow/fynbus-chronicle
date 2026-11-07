"""Editors' own Microsoft connections: connecting (web side) and the
identity checks when the sync container redeems the sign-in."""

from urllib.parse import parse_qs, urlparse

import pytest
from allauth.socialaccount.models import SocialAccount

from apps.planner import crypto
from apps.planner.graph import PlannerAuth, PlannerError
from apps.planner.models import PendingSignIn, PlannerConnection, PlannerUserConnection
from apps.planner.sync import PlannerJob

from .conftest import TENANT
from .test_graph import FakeMsal


@pytest.fixture
def anna(django_user_model):
    return django_user_model.objects.create_user("anna", email="Anna@fynbus.dk", password="x")


def _pending(user):
    return PendingSignIn.objects.create(
        sealed=crypto.seal({"code": "c", "code_verifier": "v", "redirect_uri": "https://r/"}),
        created_by=user, for_user=user)


def _result(upn, oid="oid-anna"):
    return {"access_token": "at", "id_token_claims": {"tid": TENANT, "preferred_username": upn, "oid": oid}}


def _account(oid="oid-anna"):
    return {"home_account_id": f"{oid}.tenant", "local_account_id": oid}


def _redeem(user, result, oid="oid-anna"):
    pending = _pending(user)
    conn, _ = PlannerUserConnection.objects.get_or_create(user=user)
    PlannerAuth(connection=conn, app_factory=FakeMsal(result, [_account(oid)])).redeem(pending)
    pending.refresh_from_db()
    conn.refresh_from_db()
    return pending, conn


# --- web side ------------------------------------------------------------------------


@pytest.mark.django_db
def test_connect_me_hints_own_address_and_seals_for_user(client, planner, settings, anna):
    settings.PLANNER_PRIVATE_KEY = ""  # web container
    client.force_login(anna)
    response = client.post("/planner/me/connect/")
    q = {k: v[0] for k, v in parse_qs(urlparse(response["Location"]).query).items()}
    assert q["login_hint"] == "Anna@fynbus.dk" and "prompt" not in q
    client.get("/planner/connect/callback/", {"code": "c", "state": q["state"]})
    pending = PendingSignIn.objects.get()
    assert pending.for_user == anna and "c" != pending.sealed


@pytest.mark.django_db
def test_disconnect_me_forgets_only_own_tokens(client, planner, anna, django_user_model):
    bob = django_user_model.objects.create_user("bob")
    for user in (anna, bob):
        PlannerUserConnection.objects.create(user=user, sealed_token_cache="x", home_account_id="h")
    client.force_login(anna)
    client.post("/planner/me/disconnect/")
    assert not PlannerUserConnection.objects.get(user=anna).is_connected
    assert PlannerUserConnection.objects.get(user=bob).is_connected


# --- sync side ------------------------------------------------------------------------


@pytest.mark.django_db
def test_own_account_by_email(planner, anna):
    pending, conn = _redeem(anna, _result("anna@fynbus.dk"))
    assert pending.status == "done" and conn.is_connected and conn.account_upn == "anna@fynbus.dk"
    assert not PlannerConnection.get().is_connected  # the service account is untouched


@pytest.mark.django_db
def test_own_account_by_sso_object_id(planner, anna):
    """With an SSO link the Entra object id decides, not the address."""
    SocialAccount.objects.create(user=anna, provider="microsoft", uid="oid-anna")
    assert _redeem(anna, _result("anna.alias@fynbus.dk"))[0].status == "done"


@pytest.mark.django_db
@pytest.mark.parametrize("upn, oid, why", [
    ("bob@fynbus.dk", "oid-bob", "Forkert konto"),
    ("SVC-Chronicle-Planner@fynbus.dk", "oid-svc", "Servicekontoen"),
])
def test_someone_elses_account_is_refused(planner, anna, upn, oid, why):
    pending, conn = _redeem(anna, _result(upn, oid), oid)
    assert pending.status == "failed" and why in pending.message and not conn.is_connected


@pytest.mark.django_db
def test_sso_object_id_mismatch_is_refused(planner, anna):
    SocialAccount.objects.create(user=anna, provider="microsoft", uid="oid-anna")
    pending, _ = _redeem(anna, _result("anna@fynbus.dk", oid="oid-other"), oid="oid-other")
    assert pending.status == "failed"


@pytest.mark.django_db
def test_job_redeems_into_the_users_connection(planner, anna):
    seen = []

    class Auth:
        def __init__(self, connection=None, **kw):
            seen.append(connection)

        def redeem(self, pending):
            pending.status = PendingSignIn.Status.DONE
            pending.save()

    _pending(anna)
    PlannerJob(auth_factory=Auth).handle_sign_ins()
    assert isinstance(seen[0], PlannerUserConnection) and seen[0].user == anna


@pytest.mark.django_db
def test_for_user_never_falls_back_to_the_service_account(planner, anna):
    conn = PlannerConnection.get()
    conn.sealed_token_cache, conn.home_account_id = "x", "h"
    conn.save()
    with pytest.raises(PlannerError, match="ikke forbundet"):
        PlannerAuth.for_user(anna)
