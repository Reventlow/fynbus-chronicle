"""Models for the CVE ("Sårbarheder") section.

A ``CVE`` is one published vulnerability the department is tracking. It
moves through three states — identified, patching, solved — and collects
links (advisories, vendor notes, tickets) and a timeline of comments. State
changes are written to that same timeline, so the history reads top to
bottom without a separate audit table.

CVEs are created by hand or by Harbinger through the API
(``POST /api/v1/cves/``); ``source`` and ``source_url`` record the latter.

Nothing is carried from week to week: the week log shows every CVE that was
unsolved at some point during the week (``CVE.objects.open_during``).
"""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, IntegerField, Q, Value, When
from django.urls import reverse
from django.utils import timezone

CVE_ID_RE = re.compile(r"^CVE-\d{4}-\d{4,}$")

CVEFEED_URL = "https://cvefeed.io/vuln/detail/{cve_id}"


def normalise_cve_id(value: str) -> str:
    """Return ``value`` stripped and upper-cased, or raise ValidationError
    when it is not of the form ``CVE-YYYY-NNNN…`` (four or more digits)."""
    cve_id = (value or "").strip().upper()
    if not CVE_ID_RE.match(cve_id):
        raise ValidationError(
            "Ugyldigt CVE-id. Forventet formatet CVE-ÅÅÅÅ-NNNN, fx CVE-2026-109618.",
            code="invalid_cve_id",
        )
    return cve_id


def validate_cve_id(value: str) -> None:
    """Field validator wrapper around :func:`normalise_cve_id`."""
    normalise_cve_id(value)


def iso_week_bounds(year: int, week: int) -> tuple[datetime, datetime]:
    """Aware (local time) start of the ISO week and start of the next one.

    The pair is half-open: ``start <= t < end`` is "inside the week".
    """
    monday = date.fromisocalendar(year, week, 1)
    start = timezone.make_aware(datetime.combine(monday, datetime.min.time()))
    end = timezone.make_aware(datetime.combine(monday + timedelta(days=7), datetime.min.time()))
    return start, end


