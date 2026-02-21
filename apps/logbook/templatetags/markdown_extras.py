"""Template filters for rendering Markdown and splitting strings."""

import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="render_markdown")
def render_markdown(value: str) -> str:
    """Render a Markdown string as safe HTML."""
    if not value:
        return ""
    html = markdown.markdown(
        value,
        extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
    )
    return mark_safe(html)


@register.filter(name="split_commas")
def split_commas(value: str) -> list[str]:
    """Split a comma-separated string into a list of trimmed strings."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
