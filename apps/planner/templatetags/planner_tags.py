"""Planner links on Chronicle's priorities and cases (``PlannerLink``).

* ``{% planner_links obj %}``: chips with the card's title, for the
  priority's history page and the case page; without a link, "Opret i
  Planner" for editors who have connected their Microsoft account.
* ``{% planner_pill obj %}``: a small "Planner ↗" pill, for list rows.
* ``{% planner_rows obj %}``: the same as a row of its own, for list rows
  that are one big link already (a link can't hold another link).
* ``{% planner_export_pill obj %}``: the pill with inline styles only, for
  the week log exports (HTML, PDF and the mail body pasted into Outlook).

All render nothing when the Planner board is off or there are no links.
The list tags read ``obj.planner_links.all()``, so the views prefetch
``planner_links`` and a list costs no extra query per row.
"""

from django import template
from django.conf import settings

from apps.planner.models import PlannerLink, PlannerTask

register = template.Library()


@register.inclusion_tag("planner/partials/backlinks.html", takes_context=True)
def planner_links(context, obj):
    """Chips for the linked cards (with a note if a status change didn't
    reach Planner), or "Opret i Planner" for an editor who has connected."""
    ctx = {"links": [], "obj": obj}
    if not settings.PLANNER_ENABLED or obj is None or not obj.pk:
        return ctx
    from apps.planner.models import PlannerBucket, PlannerChange
    from apps.planner.views import can_write

    is_case = getattr(obj, "is_case", False)
    field = "case" if is_case else "priority_item"
    links = list(PlannerLink.objects.filter(**{field: obj}))
    titles = dict(PlannerTask.objects.filter(id__in=[link.task_id for link in links]).values_list("id", "title"))
    for link in links:
        link.current_title = titles.get(link.task_id)
    ctx["links"] = links
    request = context.get("request")
    user = getattr(request, "user", None)
    if links or user is None or not user.is_authenticated:
        return ctx
    ctx["creating"] = PlannerChange.objects.filter(
        kind=PlannerChange.Kind.CREATE, status=PlannerChange.Status.PENDING,
        **{f"payload__link__{field}": obj.pk}).exists()
    from apps.accounts.permissions import is_editor
    if is_editor(user) and not getattr(obj, "is_deleted", False):
        ctx["can_create"] = can_write(user)
        ctx["can_connect"] = settings.PLANNER_WRITES_ENABLED and not ctx["can_create"]
        ctx["buckets"] = list(PlannerBucket.objects.filter(plan_id=settings.PLANNER_PLAN_ID).order_by("-order_hint"))
        ctx["target"] = f"{'c' if is_case else 'p'}{obj.pk}"
        ctx["csrf_token"] = context.get("csrf_token")
    return ctx


def _links(obj) -> list:
    if not settings.PLANNER_ENABLED or obj is None or not obj.pk:
        return []
    return list(obj.planner_links.all())


@register.inclusion_tag("planner/partials/pill.html")
def planner_pill(obj):
    return {"links": _links(obj)}


@register.inclusion_tag("planner/partials/pill_rows.html")
def planner_rows(obj):
    return {"links": _links(obj)}


@register.inclusion_tag("planner/partials/export_pill.html")
def planner_export_pill(obj):
    return {"links": _links(obj)}


def markdown_links(obj) -> str:
    """`` [Planner ↗](url)`` per linked card, for the Markdown export."""
    return "".join(f" [Planner ↗]({link.task_url})" for link in _links(obj))
