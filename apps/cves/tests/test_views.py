"""Web UI: list, detail, create (prefill + duplicates), edit, state
changes, HTMX links/comments and the editor/viewer split."""

import pytest
from django.urls import reverse

from apps.cves.models import CVE, CVEComment, CVELink

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


class TestList:
    def test_lists_and_links_out(self, editor_client, cve):
        response = editor_client.get(reverse("cves:list"))
        assert response.status_code == 200
        body = response.content.decode()
        assert cve.cve_id in body
        assert 'href="https://cvefeed.io/vuln/detail/CVE-2026-109618"' in body
        assert 'rel="noopener"' in body

    def test_search(self, editor_client, cve):
        CVE.objects.create(cve_id="CVE-2026-0042", subject="Exchange")
        body = editor_client.get(reverse("cves:list"), {"q": "exchange"}).content.decode()
        assert "CVE-2026-0042" in body
        assert cve.cve_id not in body

    def test_state_filter(self, editor_client, cve, editor):
        other = CVE.objects.create(cve_id="CVE-2026-0043", subject="b")
        other.set_state(CVE.State.SOLVED, editor)
        body = editor_client.get(reverse("cves:list"), {"state": "solved"}).content.decode()
        assert "CVE-2026-0043" in body
        assert cve.cve_id not in body

    def test_open_before_solved(self, editor_client, editor):
        solved = CVE.objects.create(cve_id="CVE-2026-0050", subject="løst")
        solved.set_state(CVE.State.SOLVED, editor)
        CVE.objects.create(cve_id="CVE-2026-0051", subject="åben")
        body = editor_client.get(reverse("cves:list")).content.decode()
        assert body.index("CVE-2026-0051") < body.index("CVE-2026-0050")

    def test_requires_login(self, client):
        response = client.get(reverse("cves:list"))
        assert response.status_code == 302

    def test_viewer_sees_no_create_button(self, viewer_client, cve):
        body = viewer_client.get(reverse("cves:list")).content.decode()
        assert reverse("cves:create") not in body


    def test_breadcrumb_names_the_section(self, editor_client, cve):
        html = editor_client.get(reverse("cves:list")).content.decode()
        assert '<span class="current">Sårbarheder og hændelser</span>' in html
        assert '<span class="current">Kontrolpanel</span>' not in html


class TestDetail:
    def test_renders_timeline(self, editor_client, cve, editor):
        CVEComment.objects.create(cve=cve, text="**Fed** kommentar", author=editor)
        cve.set_state(CVE.State.PATCHING, editor)
        body = editor_client.get(reverse("cves:detail", args=[cve.pk])).content.decode()
        assert "<strong>Fed</strong>" in body
        assert "Status: Identificeret → Patcher" in body
        # Newest first: the state change comes before the comment.
        assert body.index("Status: Identificeret") < body.index("<strong>Fed</strong>")
        assert reverse("cves:comment-create", args=[cve.pk]) in body

    def test_viewer_sees_no_write_controls(self, viewer_client, cve):
        body = viewer_client.get(reverse("cves:detail", args=[cve.pk])).content.decode()
        assert cve.subject in body
        assert reverse("cves:comment-create", args=[cve.pk]) not in body
        assert reverse("cves:link-create", args=[cve.pk]) not in body
        assert reverse("cves:state", args=[cve.pk]) not in body

    def test_source_link_shown(self, editor_client):
        cve = CVE.objects.create(
            cve_id="CVE-2026-0060", subject="x", source="harbinger", source_url="https://harbinger.example/v/1"
        )
        body = editor_client.get(reverse("cves:detail", args=[cve.pk])).content.decode()
        assert "https://harbinger.example/v/1" in body