class CVEQuerySet(models.QuerySet):
    """Window queries used by the Kontrolpanel card and the week log."""

    def active_in_last(self, days: int = 30) -> "CVEQuerySet":
        """CVEs created or updated within the last ``days`` days.

        Comments and links touch the CVE, so activity on them counts too.
        """
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(Q(updated_at__gte=cutoff) | Q(created_at__gte=cutoff))

    def open_during(self, week_start: datetime, week_end: datetime) -> "CVEQuerySet":
        """CVEs that were unsolved at some point in ``[week_start, week_end)``:
        created before the week ended and not solved before it began."""
        return self.filter(created_at__lt=week_end).filter(
            Q(solved_at__isnull=True) | Q(solved_at__gte=week_start)
        )

    def open_first(self) -> "CVEQuerySet":
        """Open CVEs first (patching, then identified), then solved; newest
        activity first within each state."""
        rank = Case(
            When(state=CVE.State.PATCHING, then=Value(0)),
            When(state=CVE.State.IDENTIFIED, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
        return self.annotate(state_rank=rank).order_by("state_rank", "-updated_at")

    def open(self) -> "CVEQuerySet":
        """Identified or being patched."""
        return self.exclude(state=CVE.State.SOLVED)


class CVE(models.Model):
    """A tracked vulnerability."""

    class State(models.TextChoices):
        IDENTIFIED = "identified", "Identificeret"
        PATCHING = "patching", "Patcher"
        SOLVED = "solved", "Løst"

    class Severity(models.TextChoices):
        CRITICAL = "critical", "Kritisk"
        HIGH = "high", "Høj"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Lav"
        NONE = "none", "Ingen/ukendt"

    cve_id = models.CharField(
        verbose_name="CVE-id",
        max_length=32,
        unique=True,
        validators=[validate_cve_id],
        help_text="Fx CVE-2026-109618.",
    )
    subject = models.CharField(verbose_name="Emne", max_length=300)
    cvss = models.DecimalField(
        verbose_name="CVSS",
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
    )
    severity = models.CharField(
        verbose_name="Alvorlighed",
        max_length=10,
        choices=Severity.choices,
        blank=True,
        help_text="Udledes af CVSS, hvis den ikke angives.",
    )
    cvefeed_url = models.URLField(
        verbose_name="cvefeed.io-link",
        blank=True,
        help_text="Udfyldes automatisk, hvis feltet er tomt.",
    )
    state = models.CharField(
        verbose_name="Status",
        max_length=12,
        choices=State.choices,
        default=State.IDENTIFIED,
    )
    source = models.CharField(
        verbose_name="Kilde",
        max_length=40,
        blank=True,
        help_text='"harbinger" eller "api" når CVE\'en er oprettet via API\'et; tom ved manuel oprettelse.',
    )
    source_url = models.URLField(verbose_name="Kildelink", blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cves_created",
        verbose_name="Oprettet af",
    )
    created_at = models.DateTimeField(verbose_name="Oprettet", default=timezone.now)
    updated_at = models.DateTimeField(verbose_name="Opdateret", auto_now=True)
    solved_at = models.DateTimeField(verbose_name="Løst", null=True, blank=True)
    solved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cves_solved",
        verbose_name="Løst af",
    )

    objects = CVEQuerySet.as_manager()

    class Meta:
        verbose_name = "CVE"
        verbose_name_plural = "CVE'er"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["state", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.cve_id} — {self.subject}"

    def get_absolute_url(self) -> str:
        return reverse("cves:detail", kwargs={"pk": self.pk})

    # -- derived values ------------------------------------------------------

    @classmethod
    def severity_for(cls, cvss) -> str:
        """Severity band for a CVSS score (CVSS v3 qualitative ratings)."""
        if cvss is None:
            return cls.Severity.NONE
        score = Decimal(str(cvss))
        if score >= 9:
            return cls.Severity.CRITICAL
        if score >= 7:
            return cls.Severity.HIGH
        if score >= 4:
            return cls.Severity.MEDIUM
        if score > 0:
            return cls.Severity.LOW
        return cls.Severity.NONE

    @staticmethod
    def default_cvefeed_url(cve_id: str) -> str:
        return CVEFEED_URL.format(cve_id=cve_id)

    @property
    def is_open(self) -> bool:
        return self.state != self.State.SOLVED

    @property
    def severity_pill(self) -> str:
        """The ``.pill-*`` modifier for the CVSS pill."""
        return {
            self.Severity.CRITICAL: "bad",
            self.Severity.HIGH: "warn",
            self.Severity.MEDIUM: "info",
            self.Severity.LOW: "neutral",
        }.get(self.severity, "neutral")

    @property
    def state_color(self) -> str:
        """CSS colour variable for the state dot."""
        return {
            self.State.IDENTIFIED: "var(--bad)",
            self.State.PATCHING: "var(--warn)",
            self.State.SOLVED: "var(--good)",
        }.get(self.state, "var(--ink-4)")

    def solved_within(self, start: datetime, end: datetime) -> bool:
        """True when the CVE was solved inside ``[start, end)``."""
        return self.solved_at is not None and start <= self.solved_at < end

    # -- persistence ---------------------------------------------------------

    def save(self, *args, **kwargs):
        """Normalise the id and fill severity and the cvefeed.io link."""
        self.cve_id = (self.cve_id or "").strip().upper()
        if not self.severity:
            self.severity = self.severity_for(self.cvss)
        if not self.cvefeed_url and self.cve_id:
            self.cvefeed_url = self.default_cvefeed_url(self.cve_id)
        super().save(*args, **kwargs)

    def touch(self) -> None:
        """Bump ``updated_at`` (a comment or link was added)."""
        self.updated_at = timezone.now()
        CVE.objects.filter(pk=self.pk).update(updated_at=self.updated_at)

    def set_state(self, new_state: str, user=None) -> bool:
        """Move to ``new_state`` and record it on the timeline.

        Moving to solved stamps ``solved_at``/``solved_by``; leaving solved
        clears them. Returns False (and records nothing) when the state does
        not change.
        """
        if new_state not in self.State.values:
            raise ValueError(f"Unknown CVE state: {new_state!r}")
        old_state = self.state
        if new_state == old_state:
            return False
        self.state = new_state
        if new_state == self.State.SOLVED:
            self.solved_at = timezone.now()
            self.solved_by = user
        else:
            self.solved_at = None
            self.solved_by = None
        self.save(update_fields=["state", "solved_at", "solved_by", "updated_at"])
        CVEComment.objects.create(
            cve=self,
            kind=CVEComment.Kind.STATE,
            text=f"Status: {self.State(old_state).label} → {self.State(new_state).label}",
            author=user,
        )
        return True


class CVELink(models.Model):
    """A reference for a CVE — advisory, vendor note, ticket, …"""

    cve = models.ForeignKey(CVE, on_delete=models.CASCADE, related_name="links", verbose_name="CVE")
    url = models.URLField(verbose_name="Link", max_length=500)
    label = models.CharField(verbose_name="Beskrivelse", max_length=200, blank=True)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cve_links",
        verbose_name="Tilføjet af",
    )
    added_at = models.DateTimeField(verbose_name="Tilføjet", auto_now_add=True)

    class Meta:
        verbose_name = "CVE-link"
        verbose_name_plural = "CVE-links"
        ordering = ["added_at"]

    def __str__(self) -> str:
        return self.label or self.url

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.cve.touch()


class CVEComment(models.Model):
    """One entry on a CVE's timeline: a comment or a state change."""

    class Kind(models.TextChoices):
        COMMENT = "comment", "Kommentar"
        STATE = "state", "Statusændring"

    cve = models.ForeignKey(CVE, on_delete=models.CASCADE, related_name="comments", verbose_name="CVE")
    text = models.TextField(verbose_name="Tekst", help_text="Markdown.")
    kind = models.CharField(
        verbose_name="Type",
        max_length=10,
        choices=Kind.choices,
        default=Kind.COMMENT,
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cve_comments",
        verbose_name="Forfatter",
    )
    created_at = models.DateTimeField(verbose_name="Oprettet", auto_now_add=True)

    class Meta:
        verbose_name = "CVE-kommentar"
        verbose_name_plural = "CVE-kommentarer"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.cve.cve_id}: {self.text[:40]}"

    @property
    def is_state_change(self) -> bool:
        return self.kind == self.Kind.STATE

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.cve.touch()


def weeklog_cves(weeklog) -> dict:
    """Template context for a week log's CVE section.

    Every CVE that was unsolved at some point during the log's ISO week,
    open ones first. Each carries ``solved_this_week`` for the "Løst denne
    uge" mark. Shared by the week log page and the HTML/PDF export.
    """
    start, end = iso_week_bounds(weeklog.year, weeklog.week_number)
    cves = list(CVE.objects.open_during(start, end).open_first())
    for cve in cves:
        cve.solved_this_week = cve.solved_within(start, end)
    return {"week_cves": cves}
