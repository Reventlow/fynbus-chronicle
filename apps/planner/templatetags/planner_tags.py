"""``{% planner_links obj %}``: the Planner cards a priority or case is
linked to, as chips that open the card in Planner. Renders nothing when
the Planner board is off or there are no links."""

from django import template
from django.conf import settings

from apps.planner.models import PlannerLink, PlannerTask

register = template.Library()


@register.inclusion_tag("planner/partials/backlinks.html")
def planner_links(obj):
    links = []
    if settings.PLANNER_ENABLED and obj is not None and obj.pk:
        field = "case" if getattr(obj, "is_case", False) else "priority_item"
        links = list(PlannerLink.objects.filter(**{field: obj}))
        titles = dict(PlannerTask.objects.filter(id__in=[link.task_id for link in links])
                      .values_list("id", "title"))
        for link in links:
            link.current_title = titles.get(link.task_id)
    return {"links": links}
