"""Template helpers for the CVE section."""

import re

from django import template
from django.utils.safestring import mark_safe

from apps.logbook.templatetags.markdown_extras import render_markdown

register = template.Library()

# A bare "www.example.com/path" that is not already part of a URL, a Markdown
# link target or an autolink.
_BARE_WWW = re.compile(r"(?<![\w/:.@\[(<])(www\.[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+(?:/[^\s<>()\[\]]*)?)")


@register.filter
def cve_markdown(value: str) -> str:
    """Render a CVE comment like ``render_markdown``, with clickable links.

    * a bare ``www.…`` address becomes a link (as https), like a URL with
      a scheme already does;
    * every link opens in a new tab, so the CVE page stays open.

    The HTML comes from ``render_markdown`` (nh3-sanitised), so adding the
    target attribute to its ``<a`` tags is safe.
    """
    text = _BARE_WWW.sub(lambda m: f"<https://{m.group(1).rstrip('.,;:!?')}>{m.group(1)[len(m.group(1).rstrip('.,;:!?')):]}", value or "")
    html = str(render_markdown(text))
    html = re.sub(r"<a (?![^>]*\btarget=)", '<a target="_blank" ', html)
    return mark_safe(html)


@register.simple_tag
def owner_url(owner, name: str, *args) -> str:
    """URL of a per-owner view for a CVE or a case: ``{% owner_url owner 'link-create' %}``."""
    return owner.owner_url(name, *args)


def _tab_count(open_count: int, total: int) -> dict:
    """Tab badge: the open count on the badge, both numbers in its tooltip."""
    return {"count": f"{open_count} åben" if open_count == 1 else f"{open_count} åbne",
            "title": f"{open_count} {'åben' if open_count == 1 else 'åbne'} · {total} i alt"}


@register.inclusion_tag("components/tabs.html", takes_context=True)
def cve_section_nav(context) -> dict:
    """The "Sager | CVE'er | Delopgaver" tabs on every page of the section.

    The active tab follows the URL name: case pages → Sager, the task list →
    Delopgaver, everything else (CVE list, detail, forms) → CVE'er.
    """
    from django.urls import reverse

    from ..models import CVE, CVECase, CVETask

    match = getattr(context.get("request"), "resolver_match", None)
    name = match.url_name if match else ""
    current = "tasks" if name == "task-list" else "cases" if name.startswith("case-") else "cves"
    tasks = CVETask.objects.exclude(case__kind=CVECase.Kind.TASK)
    return {
        "tabs": [
            {"key": "cases", "label": "Sager", "url": reverse("cves:case-list"),
             **_tab_count(CVECase.objects.open().count(), CVECase.objects.count())},
            {"key": "cves", "label": "CVE'er", "url": reverse("cves:list"),
             **_tab_count(CVE.objects.open().count(), CVE.objects.count())},
            {"key": "tasks", "label": "Delopgaver", "url": reverse("cves:task-list"),
             **_tab_count(tasks.filter(status__in=CVETask.OPEN_STATUSES).count(), tasks.count())},
        ],
        "current_tab": current,
        "nav_label": "Sårbarheder og hændelser",
    }
