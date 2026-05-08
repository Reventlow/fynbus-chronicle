"""Shared template tag for emitting a theme's rotating banner messages.

Replaces the per-theme ``sw_messages_json`` and ``pirate_messages_json``
constants. Both banner templates now read from the DB-backed
``ThemeBannerMessage`` table via this tag.
"""

import json

from django import template
from django.utils.safestring import mark_safe

from apps.themes.models import ThemeBannerMessage

register = template.Library()


@register.simple_tag
def theme_messages_json(slug: str) -> str:
    """Return the active banner messages for ``slug`` as a JSON literal.

    Editors curate copy through the Django admin (Theme → banner messages
    inline), so this tag has no caller-side options — just slug in,
    JSON-array-of-strings out. Empty list if the theme doesn't exist or
    has no active messages, so the template still parses safely.
    """
    texts = list(
        ThemeBannerMessage.objects
        .filter(theme__slug=slug, is_active=True)
        .order_by("order", "id")
        .values_list("text", flat=True)
    )
    return mark_safe(json.dumps(texts, ensure_ascii=False))
