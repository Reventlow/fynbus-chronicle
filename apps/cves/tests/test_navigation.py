"""Navigation in "Sårbarheder og hændelser" (1.25.0).

After a UI review and user tests: the section lands on Sager, every page has
the Sager | CVE'er | Delopgaver tabs, crumbs follow sag → CVE, the task list
round-trips through ``next``, every new CVE goes into a sag, and an incident
without CVEs shows its delopgaver.
"""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cves.models import CVE, CVECase, CVETask
from apps.logbook.models import WeekLog


@pytest.fixture
def case(editor):
    return CVECase.objects.create(title="PHP session", created_by=editor)


@pytest.fixture
def incident(editor):
    return CVECase.objects.create(title="Phishing-kampagne", kind=CVECase.Kind.INCIDENT, created_by=editor)


class TestSectionNav:
    def test_sidebar_and_mobile_menu_land_on_sager(self, editor_client):
        body = editor_client.get(reverse("dashboard:index")).content.decode()
        sager = reverse("cves:case-list")
        assert f'<a href="{sager}" title="Sårbarheder og hændelser"' in body
        assert f'<a href="{sager}" class="nav-link">Sårbarheder og hændelser</a>' in body

    @pytest.mark.parametrize("page, active", [
        ("list", "CVE&#x27;er"), ("case-list", "Sager"), ("task-list", "Delopgaver"), ("create", "CVE&#x27;er"),
    ])
    def test_every_page_has_the_three_tabs(self, editor_client, page, active):
        body = editor_client.get(reverse(f"cves:{page}")).content.decode()
        assert '<nav aria-label="Sårbarheder og hændelser" class="tab-list"' in body
        for url in ("cves:case-list", "cves:list", "cves:task-list"):
            assert f'href="{reverse(url)}"' in body
        assert body.count('aria-current="page"') == 1
        tab = body.split('aria-current="page">', 1)[1].strip()
        assert tab.startswith(active)

    def test_detail_pages_have_the_tabs_too(self, editor_client, case, cve):
        assert 'class="tab-list"' in editor_client.get(case.get_absolute_url()).content.decode()
        assert 'class="tab-list"' in editor_client.get(cve.get_absolute_url()).content.decode()

    def test_task_list_is_open_to_viewers(self, viewer_client):
        assert viewer_client.get(reverse("cves:task-list")).status_code == 200
        assert reverse("cves:task-list") in viewer_client.get(reverse("cves:case-list")).content.decode()


class TestCrumbs:
    def test_cve_in_a_sag_shows_the_sag_as_parent(self, editor_client, case, cve):
        case.add_cves([cve])
        body = editor_client.get(cve.get_absolute_url()).content.decode()
        assert f'<a href="{case.get_absolute_url()}">Sag #{case.pk}</a>' in body

    def test_cve_without_a_sag_shows_the_cve_list(self, editor_client, cve):
        body = editor_client.get(cve.get_absolute_url()).content.decode()
        assert f'<a href="{reverse("cves:list")}">CVE\'er</a>' in body


class TestIncidentTasks:
    def test_incident_without_cves_shows_its_delopgaver(self, editor_client, incident, editor):
        """The bug: the tasks card sat inside "is vulnerability or has CVEs"."""
        task = CVETask.add(incident, title="Nulstil adgangskoder", user=editor)
        body = editor_client.get(incident.get_absolute_url()).content.decode()
        assert f'id="task-{task.pk}"' in body and "Tilføj delopgave" in body
        assert "Tilføj CVE til sagen" in body  # an editor can still add a CVE

    def test_task_counter_does_not_count_waiting_twice(self, editor_client, case, editor):
        CVETask.add(case, title="a", user=editor)
        CVETask.add(case, title="b", user=editor, status=CVETask.Status.WAITING_PATCH)
        body = editor_client.get(case.get_absolute_url()).content.decode()
        assert "1 åben\n      · 1 venter på patch" in body

    def test_add_form_has_visible_labels(self, editor_client, case):
        body = editor_client.get(case.get_absolute_url()).content.decode()
        for field in ("Ny delopgave", "Ansvarlig", "Frist", "Note"):
            assert f'class="input-label">{field}</label>' in body

    def test_overdue_says_so_in_words(self, editor_client, case, editor):
        CVETask.add(case, title="Sent", user=editor, due_date=timezone.localdate() - timedelta(days=2))
        assert "(overskredet)" in editor_client.get(case.get_absolute_url()).content.decode()
        assert "1 overskredet" in editor_client.get(reverse("cves:task-list")).content.decode()


class TestNextRoundTrip:
    def test_task_list_links_carry_next_and_saving_returns(self, editor_client, case, editor):
        task = CVETask.add(case, title="Opdatér", user=editor)
        list_url = reverse("cves:task-list") + "?status=open"
        body = editor_client.get(list_url).content.decode()
        assert "?next=/cves/tasks/%3Fstatus%3Dopen#task-" in body
        page = editor_client.get(case.get_absolute_url(), {"next": list_url}).content.decode()
        assert "Tilbage til delopgaverne" in page and f'name="next" value="{list_url}"' in page
        response = editor_client.post(reverse("cves:case-task-status", args=[case.pk, task.pk]),
                                      {"status": "done", "next": list_url})
        assert response.url == list_url

    def test_foreign_next_is_ignored(self, editor_client, case, editor):
        task = CVETask.add(case, title="Opdatér", user=editor)
        response = editor_client.post(reverse("cves:case-task-status", args=[case.pk, task.pk]),
                                      {"status": "done", "next": "https://evil.example/"})
        assert response.url == case.get_absolute_url() + "#opgaver"


