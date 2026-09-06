"""Markdown rendering for priority descriptions and notes.

Two renderers: one for the web (Pygments classes, themed by the site CSS)
and one for exports (every colour and every block inlined, because email
clients strip stylesheets).
"""

import pytest
from django.template.loader import render_to_string

from apps.logbook.exports.markdown import generate_markdown
from apps.logbook.models import PriorityItem, PriorityItemAppearance, WeekLog
from apps.logbook.templatetags.markdown_extras import (
    render_markdown,
    render_markdown_inline,
)

pytestmark = pytest.mark.django_db

SAMPLE = """Vi har **afsluttet** migreringen.

- punkt et
- punkt to med `inline kode`

```python
def sync(week: int) -> None:
    print(f"syncing {week}")
```

| Miljø | Status |
| --- | --- |
| prod | ok |
"""


class TestWebRenderer:
    def test_renders_block_markdown(self):
        html = render_markdown(SAMPLE)

        assert "<strong>afsluttet</strong>" in html
        assert "<li>punkt et</li>" in html
        assert "<code>inline kode</code>" in html
        assert "<table>" in html

    def test_code_block_is_highlighted_with_classes(self):
        html = render_markdown(SAMPLE)

        assert 'class="codehilite"' in html
        # Pygments marks the keyword "def" — that is the highlighting.
        assert '<span class="k">def</span>' in html
        # Web output stays class-based so the site CSS can theme it.
        assert "style=" not in html.split("</table>")[0]

    def test_unlabelled_fence_is_not_guessed(self):
        html = render_markdown("```\njust some text\n```")

        assert "<pre>" in html or "codehilite" in html
        assert '<span class="k">' not in html

    def test_bare_urls_stay_clickable(self):
        html = render_markdown("Se https://fynbus.sharepoint.com/x?a=b for detaljer")

        assert 'href="https://fynbus.sharepoint.com/x?a=b"' in html

    def test_markdown_links_are_not_double_wrapped(self):
        html = render_markdown("[Portainer](https://portainer.fynbus.net)")

        assert html.count("<a ") == 1
        assert ">Portainer</a>" in html

    def test_links_get_noopener(self):
        """nh3 adds rel="noopener noreferrer" to every link it keeps."""
        html = render_markdown("[Portainer](https://portainer.fynbus.net)")

        assert 'rel="noopener noreferrer"' in html

    def test_trailing_punctuation_is_left_out_of_the_link(self):
        html = render_markdown("Se https://example.com/side.")

        assert 'href="https://example.com/side"' in html

    def test_empty_input_is_empty_output(self):
        assert render_markdown("") == ""
        assert render_markdown(None) == ""


class TestRawHtmlIsNeutralised:
    """Descriptions are user input; nothing in them should become markup."""

    def test_script_tags_are_removed(self):
        html = render_markdown("<script>alert('xss')</script>")

        assert "<script>" not in html
        assert "alert" not in html

    def test_event_handlers_do_not_survive(self):
        html = render_markdown('<img src=x onerror="alert(1)">')

        assert "onerror" not in html

    def test_exports_are_neutralised_too(self):
        html = render_markdown_inline("<script>alert('xss')</script>")

        assert "<script>" not in html

    def test_javascript_urls_are_dropped(self):
        html = render_markdown("[klik](javascript:alert(1))")

        assert "javascript:" not in html

    def test_html_inside_a_code_block_is_shown_as_text(self):
        html = render_markdown("```\n<b>bold</b>\n```")

        assert "<b>bold</b>" not in html
        assert "&lt;b&gt;bold&lt;/b&gt;" in html


class TestExportRenderer:
    def test_highlighting_is_inlined(self):
        html = render_markdown_inline(SAMPLE)

        assert 'class="codehilite"' in html
        assert "style=" in html
        # No class-based colouring to depend on.
        assert '<span class="k">' not in html

    def test_block_elements_carry_their_own_styling(self):
        html = render_markdown_inline(SAMPLE)

        assert "<pre style=" in html
        assert "<table style=" in html
        assert "<th style=" in html
        assert "<li style=" in html

    def test_code_inside_pre_does_not_get_the_inline_code_chrome(self):
        html = render_markdown_inline("```\nx = 1\n```")
        code_tag = html[html.index("<code"): html.index(">", html.index("<code")) + 1]

        assert "background: none" in code_tag

    def test_pre_wraps_rather_than_scrolls(self):
        """A PDF page cannot scroll sideways."""
        html = render_markdown_inline("```\n" + "x" * 300 + "\n```")

        assert "white-space: pre-wrap" in html


class TestTemplatesUseIt:
    @pytest.fixture
    def weeklog_with_task(self):
        weeklog = WeekLog.objects.create(year=2026, week_number=36)
        item = PriorityItem.objects.create(
            origin_weeklog=weeklog,
            title="Docker-migrering",
            priority="high",
            status="ongoing",
            notes="Se **noter** her",
        )
        appearance = PriorityItemAppearance.objects.create(
            priority_item=item, weeklog=weeklog, description=SAMPLE
        )
        return weeklog, item, appearance

    def test_weeklog_row_renders_markdown(self, weeklog_with_task):
        _, item, appearance = weeklog_with_task

        html = render_to_string(
            "logbook/partials/priority_item_row.html",
            {"appearance": appearance, "item": item, "is_editor": True},
        )

        assert "<strong>afsluttet</strong>" in html
        assert 'class="codehilite"' in html
        assert 'class="md"' in html

    def test_pdf_and_html_export_render_markdown(self, weeklog_with_task):
        weeklog, _, appearance = weeklog_with_task

        html = render_to_string(
            "logbook/exports/weekly_report.html",
            {"weeklog": weeklog, "priority_items": [appearance]},
        )

        assert "<strong>afsluttet</strong>" in html
        assert "<pre style=" in html

    def test_email_export_renders_markdown(self, weeklog_with_task):
        weeklog, _, appearance = weeklog_with_task

        html = render_to_string(
            "logbook/exports/email_body.html",
            {"weeklog": weeklog, "priority_items": [appearance]},
        )

        assert "<strong>afsluttet</strong>" in html
        assert "<pre style=" in html

    def test_markdown_export_keeps_the_source(self, weeklog_with_task):
        """The .md export is Markdown already — it must not be rendered."""
        weeklog, _, _ = weeklog_with_task

        text = generate_markdown(weeklog)

        assert "**afsluttet**" in text
        assert "```python" in text
