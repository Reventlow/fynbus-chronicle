"""
Service layer for on-call assignment changes (FR #5).

``apply_assignment`` is the single write path for duty, coverage
segments and the audit trail — claim, release and the assign form all
go through it. Never write those tables directly from views: the
invariants (segments never overlap, ``duty.user`` equals the holder of
the week's last segment, every real change leaves an audit row) only
hold because every mutation funnels through here.
"""

from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.notifications.models import Notification

from .models import OnCallChange, OnCallDuty, OnCallSegment, boundary_label, week_span


def _display_name(user: User) -> str:
    return user.get_full_name() or user.username


def _calendar_url(year: int, week: int) -> str:
    return f"{reverse('oncall:calendar')}#oncall-week-{year}-{week}"


@transaction.atomic
def apply_assignment(
    year: int,
    week: int,
    new_user: User | None,
    effective_at: datetime,
    changed_by: User | None,
    notes: str | None = None,
) -> OnCallChange | None:
    """Assign ``new_user`` (or free the week when None) from ``effective_at``.

    Coverage before ``effective_at`` is preserved; everything from that
    moment to the end of the week is rewritten. Returns the audit row,
    or None when the change was a no-op (same holder — HTMX double
    submits and retries must not spam the audit trail).

    ``notes`` replaces the duty notes when given (None = leave as-is).
    A notes-only change writes no audit row.
    """
    week_start, week_end = week_span(year, week)
    effective_at = effective_at.replace(second=0, microsecond=0)
    effective_at = max(effective_at, week_start)
    if effective_at >= week_end:
        raise ValueError(f"effective_at {effective_at} is outside uge {week}, {year}")

    duty = (
        OnCallDuty.objects.select_for_update()
        .filter(year=year, week_number=week)
        .select_related("user")
        .first()
    )
    segments = OnCallSegment.objects.filter(year=year, week_number=week)

    covering = segments.filter(start_at__lte=effective_at, end_at__gt=effective_at).select_related("user").first()
    if covering is not None:
        old_user = covering.user
    else:
        old_user = duty.user if duty is not None else None

    # Everyone whose recorded coverage overlaps the rewritten tail —
    # on a split week that can be more people than the holder at
    # effective_at, and all of them deserve a notification.
    tail = list(segments.filter(end_at__gt=effective_at).select_related("user").order_by("start_at"))
    new_pk = new_user.pk if new_user else None

    if _is_noop(tail, duty, new_pk, effective_at, week_end):
        if duty is not None and notes is not None and duty.notes != notes:
            duty.notes = notes
            duty.save(update_fields=["notes", "updated_at"])
        return None

    displaced = {s.user for s in tail if s.user_id != new_pk}

    # Rewrite coverage from effective_at: truncate the straddling
    # segment, drop everything that starts later.
    if covering is not None and covering.start_at < effective_at:
        covering.end_at = effective_at
        covering.save(update_fields=["end_at"])
    segments.filter(start_at__gte=effective_at).delete()

    if new_user is not None:
        # Merge with an adjacent own segment (release-then-reclaim,
        # back-to-back handovers) so continuous coverage stays one
        # segment and the week doesn't render as "split".
        adjacent = segments.filter(end_at=effective_at, user=new_user).first()
        if adjacent is not None:
            adjacent.end_at = week_end
            adjacent.save(update_fields=["end_at"])
        else:
            OnCallSegment.objects.create(
                year=year,
                week_number=week,
                user=new_user,
                start_at=effective_at,
                end_at=week_end,
            )
        defaults: dict = {"user": new_user}
        if notes is not None:
            defaults["notes"] = notes
        OnCallDuty.objects.update_or_create(year=year, week_number=week, defaults=defaults)
    elif duty is not None:
        # Freeing the week: the duty row goes, past coverage stays.
        duty.delete()

    change = OnCallChange.objects.create(
        year=year,
        week_number=week,
        from_user=old_user,
        to_user=new_user,
        effective_at=effective_at,
        changed_by=changed_by,
    )

    _notify(year, week, old_user, new_user, displaced, effective_at, week_start, changed_by)
    return change


