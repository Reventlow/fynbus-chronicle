"""Editing one's own timeline comment on a CVE or a case."""

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.cves.models import CVECase, CVEComment

pytestmark = pytest.mark.django_db


def login(user) -> Client:
    """Own Client per user: conftest's editor/viewer clients share one."""
    c = Client()
    c.force_login(user)
    return c


@pytest.fixture
def comment(cve, editor):
    return CVEComment.objects.create(cve=cve, text="Første udkast", author=editor)


def edit_url(comment):
    return reverse("cves:comment-edit", args=[comment.cve_id, comment.pk])


class TestEditOwnComment:
    def test_author_sees_edit_button_on_the_page(self, cve, editor, comment):
        body = login(editor).get(reverse("cves:detail", args=[cve.pk])).content.decode()
        assert edit_url(comment) in body and "Redigér kommentar" in body

    def test_get_returns_form_with_current_text(self, editor, comment):
        body = login(editor).get(edit_url(comment), HTTP_HX_REQUEST="true").content.decode()
        assert "Første udkast" in body and "Gem" in body and "Annullér" in body
        assert f'id="comment-{comment.pk}-text"' in body  # not clashing with the add form's id

    def test_post_saves_and_marks_edited(self, cve, editor, comment):
        before = cve.updated_at
        response = login(editor).post(edit_url(comment), {"text": "Rettet **tekst**"}, HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        comment.refresh_from_db()
        assert comment.text == "Rettet **tekst**" and comment.edited_at is not None
        body = response.content.decode()
        assert "<strong>tekst</strong>" in body and "redigeret" in body
        cve.refresh_from_db()
        assert cve.updated_at > before

    def test_unchanged_text_is_not_marked_edited(self, editor, comment):
        login(editor).post(edit_url(comment), {"text": "Første udkast"}, HTTP_HX_REQUEST="true")
        comment.refresh_from_db()
        assert comment.edited_at is None

    def test_empty_text_is_rejected(self, editor, comment):
        body = login(editor).post(edit_url(comment), {"text": ""}, HTTP_HX_REQUEST="true").content.decode()
        assert "input-error-message" in body
        comment.refresh_from_db()
        assert comment.text == "Første udkast"

    def test_cancel_returns_unchanged_row(self, editor, comment):
        url = reverse("cves:comment", args=[comment.cve_id, comment.pk])
        body = login(editor).get(url, HTTP_HX_REQUEST="true").content.decode()
        assert "Første udkast" in body and f'id="cve-comment-{comment.pk}"' in body


class TestWhoMayEdit:
    def test_other_editor_cannot_edit_or_see_button(self, cve, comment):
        other = login(User.objects.create_user("kollega", password="x"))
        assert edit_url(comment) not in other.get(reverse("cves:detail", args=[cve.pk])).content.decode()
        assert other.get(edit_url(comment)).status_code == 403
        assert other.post(edit_url(comment), {"text": "kapret"}).status_code == 403
        comment.refresh_from_db()
        assert comment.text == "Første udkast"

    def test_viewer_cannot_edit(self, viewer, comment):
        assert login(viewer).post(edit_url(comment), {"text": "x"}).status_code == 403

    def test_state_changes_are_not_editable(self, cve, editor):
        state = CVEComment.objects.create(cve=cve, text="Status: Patcher", author=editor, kind=CVEComment.Kind.STATE)
        assert login(editor).get(edit_url(state)).status_code == 403

    def test_comment_must_belong_to_the_cve_in_the_url(self, cve, editor, comment):
        assert login(editor).get(reverse("cves:comment-edit", args=[cve.pk + 999, comment.pk])).status_code == 404


def test_case_comment_edit(editor):
    case = CVECase.objects.create(title="Orientering: kendte IOC'er")
    comment = CVEComment.objects.create(case=case, text="IP'er tjekket", author=editor)
    c = login(editor)
    url = reverse("cves:case-comment-edit", args=[case.pk, comment.pk])
    assert url in c.get(reverse("cves:case-detail", args=[case.pk])).content.decode()
    c.post(url, {"text": "IP'er tjekket i Traffic 25.10–27.10"}, HTTP_HX_REQUEST="true")
    comment.refresh_from_db()
    assert comment.text.startswith("IP'er tjekket i Traffic") and comment.edited_at