class TestCreate:
    def test_prefill_from_query_string(self, editor_client):
        response = editor_client.get(
            reverse("cves:create"),
            {
                "cve_id": "cve-2026-7777",
                "subject": "Fortinet RCE",
                "cvss": "9.1",
                "severity": "critical",
                "cvefeed_url": "https://cvefeed.io/vuln/detail/CVE-2026-7777",
                "source_url": "https://harbinger.example/v/7777",
            },
        )
        assert response.status_code == 200
        initial = response.context["form"].initial
        assert initial["cve_id"] == "CVE-2026-7777"
        assert initial["subject"] == "Fortinet RCE"
        assert initial["cvss"] == "9.1"
        assert initial["severity"] == "critical"
        assert initial["source_url"] == "https://harbinger.example/v/7777"
        assert 'value="Fortinet RCE"' in response.content.decode()

    def test_get_with_existing_id_redirects(self, editor_client, cve):
        response = editor_client.get(reverse("cves:create"), {"cve_id": "cve-2026-109618"})
        assert response.status_code == 302
        assert response.url == reverse("cves:detail", args=[cve.pk])

    def test_post_with_existing_id_redirects_without_duplicate(self, editor_client, cve):
        response = editor_client.post(reverse("cves:create"), {"cve_id": cve.cve_id, "subject": "dublet"})
        assert response.status_code == 302
        assert response.url == reverse("cves:detail", args=[cve.pk])
        assert CVE.objects.count() == 1
        cve.refresh_from_db()
        assert cve.subject != "dublet"

    def test_create_with_initial_comment(self, editor_client, editor):
        response = editor_client.post(
            reverse("cves:create"),
            {"cve_id": "cve-2026-8888", "subject": "Citrix", "cvss": "7.5", "comment": "Rammer NetScaler"},
        )
        cve = CVE.objects.get(cve_id="CVE-2026-8888")
        assert response.status_code == 302
        assert response.url == reverse("cves:detail", args=[cve.pk])
        assert cve.created_by == editor
        assert cve.severity == "high"
        assert cve.source == ""
        assert cve.comments.get().text == "Rammer NetScaler"

    def test_prefilled_source_url_marks_harbinger(self, editor_client):
        editor_client.post(
            reverse("cves:create"),
            {"cve_id": "CVE-2026-8889", "subject": "x", "source_url": "https://harbinger.example/v/1"},
        )
        assert CVE.objects.get(cve_id="CVE-2026-8889").source == "harbinger"

    def test_invalid_id_shows_error(self, editor_client):
        response = editor_client.post(reverse("cves:create"), {"cve_id": "nope", "subject": "x"})
        assert response.status_code == 200
        assert response.context["form"].errors["cve_id"]
        assert not CVE.objects.exists()

    def test_viewer_forbidden(self, viewer_client):
        assert viewer_client.get(reverse("cves:create")).status_code == 403
        response = viewer_client.post(reverse("cves:create"), {"cve_id": "CVE-2026-9999", "subject": "x"})
        assert response.status_code == 403
        assert not CVE.objects.exists()


class TestEdit:
    def test_edit(self, editor_client, cve):
        response = editor_client.post(
            reverse("cves:edit", args=[cve.pk]), {"subject": "Nyt emne", "cvss": "5.0", "severity": ""}
        )
        assert response.status_code == 302
        cve.refresh_from_db()
        assert cve.subject == "Nyt emne"
        assert cve.severity == "medium"

    def test_viewer_forbidden(self, viewer_client, cve):
        response = viewer_client.post(reverse("cves:edit", args=[cve.pk]), {"subject": "hack"})
        assert response.status_code == 403


class TestStateView:
    def test_editor_moves_state(self, editor_client, cve, editor):
        response = editor_client.post(reverse("cves:state", args=[cve.pk]), {"state": "solved"})
        assert response.status_code == 302
        cve.refresh_from_db()
        assert cve.state == "solved"
        assert cve.solved_by == editor

    def test_invalid_state(self, editor_client, cve):
        response = editor_client.post(reverse("cves:state", args=[cve.pk]), {"state": "bogus"})
        assert response.status_code == 400

    def test_viewer_forbidden(self, viewer_client, cve):
        response = viewer_client.post(reverse("cves:state", args=[cve.pk]), {"state": "solved"})
        assert response.status_code == 403
        cve.refresh_from_db()
        assert cve.state == "identified"
        assert not cve.comments.exists()

    def test_get_not_allowed(self, editor_client, cve):
        assert editor_client.get(reverse("cves:state", args=[cve.pk])).status_code == 405


