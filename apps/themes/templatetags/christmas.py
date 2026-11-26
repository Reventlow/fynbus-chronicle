"""Template tag for the Christmas theme's kalenderlys (apps/themes/candle.py)."""

from django import template
from django.utils import timezone

from apps.themes.candle import DAYS, candle_state

register = template.Library()


def _local_now():
    """Django's local wall-clock time, naive (a seam for the tests)."""
    return timezone.localtime().replace(tzinfo=None)


def candle_caption(day: int, lit: bool) -> str:
    """The line under the date: days left, Christmas Eve, or burnt out.

    Mirrored by ``candleCaption`` in static/js/christmas-parade.js.
    """
    if not lit:
        return "Brændt ned. Glædelig jul!"
    left = DAYS - day
    if left == 0:
        return "Juleaften: det sidste mærke brænder i dag"
    return f"{left} {'dag' if left == 1 else 'dage'} til juleaften"


@register.inclusion_tag("components/christmas_candle.html", takes_context=True)
def christmas_candle(context, variant: str = "dash") -> dict:
    """Render the kalenderlys as it stands right now (Django local time).

    ``variant`` is "sidebar" (above the sidebar's on-call mini card) or
    "dash" (above the Kontrolpanel's on-call card, which only shows on
    phones and with the sidebar collapsed); CSS shows the one that sits
    above the visible on-call card, and only while the Christmas theme is
    on. The script refreshes both from the browser's clock every few
    minutes.

    Not rendered at all while the server has put another theme on (a
    schedule or ?force-theme=). With no server theme it is rendered and
    left to CSS, because a user's own theme pick lives in localStorage
    and is only known in the browser.
    """
    active = context.get("ACTIVE_THEME") or ""
    if active not in ("", "christmas"):
        return {"show": False}
    state = candle_state(_local_now())
    return {
        "show": True,
        "variant": variant,
        "state": state,
        # Pre-formatted: the Danish locale would print "0,5" in a template,
        # which is not a number to CSS.
        "remaining": f"{state.remaining:.4f}",
        "caption": candle_caption(state.day, state.lit),
        "marks": range(1, DAYS + 1),
    }
