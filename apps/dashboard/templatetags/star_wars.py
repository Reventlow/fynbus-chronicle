"""Template tag that emits all three phrasings of a label so CSS can pick
the right one when the May 4th Star Wars Day skin is active.

Usage::

    {% load star_wars %}
    {% sw_phrase "Lukkede sager" "Fuldførte missioner" "Oprørere fanget" %}

Always renders Danish; the rebel/sith variants stay hidden via CSS unless
``data-event="star-wars"`` is on the ``<html>`` element. Inside the skin,
light mode shows the rebel variant and dark mode shows the sith one.
"""

from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def sw_phrase(default: str, rebel: str = "", sith: str = "") -> str:
    """Render the default phrase plus optional rebel/sith variants."""
    return format_html(
        '<span class="sw-phrase">'
        '<span class="sw-default">{}</span>'
        '<span class="sw-rebel" aria-hidden="true">{}</span>'
        '<span class="sw-sith" aria-hidden="true">{}</span>'
        "</span>",
        default,
        rebel or default,
        sith or default,
    )