class TestHtmxComments:
    def test_add_returns_row_and_fresh_form(self, editor_client, cve, editor):
        response = editor_client.post(
            reverse("cves:comment-create", args=[cve.pk]), {"text": "Patch ude i aften"}, **HTMX
        )
        assert response.status_code == 200
        body = response.content.decode()
        comment = cve.comments.get()
        assert comment.author == editor
        assert f'id="cve-comment-{comment.pk}"' in body
        assert 'id="cve-comment-form-container" hx-swap-oob="outerHTML"' in body
        assert 'id="no-cve-comments" hx-swap-oob="delete"' in body

    def test_invalid_retargets_form(self, editor_client, cve):
        response = editor_client.post(reverse("cves:comment-create", args=[cve.pk]), {"text": ""}, **HTMX)
        assert response.status_code == 200
        assert response["HX-Retarget"] == "#cve-comment-form-container"
        assert response["HX-Reswap"] == "outerHTML"
        assert not cve.comments.exists()

    def test_viewer_forbidden(self, viewer_client, cve):
        response = viewer_client.post(reverse("cves:comment-create", args=[cve.pk]), {"text": "x"}, **HTMX)
        assert response.status_code == 403
        assert not cve.comments.exists()


class TestHtmxLinks:
    def test_add_and_delete(self, editor_client, cve, editor):
        response = editor_client.post(
            reverse("cves:link-create", args=[cve.pk]),
            {"url": "https://www.openssh.com/security.html", "label": "OpenSSH advisory"},
            **HTMX,
        )
        assert response.status_code == 200
        link = cve.links.get()
        assert link.added_by == editor
        body = response.content.decode()
        assert "OpenSSH advisory" in body
        assert 'id="cve-link-form-container" hx-swap-oob="outerHTML"' in body

        response = editor_client.post(reverse("cves:link-delete", args=[cve.pk, link.pk]), **HTMX)
        assert response.status_code == 200
        assert not CVELink.objects.exists()

    def test_invalid_url_retargets_form(self, editor_client, cve):
        response = editor_client.post(reverse("cves:link-create", args=[cve.pk]), {"url": "ikke en url"}, **HTMX)
        assert response["HX-Retarget"] == "#cve-link-form-container"
        assert not cve.links.exists()

    def test_delete_checks_cve(self, editor_client, cve):
        other = CVE.objects.create(cve_id="CVE-2026-0070", subject="x")
        link = CVELink.objects.create(cve=other, url="https://example.com")
        response = editor_client.post(reverse("cves:link-delete", args=[cve.pk, link.pk]), **HTMX)
        assert response.status_code == 404
        assert CVELink.objects.filter(pk=link.pk).exists()

    def test_viewer_forbidden(self, viewer_client, cve):
        link = CVELink.objects.create(cve=cve, url="https://example.com")
        assert viewer_client.post(
            reverse("cves:link-create", args=[cve.pk]), {"url": "https://example.org"}, **HTMX
        ).status_code == 403
        assert viewer_client.post(reverse("cves:link-delete", args=[cve.pk, link.pk]), **HTMX).status_code == 403
        assert list(cve.links.all()) == [link]


def test_sidebar_has_entry(editor_client):
    body = editor_client.get(reverse("cves:list")).content.decode()
    assert "CVE&#x27;er" in body or "CVE'er" in body


def test_list_intro_links_to_all(editor_client):
    """The intro offers a real "vis alle" link (not a dropdown hint), hidden once showing all."""
    from django.urls import reverse
    body = editor_client.get(reverse("cves:list")).content.decode()
    assert 'href="?state=all"' in body and "vis alle CVE" in body
    body = editor_client.get(reverse("cves:list") + "?state=all").content.decode()
    assert 'href="?state=all"' not in body
