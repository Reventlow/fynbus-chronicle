"""Footer link to udviklingsgruppen.dk (1.27.1): every page's footer credits
udviklingsgruppen, opens the homelab site in a new tab and sends no referrer,
so Chronicle's internal addresses never reach that server's logs."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_footer_links_to_udviklingsgruppen(client):
    client.force_login(User.objects.create_user("gre", password="x"))
    html = client.get(reverse("dashboard:index")).content.decode()
    assert 'href="https://udviklingsgruppen.dk"' in html
    tag = html[html.index('href="https://udviklingsgruppen.dk"') - 200:html.index(">udviklingsgruppen</a>")]
    assert 'rel="noopener noreferrer"' in tag
    assert 'target="_blank"' in tag
