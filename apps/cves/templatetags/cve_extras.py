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
