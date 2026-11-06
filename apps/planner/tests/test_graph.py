"""The Graph client and the sign-in hand-over (MSAL mocked)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.planner import crypto
from apps.planner.graph import GraphClient, PlannerAuth, PlannerError
from apps.planner.models import PendingSignIn, PlannerConnection

from .conftest import TENANT

# --- GraphClient ---------------------------------------------------------------


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}

    def json(self):
        return self._body


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs["headers"]["Authorization"]))
        return self.responses.pop(0)


def test_get_all_follows_paging():
    session = Session([Resp(200, {"value": [1, 2], "@odata.nextLink": "https://graph.microsoft.com/v1.0/p2"}),
                       Resp(200, {"value": [3]})])
    client = GraphClient(lambda: "tok", session=session)
    assert list(client.get_all("/x")) == [1, 2, 3]
    assert session.calls[1][0] == "https://graph.microsoft.com/v1.0/p2"
    assert session.calls[0][1] == "Bearer tok"


def test_throttling_waits_retry_after():
    waits = []
    session = Session([Resp(429, headers={"Retry-After": "7"}), Resp(200, {"ok": True})])
    assert GraphClient(lambda: "t", session=session, sleep=waits.append).get("/x") == {"ok": True}
    assert waits == [7.0]


def test_error_carries_code_not_body():
    session = Session([Resp(403, {"error": {"code": "Forbidden", "message": "token abc..."}})])
    with pytest.raises(PlannerError) as exc:
        GraphClient(lambda: "t", session=session).get("/planner/plans/p")
    assert "403 Forbidden" in str(exc.value) and "token" not in str(exc.value)


# --- sign-in hand-over ------------------------------------------------------------


class FakeMsal:
    """Enough of msal.ConfidentialClientApplication for PlannerAuth."""

    def __init__(self, result, accounts):
        self.result, self.accounts, self.removed, self.calls = result, accounts, [], []

    def __call__(self, client_id, client_credential, authority, token_cache):
        assert client_credential == "test-secret" and authority.endswith(TENANT)
        self.cache = token_cache
        return self

    def acquire_token_by_authorization_code(self, code, scopes, redirect_uri, data):
        self.calls.append((code, redirect_uri, data))
        return self.result

    def get_accounts(self):
        return self.accounts

    def remove_account(self, account):
        self.removed.append(account)

    def acquire_token_silent(self, scopes, account):
        return self.result


def _pending(user=None, age=timedelta(0)):
    return PendingSignIn.objects.create(
        sealed=crypto.seal({"code": "the-code", "code_verifier": "v", "redirect_uri": "https://r/"}),
        created_by=user, created_at=timezone.now() - age)


def _ok_result(upn="chronicle-planner@fynbus.dk", tid=TENANT):
    return {"access_token": "at", "id_token_claims": {"tid": tid, "preferred_username": upn, "oid": "oid-svc"}}


ACCOUNT = {"home_account_id": "oid-svc.tenant", "local_account_id": "oid-svc"}


@pytest.mark.django_db
def test_redeem_connects_the_service_account(planner, django_user_model):
    staff = django_user_model.objects.create_user("gre", is_staff=True)
    fake = FakeMsal(_ok_result(), [ACCOUNT])
    pending = _pending(staff)
    PlannerAuth(app_factory=fake).redeem(pending)
    pending.refresh_from_db()
    conn = PlannerConnection.get()
    assert pending.status == "done" and pending.sealed == ""
    assert fake.calls == [("the-code", "https://r/", {"code_verifier": "v"})]
    assert conn.is_connected and conn.account_upn == "chronicle-planner@fynbus.dk"
    assert conn.connected_by == staff
    assert conn.sealed_token_cache and "at" not in conn.sealed_token_cache[:10]


@pytest.mark.django_db
@pytest.mark.parametrize("result, reason", [
    (_ok_result(upn="gre@fynbus.dk"), "Forkert konto"),
    (_ok_result(tid="00000000-0000-0000-0000-000000000000"), "tenant"),
    ({"error": "invalid_grant"}, "invalid_grant"),
])
def test_redeem_refuses(planner, result, reason):
    pending = _pending()
    PlannerAuth(app_factory=FakeMsal(result, [ACCOUNT])).redeem(pending)
    pending.refresh_from_db()
    assert pending.status == "failed" and reason in pending.message
    assert pending.sealed == ""
    assert not PlannerConnection.get().is_connected


@pytest.mark.django_db
def test_redeem_refuses_expired_code(planner):
    pending = _pending(age=timedelta(minutes=15))
    PlannerAuth(app_factory=FakeMsal(_ok_result(), [ACCOUNT])).redeem(pending)
    pending.refresh_from_db()
    assert pending.status == "failed" and "udløb" in pending.message


@pytest.mark.django_db
def test_access_token_without_connection(planner):
    with pytest.raises(PlannerError, match="ikke forbundet"):
        PlannerAuth(app_factory=FakeMsal(_ok_result(), [])).access_token()


def test_auth_refuses_without_secret_or_private_key(planner, settings):
    settings.PLANNER_PRIVATE_KEY = ""
    with pytest.raises(PlannerError):
        PlannerAuth(connection=PlannerConnection(), app_factory=FakeMsal({}, []))
