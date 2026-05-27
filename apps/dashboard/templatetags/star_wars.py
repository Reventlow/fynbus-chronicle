"""Phrase-swap template tag for the editorial theme overlays.

Despite the historical ``star_wars`` filename, this library now powers
the phrase-swap mechanism for every theme that re-skins page text
(currently Star Wars + Pirate). Kept under this name so existing
templates with ``{% load star_wars %}`` keep working without churn.

Banner messages used to live here as a hardcoded constant — they're
now in the DB (``ThemeBannerMessage``) and emitted via the shared
``{% theme_messages_json %}`` tag in ``apps.themes.templatetags``.
"""

from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def sw_phrase(
    default: str,
    rebel: str = "",
    sith: str = "",
    pirate: str = "",
    trek: str = "",
    klingon: str = "",
) -> str:
    """Render the default phrase plus optional theme-specific variants.

    All variant spans always render; CSS in ``input.css`` toggles which
    one is visible based on ``data-event`` (+ ``.dark`` for light/dark
    splits). Variants that aren't supplied fall back to ``default``, so
    callers only fill in the themes they want to skin.

    Theme → variant mapping:
      * ``rebel`` — Star Wars light mode.
      * ``sith`` — Star Wars dark mode.
      * ``pirate`` — Pirate Day (same phrase in both modes).
      * ``trek`` — Star Trek light mode (Federation).
      * ``klingon`` — Star Trek dark mode (Klingon). Falls back to
        ``trek`` if omitted, so single-phrase Star Trek skins are easy.
    """
    return format_html(
        '<span class="sw-phrase">'
        '<span class="sw-default">{}</span>'
        '<span class="sw-rebel" aria-hidden="true">{}</span>'
        '<span class="sw-sith" aria-hidden="true">{}</span>'
        '<span class="sw-pirate" aria-hidden="true">{}</span>'
        '<span class="sw-trek" aria-hidden="true">{}</span>'
        '<span class="sw-klingon" aria-hidden="true">{}</span>'
        "</span>",
        default,
        rebel or default,
        sith or default,
        pirate or default,
        trek or default,
        klingon or trek or default,
    )
