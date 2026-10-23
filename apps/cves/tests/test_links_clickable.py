"""Links on a CVE are clickable: the links list and URLs in comments."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.cves.models import CVEComment, CVELink
from apps.cves.templatetags.cve_extras import cve_markdown

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("text,href", [
    ("Se https://www.fortiguard.com/psirt/FG-IR-26-161 nu", "https://www.fortiguard.com/psirt/FG-IR-26-161"),
    ("Læs www.fortinet.com/support.", "https://www.fortinet.com/support"),
    ("[advisory](https://example.org/a)", "https://example.org/a"),
])
def test_comment_urls_become_new_tab_links(text, href):
    html = cve_markdown(text)
    assert f'href="{href}"' in html
    assert 'target="_blank"' in html and "noopener" in html


def test_email_addresses_and_scripts_are_not_linked():
    assert "<a" not in cve_markdown("skriv til gre@www.fynbus.dk")
    html = cve_markdown("<script>alert(1)</script> tekst")
    assert "<script" not in html


def test_link_rows_and_comments_render_clickable(editor, cve):
    c = Client()
    c.force_login(editor)
    CVELink.objects.create(cve=cve, url="https://www.fortiguard.com/psirt/FG-IR-26-161", label="FortiGuard PSIRT", added_by=editor)
    CVEComment.objects.create(cve=cve, text="Se også www.fortinet.com/support", author=editor)
    body = c.get(reverse("cves:detail", args=[cve.pk])).content.decode()
    # title and the URL line are both links to the target, in a new tab
    assert body.count('href="https://www.fortiguard.com/psirt/FG-IR-26-161" target="_blank"') == 2
    assert "FortiGuard PSIRT" in body and "↗" in body
    assert 'href="https://www.fortinet.com/support"' in body