class TestEveryCVEInASag:
    def test_new_cve_can_join_an_existing_sag(self, editor_client, case):
        response = editor_client.post(reverse("cves:create"), {
            "cve_id": "CVE-2026-1234", "subject": "Kerne", "sag": case.pk})
        cve = CVE.objects.get(cve_id="CVE-2026-1234")
        assert cve.case == case and response.url == case.get_absolute_url()
        assert CVECase.objects.count() == 1

    def test_sag_can_be_preselected(self, editor_client, case):
        body = editor_client.get(reverse("cves:create") + f"?sag={case.pk}").content.decode()
        assert f'<option value="{case.pk}" selected>' in body

    def test_cve_page_has_no_free_state_buttons(self, editor_client, cve):
        body = editor_client.get(cve.get_absolute_url()).content.decode()
        assert reverse("cves:state", args=[cve.pk]) not in body and "Ikke i en sag" in body

    def test_sager_list_points_at_cves_without_a_sag(self, editor_client, case, cve):
        body = editor_client.get(reverse("cves:case-list")).content.decode()
        assert "</strong> åben CVE er ikke i en sag endnu." in body
        listed = editor_client.get(reverse("cves:list") + "?sag=ingen").context["cves"]
        assert list(listed) == [cve]
        case.add_cves([cve])
        assert "ikke i en sag endnu" not in editor_client.get(reverse("cves:case-list")).content.decode()

    def test_cancel_on_new_sag_from_a_cve_goes_back_to_it(self, editor_client, cve):
        body = editor_client.get(reverse("cves:case-create") + f"?cve_ids={cve.cve_id}").content.decode()
        assert f'<a href="{cve.get_absolute_url()}" class="btn btn-sm">Annullér</a>' in body


class TestListsAndWording:
    def test_search_finds_old_solved_cves(self, editor_client, editor):
        old = CVE.objects.create(cve_id="CVE-2025-0001", subject="Gammel Exchange", state=CVE.State.SOLVED)
        CVE.objects.filter(pk=old.pk).update(updated_at=timezone.now() - timedelta(days=200),
                                             solved_at=timezone.now() - timedelta(days=200))
        assert old not in editor_client.get(reverse("cves:list")).context["cves"]
        assert old in editor_client.get(reverse("cves:list") + "?q=Exchange").context["cves"]

    def test_ready_for_review_sorts_before_solved(self, editor):
        solved = CVECase.objects.create(title="a", state=CVE.State.SOLVED)
        review = CVECase.objects.create(title="b", state=CVE.State.REVIEW)
        CVECase.objects.filter(pk=solved.pk).update(updated_at=timezone.now() + timedelta(hours=1))
        assert list(CVECase.objects.open_first()) == [review, solved]

    def test_plural_is_aabne(self, editor_client, editor):
        CVECase.objects.create(title="a")
        CVECase.objects.create(title="b")
        body = editor_client.get(reverse("cves:case-list")).content.decode()
        assert "<span>2 åbne</span>" in body and "åbene" not in body

    def test_new_sag_heading_follows_the_kind(self, editor_client):
        for kind, heading in (("incident", "Ny hændelse"), ("task", "Nyt planlagt arbejde"), ("", "Ny sårbarhedssag")):
            body = editor_client.get(reverse("cves:case-create") + f"?kind={kind}").content.decode()
            assert f"<title>{heading} — FynBus Chronicle</title>" in body


def test_week_list_counts_incident_sager(editor_client, incident):
    year, week, _ = date.today().isocalendar()
    WeekLog.objects.create(year=year, week_number=week)
    body = editor_client.get(reverse("logbook:weeklog-list")).content.decode()
    assert "1 hændelse<" in body


class TestReviewFixes:
    def test_failed_save_stays_on_the_sag_and_keeps_next(self, editor_client, case, editor):
        task = CVETask.add(case, title="Opdatér", user=editor)
        list_url = reverse("cves:task-list") + "?status=open"
        response = editor_client.post(reverse("cves:case-task-status", args=[case.pk, task.pk]),
                                      {"status": "ignored", "note": "", "next": list_url})
        assert response.url == case.get_absolute_url() + "?next=%2Fcves%2Ftasks%2F%3Fstatus%3Dopen#opgaver"

    def test_only_open_sager_are_offered_to_a_new_cve(self, editor_client, case, editor):
        closed = CVECase.objects.create(title="Gammel", state=CVE.State.SOLVED)
        body = editor_client.get(reverse("cves:create")).content.decode()
        assert f'<option value="{case.pk}"' in body and f'<option value="{closed.pk}"' not in body

    def test_harbinger_source_carries_to_the_new_sag(self, editor_client):
        editor_client.post(reverse("cves:create"), {"cve_id": "CVE-2026-4321", "subject": "x",
                                                     "source_url": "https://harbinger.example.test/hit/1"})
        case = CVE.objects.get(cve_id="CVE-2026-4321").case
        assert (case.source, case.source_url) == ("harbinger", "https://harbinger.example.test/hit/1")

    def test_filter_form_keeps_the_without_sag_view(self, editor_client):
        body = editor_client.get(reverse("cves:list") + "?sag=ingen").content.decode()
        assert '<input type="hidden" name="sag" value="ingen">' in body