def _is_noop(
    tail: list[OnCallSegment],
    duty: OnCallDuty | None,
    new_pk: int | None,
    effective_at: datetime,
    week_end: datetime,
) -> bool:
    """True when [effective_at, week_end) already matches the request.

    Checking only the holder *at* effective_at is not enough: on a
    split week "give Anna the whole week" must rewrite Bo's later
    segment even though Anna covers Monday.
    """
    if new_pk is None:
        return duty is None and not tail
    if duty is None or duty.user_id != new_pk:
        return False
    cursor = effective_at
    for segment in tail:
        if segment.user_id != new_pk or segment.start_at > cursor:
            return False
        cursor = max(cursor, segment.end_at)
    return cursor >= week_end


def _notify(
    year: int,
    week: int,
    old_user: User | None,
    new_user: User | None,
    displaced: set[User],
    effective_at: datetime,
    week_start: datetime,
    changed_by: User | None,
) -> None:
    """Bell notifications for the people affected by an assignment change.

    ``displaced`` holds every holder whose coverage in the rewritten
    tail was taken over — on a split week that includes later-segment
    holders, not just the person covering at effective_at.
    ``Notification.notify`` skips self-notifications, so claiming or
    releasing your own shift stays silent.
    """
    url = _calendar_url(year, week)
    suffix = "" if effective_at == week_start else f" fra {boundary_label(effective_at)}"

    if new_user is not None:
        Notification.notify(
            new_user,
            f"Du er sat på rådighedsvagt uge {week}, {year}{suffix}",
            url=url,
            actor=changed_by,
        )
    recipients = set(displaced)
    if old_user is not None and (new_user is None or old_user.pk != new_user.pk):
        recipients.add(old_user)
    for holder in recipients:
        if new_user is not None:
            message = f"{_display_name(new_user)} overtager din rådighedsvagt uge {week}, {year}{suffix}"
        else:
            message = f"Din rådighedsvagt uge {week}, {year} er frigivet{suffix}"
        Notification.notify(holder, message, url=url, actor=changed_by)


def claim_week(year: int, week: int, user: User) -> OnCallChange | None:
    """Self-service claim of a free week ("Tag vagt").

    No-op when the week already has a base assignee. Coverage starts
    where the week's existing coverage ends (a week freed mid-week is
    claimed from the release moment, never overlapping the previous
    holder's record) — or from Monday when the week is untouched.
    """
    if OnCallDuty.objects.filter(year=year, week_number=week).exists():
        return None

    week_start, _ = week_span(year, week)
    last_end = (
        OnCallSegment.objects.filter(year=year, week_number=week)
        .order_by("-end_at")
        .values_list("end_at", flat=True)
        .first()
    )
    effective_at = max(week_start, last_end) if last_end else week_start
    return apply_assignment(year, week, user, effective_at, changed_by=user)


def release_week(year: int, week: int, user: User) -> OnCallChange | None:
    """Release your own week ("Frigiv") — only the part you actually hold.

    On a split week the button belongs to the base assignee (holder of
    the last segment); releasing must free from the start of their own
    trailing coverage run, never truncating an earlier holder's active
    segment. Releasing mid-coverage keeps the already-covered part on
    record; only your own weeks can be released.
    """
    duty = OnCallDuty.objects.filter(year=year, week_number=week, user=user).first()
    if duty is None:
        return None

    week_start, week_end = week_span(year, week)
    now = timezone.localtime()
    if now >= week_end:
        return None

    # Start of the trailing run of segments owned by the releasing user.
    own_start = None
    for segment in OnCallSegment.for_week(year, week).order_by("-start_at"):
        if segment.user_id != user.pk:
            break
        own_start = segment.start_at
    effective_at = max(week_start, now if own_start is None else max(now, own_start))
    if effective_at >= week_end:
        return None
    return apply_assignment(year, week, None, effective_at, changed_by=user)
