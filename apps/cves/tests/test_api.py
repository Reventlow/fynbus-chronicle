"""The CVE endpoints Harbinger talks to."""

import json

import pytest
from django.urls import reverse

from apps.cves.models import CVE, CVEComment

pytestmark = pytest.mark.django_db

PAYLOAD = {
    "cve_id": "cve-2026-109618",
    "subject": "OpenSSH regreSSHion igen",
    "cvss": 9.8,
    "severity": None,
    "cvefeed_url": None,
    "source_url": "https://harbinger.example/vulns/42",
    "comment": "Fundet af Harbinger på 3 servere.",
}


def post(client, key, body):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {key}"} if key else {}
    return client.post(
        reverse("api:cve-create"), data=json.dumps(body), content_type="application/json", **headers
    )


class TestCreate:
    def test_creates_201(self, client, write_key):
        response = post(client, write_key, PAYLOAD)
        assert response.status_code == 201
        data = response.json()
        cve = CVE.objects.get()
        assert data == {
            "id": cve.pk,
            "cve_id": "CVE-2026-109618",
            "subject": "OpenSSH regreSSHion igen",
            "cvss": 9.8,
            "severity": "critical",
            "state": "identified",
            "url": f"http://testserver{reverse('cves:detail', args=[cve.pk])}",
            "created": True,
        }
        assert cve.source == "harbinger"
        assert cve.source_url == PAYLOAD["source_url"]
        assert cve.cvefeed_url == "https://cvefeed.io/vuln/detail/CVE-2026-109618"
        assert cve.created_by.username == "harbinger"
        comment = cve.comments.get()
        assert comment.text == PAYLOAD["comment"]
        assert comment.author.username == "harbinger"

    def test_without_source_url_is_api(self, client, write_key):
        response = post(client, write_key, {"cve_id": "CVE-2026-0001", "subject": "x"})
        assert response.status_code == 201
        cve = CVE.objects.get()
        assert cve.source == "api"
        assert cve.cvss is None
        assert cve.severity == "none"
        assert not cve.comments.exists()

    def test_existing_returns_200_adds_comment_keeps_fields(self, client, write_key, cve):
        cve.set_state(CVE.State.PATCHING, None)
        response = post(
            client,
            write_key,
            {**PAYLOAD, "subject": "Andet emne", "cvss": 1.0, "severity": "low", "comment": "Set igen i dag."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created"] is False
        assert data["id"] == cve.pk
        assert data["subject"] == "OpenSSH regreSSHion igen"
        assert data["cvss"] == 9.8
        assert data["state"] == "patching"
        cve.refresh_from_db()
        assert cve.subject == "OpenSSH regreSSHion igen"
        assert cve.severity == "critical"
        assert cve.source == ""
        assert cve.comments.filter(kind=CVEComment.Kind.COMMENT).get().text == "Set igen i dag."
        assert CVE.objects.count() == 1

    def test_existing_without_comment(self, client, write_key, cve):
        response = post(client, write_key, {"cve_id": cve.cve_id, "subject": "x"})
        assert response.status_code == 200
        assert not cve.comments.exists()

    @pytest.mark.parametrize(
        ("body", "field"),
        [
            ({"cve_id": "CVE-26-1", "subject": "x"}, "cve_id"),
            ({"cve_id": "CVE-2026-0001", "subject": "x", "severity": "catastrophic"}, "severity"),
            ({"cve_id": "CVE-2026-0001", "subject": "x", "cvss": 11}, "cvss"),
            ({"cve_id": "CVE-2026-0001", "subject": "x", "cvss": "9.8"}, "cvss"),
            ({"cve_id": "CVE-2026-0001", "subject": "x", "source_url": "ftp://x"}, "source_url"),
            ({"cve_id": "CVE-2026-0001", "subject": "x", "cvefeed_url": "nope"}, "cvefeed_url"),
            ({"cve_id": "CVE-2026-0001", "subject": "x", "comment": 5}, "comment"),
            ({"cve_id": "CVE-2026-0001", "subject": "x" * 301}, "subject"),
        ],
    )
    def test_invalid_field_400(self, client, write_key, body, field):
        response = post(client, write_key, body)
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_field"
        assert response.json()["field"] == field
        assert not CVE.objects.exists()

    @pytest.mark.parametrize("body", [{"subject": "x"}, {"cve_id": "CVE-2026-0001"}, {"cve_id": "CVE-2026-0001", "subject": "  "}])
    def test_missing_field_400(self, client, write_key, body):
        response = post(client, write_key, body)
        assert response.status_code == 400
        assert response.json()["error"] == "missing_field"

    def test_invalid_json_400(self, client, write_key):
        response = client.post(
            reverse("api:cve-create"), data="{nope", content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {write_key}",
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_body"


class TestAuth:
    def test_no_key_401(self, client):
        assert post(client, None, PAYLOAD).status_code == 401
        assert client.get(reverse("api:cve-list")).status_code == 401

    def test_read_key_cannot_post(self, client, read_key):
        response = post(client, read_key, PAYLOAD)
        assert response.status_code == 403
        assert not CVE.objects.exists()

    def test_read_key_can_list(self, client, read_key, cve):
        response = client.get(reverse("api:cve-list"), HTTP_AUTHORIZATION=f"Bearer {read_key}")
        assert response.status_code == 200

    def test_other_methods_405(self, client, write_key):
        response = client.delete(reverse("api:cve-list"), HTTP_AUTHORIZATION=f"Bearer {write_key}")
        assert response.status_code == 405

    def test_list_and_create_share_route(self):
        assert reverse("api:cve-list") == reverse("api:cve-create") == "/api/v1/cves/"


class TestRead:
    def test_detail_shape(self, client, read_key, cve, editor):
        cve.links.create(url="https://www.openssh.com/security.html", label="Advisory", added_by=editor)
        CVEComment.objects.create(cve=cve, text="Kommentar", author=editor)
        response = client.get(
            reverse("api:cve-detail", args=["cve-2026-109618"]), HTTP_AUTHORIZATION=f"Bearer {read_key}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cve_id"] == "CVE-2026-109618"
        assert data["url"].endswith(reverse("cves:detail", args=[cve.pk]))
        assert data["links"][0]["url"] == "https://www.openssh.com/security.html"
        assert data["links"][0]["label"] == "Advisory"
        assert set(data["links"][0]) == {"url", "label", "added_at"}
        assert data["comments"][0] == {
            "text": "Kommentar",
            "kind": "comment",
            "author": "gre",
            "created_at": data["comments"][0]["created_at"],
        }

    def test_detail_404(self, client, read_key):
        response = client.get(
            reverse("api:cve-detail", args=["CVE-2026-0404"]), HTTP_AUTHORIZATION=f"Bearer {read_key}"
        )
        assert response.status_code == 404
        assert response.json()["error"] == "not_found"

    def test_list_with_state_filter(self, client, read_key, cve, editor):
        other = CVE.objects.create(cve_id="CVE-2026-0002", subject="b")
        other.set_state(CVE.State.SOLVED, editor)
        auth = {"HTTP_AUTHORIZATION": f"Bearer {read_key}"}
        all_ids = [c["cve_id"] for c in client.get(reverse("api:cve-list"), **auth).json()["cves"]]
        assert all_ids == ["CVE-2026-109618", "CVE-2026-0002"]
        solved = client.get(reverse("api:cve-list"), {"state": "solved"}, **auth).json()["cves"]
        assert [c["cve_id"] for c in solved] == ["CVE-2026-0002"]
        assert set(solved[0]) == {"id", "cve_id", "subject", "cvss", "severity", "state", "url"}

    def test_list_bad_state_400(self, client, read_key):
        response = client.get(reverse("api:cve-list"), {"state": "x"}, HTTP_AUTHORIZATION=f"Bearer {read_key}")
        assert response.status_code == 400


class TestCreateRace:
    """Two senders racing on one cve_id: the loser gets the winner's CVE (200), not a 500."""

    def test_integrity_error_falls_back_to_existing(self, client, write_key, monkeypatch):
        from django.db import IntegrityError

        winner = CVE.objects.create(cve_id="CVE-2026-0007", subject="Created by the other request")
        real_filter = CVE.objects.filter
        calls = {"n": 0}

        def filter_hiding_winner_once(*args, **kwargs):
            # First lookup happens "before" the other request committed.
            calls["n"] += 1
            if calls["n"] == 1:
                return real_filter(pk=-1)
            return real_filter(*args, **kwargs)

        def create_loses_race(**kwargs):
            raise IntegrityError("UNIQUE constraint failed: cves_cve.cve_id")

        monkeypatch.setattr(CVE.objects, "filter", filter_hiding_winner_once)
        monkeypatch.setattr(CVE.objects, "create", create_loses_race)
        response = post(client, write_key, {"cve_id": "CVE-2026-0007", "subject": "x", "comment": "Sendt fra Harbinger"})
        assert response.status_code == 200
        body = response.json()
        assert body["created"] is False
        assert body["id"] == winner.pk
        assert CVEComment.objects.filter(cve=winner, text="Sendt fra Harbinger").exists()
