"""Board, status, "Synk nu" and connecting (web container side)."""

from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.planner import crypto
from apps.planner.models import PendingSignIn, PlannerConnection, SyncState
from apps.planner.sync import mirror_plan

from .conftest import CLIENT_ID, PLAN, TENANT, FakeGraph


@pytest.fixture
def web(planner, settings):
    """As the web container: no client secret, no private key."""
    settings.PLANNER_CLIENT_SECRET = ""
    private = settings.PLANNER_PRIVATE_KEY
    settings.PLANNER_PRIVATE_KEY = ""
    return private


@pytest.fixture
def editor(django_user_model):
    return django_user_model.objects.create_user("anna", password="x")


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user("gre", password="x", is_staff=True)


@pytest.fixture
def viewer(django_user_model):
    user = django_user_model.objects.create_user("vera", password="x")
    user.groups.add(Group.objects.get_or_create(name="Viewer")[0])
    return user


@pytest.fixture
def mirrored(planner):
    mirror_plan(FakeGraph(), PLAN)
    conn = PlannerConnection.get()
    conn.sealed_token_cache, conn.home_account_id, conn.account_upn = "x", "h", "SVC-Chronicle-Planner@fynbus.dk"
    conn.save()
    SyncState.objects.filter(pk=1).update(last_success_at=timezone.now()) or SyncState.get()
    state = SyncState.get()
    state.last_success_at = timezone.now()
    state.save()


# --- access -------------------------------------------------------------------


@pytest.mark.django_db
def test_board_404_when_disabled(client, editor, settings):
    settings.PLANNER_ENABLED = False
    client.force_login(editor)
    assert client.get("/planner/").status_code == 404


@pytest.mark.django_db
def test_viewer_is_refused(client, viewer, web):
    client.force_login(viewer)
    assert client.get("/planner/").status_code == 403
    assert client.post("/planner/sync/").status_code == 403


@pytest.mark.django_db
def test_editor_cannot_connect(client, editor, web):
    client.force_login(editor)
    assert client.post("/planner/connect/").status_code == 403
    assert client.get("/planner/connect/callback/?code=x&state=y").status_code == 403
    assert client.post("/planner/disconnect/").status_code == 403


# --- board ------------------------------------------------------------------------


@pytest.mark.django_db
def test_board_renders_buckets_cards_and_escapes(client, editor, web, mirrored):
    client.force_login(editor)
    html = client.get("/planner/").content.decode()
    assert "Intern IT - Backlog" in html
    assert "Backlog (skal løses 2026)" in html and "Icelog (kan vente til 2027)" in html
    assert "Fornyelse af funktionscertifikater" in html and "1/2" in html
    assert "Ubehandlet" in html and "GR" in html  # label, assignee initials
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert "Fuldførte opgaver" in html  # the completed task is folded away
    assert "Forbind" not in html  # editors don't see the connection card


@pytest.mark.django_db
def test_board_before_first_sync(client, staff, web):
    client.force_login(staff)
    html = client.get("/planner/").content.decode()
    assert "Planner er ikke forbundet endnu" in html and "Forbind Planner" in html


@pytest.mark.django_db
def test_sidebar_item_only_for_editors(client, editor, viewer, web, mirrored):
    client.force_login(editor)
    assert 'href="/planner/"' in client.get("/dashboard/").content.decode()
    client.force_login(viewer)
    assert 'href="/planner/"' not in client.get("/dashboard/").content.decode()


# --- status and Synk nu --------------------------------------------------------------


@pytest.mark.django_db
def test_sync_now_records_request(client, editor, web, mirrored):
    client.force_login(editor)
    html = client.post("/planner/sync/").content.decode()
    state = SyncState.get()
    assert state.is_requested and state.requested_by == editor
    assert "Synkronisering bestilt" in html and "every 2s" in html


@pytest.mark.django_db
def test_status_reloads_page_after_newer_sync(client, editor, web, mirrored):
    client.force_login(editor)
    old = (timezone.now() - timezone.timedelta(minutes=5)).isoformat()
    response = client.get("/planner/status/", {"since": old})
    assert response["HX-Refresh"] == "true"
    current = SyncState.get().last_success_at.isoformat()
    assert "HX-Refresh" not in client.get("/planner/status/", {"since": current})


@pytest.mark.django_db
def test_stale_sync_is_shown_in_red(client, editor, web, mirrored):
    state = SyncState.get()
    state.last_success_at = timezone.now() - timezone.timedelta(hours=3)
    state.last_error = "Microsoft Graph svarede 403 Forbidden"
    state.save()
    client.force_login(editor)
    html = client.get("/planner/status/", {"since": state.last_success_at.isoformat()}).content.decode()
    assert "Sidst synkroniseret for" in html and "403 Forbidden" in html


# --- connecting -----------------------------------------------------------------------


@pytest.mark.django_db
def test_connect_sends_staff_to_microsoft_with_pkce(client, staff, web):
    client.force_login(staff)
    response = client.post("/planner/connect/")
    url = urlparse(response["Location"])
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert url.netloc == "login.microsoftonline.com" and url.path.startswith(f"/{TENANT}/")
    assert q["client_id"] == CLIENT_ID
    assert q["redirect_uri"] == "https://chronicle.fynbus.net/planner/connect/callback/"
    assert q["code_challenge_method"] == "S256" and q["login_hint"] == "SVC-Chronicle-Planner@fynbus.dk"
    assert "Tasks.ReadWrite" in q["scope"] and "offline_access" in q["scope"]
    assert "client_secret" not in response["Location"]
    assert client.session["planner_connect"]["state"] == q["state"]


@pytest.mark.django_db
def test_callback_seals_code_for_sync_container(client, staff, web):
    client.force_login(staff)
    state = parse_qs(urlparse(client.post("/planner/connect/")["Location"]).query)["state"][0]
    response = client.get("/planner/connect/callback/", {"code": "the-one-time-code", "state": state})
    assert response.status_code == 302
    pending = PendingSignIn.objects.get()
    assert pending.created_by == staff and "the-one-time-code" not in pending.sealed
    # Only the sync container's private key opens it.
    from django.conf import settings
    settings.PLANNER_PRIVATE_KEY = web
    assert crypto.open_sealed(pending.sealed)["code"] == "the-one-time-code"


@pytest.mark.django_db
def test_callback_rejects_wrong_state(client, staff, web):
    client.force_login(staff)
    client.post("/planner/connect/")
    client.get("/planner/connect/callback/", {"code": "c", "state": "forged"})
    assert not PendingSignIn.objects.exists()


@pytest.mark.django_db
def test_callback_without_flow_is_refused(client, staff, web):
    client.force_login(staff)
    client.get("/planner/connect/callback/", {"code": "c", "state": "s"})
    assert not PendingSignIn.objects.exists()


@pytest.mark.django_db
def test_disconnect_forgets_tokens(client, staff, web, mirrored):
    client.force_login(staff)
    client.post("/planner/disconnect/")
    conn = PlannerConnection.get()
    assert not conn.is_connected and conn.sealed_token_cache == ""
