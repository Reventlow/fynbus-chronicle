"""Context processor exposing feedback-board state to every template.

Adds ``OPEN_FEEDBACK_COUNT`` — the number of feature requests that are
either open or in progress — so the global nav can show a notification
badge on "Forslag". Anonymous users get 0 (the link is hidden anyway).
"""

from django.db.models import Q

from .models import FeatureRequest


def feedback_badge(request):
    if not request.user.is_authenticated:
        return {"OPEN_FEEDBACK_COUNT": 0}
    count = FeatureRequest.objects.filter(
        Q(status=FeatureRequest.Status.OPEN)
        | Q(status=FeatureRequest.Status.IN_PROGRESS)
    ).count()
    return {"OPEN_FEEDBACK_COUNT": count}
