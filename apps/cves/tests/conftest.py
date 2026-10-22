"""Shared fixtures for the CVE tests."""

import pytest
from django.contrib.auth.models import Group, User

from apps.accounts.models import APIKey
from apps.cves.models import CVE


@pytest.fixture
def editor(db):
    return User.objects.create_user("gre", password="x", first_name="Gorm")


@pytest.fixture
def viewer(db):
    user = User.objects.create_user("viewer", password="x")
    group, _ = Group.objects.get_or_create(name="Viewer")
    user.groups.add(group)
    return user


@pytest.fixture
def editor_client(client, editor):
    client.force_login(editor)
    return client


@pytest.fixture
def viewer_client(client, viewer):
    client.force_login(viewer)
    return client


@pytest.fixture
def cve(editor):
    return CVE.objects.create(
        cve_id="CVE-2026-109618", subject="OpenSSH regreSSHion igen", cvss="9.8", created_by=editor
    )


@pytest.fixture
def write_key(db):
    user = User.objects.create_user("harbinger", password="x")
    _, raw = APIKey.generate(user=user, scope=APIKey.Scope.WRITE, label="harbinger")
    return raw


@pytest.fixture
def read_key(db):
    user = User.objects.create_user("reader", password="x")
    _, raw = APIKey.generate(user=user, scope=APIKey.Scope.READ, label="reader")
    return raw
