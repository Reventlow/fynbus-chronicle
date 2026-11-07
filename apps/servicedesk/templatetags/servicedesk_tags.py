"""ServiceDesk links on Chronicle's priorities and cases (``TicketLink``).

* ``{% ticket_links obj %}``: chips with ticket number and subject, for
  the priority's history page and the case page.
* ``{% ticket_pill obj %}``: a small "ServiceDesk #1234 ↗" pill, for list rows.
* ``{% ticket_rows obj %}``: the same as a row of its own, for list rows
  that are one big link already (a link can't hold another link).
* ``{% ticket_export_pill obj %}``: the pill with inline styles only, for
  the week log exports (HTML, PDF and the mail body pasted into Outlook).
* :func:`markdown_links`: the same for the Markdown export.

All render nothing without links. The list tags read
``obj.ticket_links.all()``, so the views prefetch ``ticket_links`` and a
list costs no extra query per row.
"""

from django import template

register = template.Library()


def _links(obj) -> list:
    if obj is None or not getattr(obj, "pk", None):
        return []
    return list(obj.ticket_links.all())


@register.inclusion_tag("servicedesk/partials/backlinks.html")
def ticket_links(obj):
    return {"links": _links(obj)}


@register.inclusion_tag("servicedesk/partials/pill.html")
def ticket_pill(obj):
    return {"links": _links(obj)}


@register.inclusion_tag("servicedesk/partials/pill_rows.html")
def ticket_rows(obj):
    return {"links": _links(obj)}


@register.inclusion_tag("servicedesk/partials/export_pill.html")
def ticket_export_pill(obj):
    return {"links": _links(obj)}


def markdown_links(obj) -> str:
    """`` [ServiceDesk #1234 ↗](url)`` per linked ticket, for the Markdown export."""
    return "".join(f" [ServiceDesk #{link.sdp_id} ↗]({link.ticket_url})" if link.ticket_url
                   else f" (ServiceDesk #{link.sdp_id})" for link in _links(obj))
