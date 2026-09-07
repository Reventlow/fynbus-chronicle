"""The report email has to survive Outlook classic, which renders with Word.

Word ignores flexbox, max-width, border-radius and padding on a <div>,
refuses data: URIs outright, and only reliably paints a background on a
table cell. These tests pin the constructs that keep the mail readable
there; they say nothing about how it looks, only that the known-broken
constructs are absent and the Word-safe ones present.
"""

import re

import pytest
from django.core import mail

from apps.logbook.exports.email import CHART_CID, FLOW_CHART_CID, send_weeklog_email
from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog
from apps.logbook.templatetags.markdown_extras import render_markdown_inline

pytestmark = pytest.mark.django_db


@pytest.fixture
def weeklog(settings):
    settings.CHRONICLE_EMAIL_RECIPIENTS = ["team@fynbus.dk"]
    # The charts need a couple of weeks of history before they render at
    # all, and this suite is about how they travel.
    for week in (33, 34, 35):
        WeekLog.objects.create(
            year=2026, week_number=week, helpdesk_new=10, helpdesk_closed=9, helpdesk_open=40
        )
    weeklog = WeekLog.objects.create(
        year=2026, week_number=36, helpdesk_new=18, helpdesk_closed=15, helpdesk_open=40
    )
    item = PriorityItem.objects.create(
        origin_weeklog=weeklog, title="Veeam", priority="high", status="ongoing"
    )
    PriorityItemAppearance.objects.create(
        priority_item=item,
        weeklog=weeklog,
        description="Trin:\n\n1. Opret bruger\n```bash\nsudo adduser veeam\n```\n",
    )
    return weeklog


@pytest.fixture
def sent(weeklog):
    ok, message = send_weeklog_email(weeklog, format="html", from_email="gorm@fynbus.dk")
    assert ok, message
    return mail.outbox[0]


class TestBodyAvoidsWhatWordCannotRender:
    def test_no_flexbox(self, sent):
        assert "display:flex" not in sent.body
        assert "display: flex" not in sent.body

    def test_no_data_uri_images(self, sent):
        """Outlook classic shows an empty box for these."""
        assert 'src="data:' not in sent.body

    def test_no_max_width_layout(self, sent):
        """Word ignores max-width, so the layout cannot depend on it."""
        assert "max-width:" not in sent.body

    def test_width_is_pinned_by_a_table(self, sent):
        assert 'width="600"' in sent.body


class TestChartsTravelAsInlineAttachments:
    def test_body_references_them_by_cid(self, sent):
        assert f'src="cid:{CHART_CID}"' in sent.body
        assert f'src="cid:{FLOW_CHART_CID}"' in sent.body

    def test_they_are_attached_with_matching_content_ids(self, sent):
        cids = {
            a.get("Content-ID").strip("<>")
            for a in sent.attachments
            if not isinstance(a, tuple)
        }

        assert cids == {CHART_CID, FLOW_CHART_CID}

    def test_the_message_is_multipart_related(self, sent):
        """Otherwise clients list the charts as attachments instead."""
        assert sent.mixed_subtype == "related"
        assert "multipart/related" in sent.message().as_string()

    def test_images_carry_html_width_and_height(self, sent):
        """Word scales images by its own DPI without them."""
        for img in re.findall(r"<img[^>]+>", sent.body):
            if "cid:" in img:
                assert 'width="' in img and 'height="' in img


class TestCodeBlocksSurvive:
    def test_a_code_block_sits_in_a_table_cell_with_bgcolor(self):
        html = render_markdown_inline("```bash\nsudo adduser veeam\n```")

        assert "<table" in html
        assert 'bgcolor="#FAF9F7"' in html

    def test_the_pre_itself_carries_no_frame(self):
        """The cell draws it; Word would ignore it on the <pre>."""
        html = render_markdown_inline("```\nx = 1\n```")
        pre = html[html.index("<pre"): html.index(">", html.index("<pre")) + 1]

        assert "border: 0" in pre
        assert "background: none" in pre

    def test_no_empty_paragraphs(self):
        """Markdown leaves one before each block; Word shows a blank line."""
        html = render_markdown_inline("Tekst\n\n```\nx\n```\n\nMere")

        assert not re.search(r"<p[^>]*>\s*</p>", html)

    def test_the_web_renderer_is_untouched(self):
        """Only exports need the table; the site styles .codehilite itself."""
        from apps.logbook.templatetags.markdown_extras import render_markdown

        html = render_markdown("```bash\nsudo adduser veeam\n```")

        assert "<table" not in html
        assert 'class="codehilite"' in html


class TestPdfStillWorks:
    def test_pdf_renders_with_a_code_block(self, weeklog):
        """The code-block table must not break WeasyPrint."""
        from apps.logbook.exports.pdf import generate_pdf

        pdf = generate_pdf(weeklog)

        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000
