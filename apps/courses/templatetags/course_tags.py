"""Course material links on Chronicle's priorities and cases (``CourseLink``).

Mirrors servicedesk_tags:

* ``{% course_links obj %}``: chips for the priority's history page and the case page.
* ``{% course_pill obj %}``: a small "🎓 Anthropic ↗" pill, for list rows.
* ``{% course_rows obj %}``: the same as a row of its own, for list rows
  that are one big link already (a link can't hold another link).
* ``{% course_export_pill obj %}``: inline styles only, for the week log
  exports. Course pages are public, so these links work for any reader.
* :func:`markdown_links`: the same for the Markdown export.

All render nothing without links. They read ``obj.course_links.all()``,
so list views prefetch ``course_links__folder`` and
``course_links__material__folder``.
"""

from django import template
from django.conf import settings

register = template.Library()


def _links(obj) -> list:
    if obj is None or not getattr(obj, "pk", None):
        return []
    return list(obj.course_links.all())


@register.inclusion_tag("courses/partials/backlinks.html")
def course_links(obj):
    return {"links": _links(obj)}


@register.inclusion_tag("courses/partials/pill.html")
def course_pill(obj):
    return {"links": _links(obj)}


@register.inclusion_tag("courses/partials/pill_rows.html")
def course_rows(obj):
    return {"links": _links(obj)}


def _absolute(url: str) -> str:
    return url if url.startswith(("http://", "https://")) else settings.SITE_URL + url


@register.inclusion_tag("courses/partials/export_pill.html")
def course_export_pill(obj):
    return {"links": [(link, _absolute(link.course_url)) for link in _links(obj)]}


def markdown_links(obj) -> str:
    """`` [Kursus: Anthropic ↗](url)`` per linked course item, for the Markdown export."""
    return "".join(f" [Kursus: {link.course_label} ↗]({_absolute(link.course_url)})" for link in _links(obj))
