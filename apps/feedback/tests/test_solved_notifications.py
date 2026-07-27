"""Tests for bell notifications when a feature request is marked solved."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from apps.feedback.models import FeatureRequest
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def submitter():
    return User.objects.create_user("mra", password="x", first_name="Mia")


@pytest.fixture
def editor():
    user = User.objects.create_user("gorm", password="x", is_staff=True)
    return user


@pytest.fixture
def request_obj(submitter):
    return FeatureRequest.objects.create(
        title="Fjerne nedtoning ved afsluttet",
        submitted_by=submitter,
    )


class TestMarkSolvedNotifies:
    def test_submitter_gets_notification(self, request_obj, submitter, editor):
        request_obj.mark_solved(by=editor)
        notification = Notification.objects.get(recipient=submitter)
        assert request_obj.title in notification.message
        assert notification.url == reverse(
            "feedback:detail", kwargs={"pk": request_obj.pk}
        )

    def test_no_duplicate_when_already_solved(self, request_obj, submitter, editor):
        request_obj.mark_solved(by=editor)
        request_obj.mark_solved(by=editor)
        assert Notification.objects.filter(recipient=submitter).count() == 1

    def test_self_solve_stays_silent(self, request_obj, submitter):
        request_obj.mark_solved(by=submitter)
        assert Notification.objects.count() == 0

    def test_no_submitter_no_crash(self, editor):
        obj = FeatureRequest.objects.create(title="Anonymt forslag")
        obj.mark_solved(by=editor)
        assert Notification.objects.count() == 0

    def test_reopen_then_solve_notifies_again(self, request_obj, submitter, editor):
        request_obj.mark_solved(by=editor)
        request_obj.reopen()
        request_obj.mark_solved(by=editor)
        assert Notification.objects.filter(recipient=submitter).count() == 2
