"""The sidebar and mobile menu link to Django admin, for staff only."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

ADMIN_NAV = 'title="Administration"'
ADMIN_MOBILE = f'<a href="{reverse("admin:index")}" class="nav-link">Admin</a>'


@pytest.mark.django_db
def test_staff_see_admin_in_the_menus(client):
    client.force_login(User.objects.create_user("staffer", is_staff=True))
    body = client.get(reverse("dashboard:index")).content.decode()
    assert ADMIN_NAV in body
    assert ADMIN_MOBILE in body


@pytest.mark.django_db
def test_other_users_do_not(client):
    client.force_login(User.objects.create_user("viewer"))
    body = client.get(reverse("dashboard:index")).content.decode()
    assert ADMIN_NAV not in body
    assert ADMIN_MOBILE not in body
