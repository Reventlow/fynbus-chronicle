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

A ``CVECase`` ("sag") groups CVEs that share one assessment and one fix —
e.g. four kernel CVEs closed by the same kernel update. A CVE belongs to at
most one case; while it does, its state follows the case's. The case keeps
the shared documentation: assessment, solution, links, attachments and its
own timeline. Links, comments and attachments therefore belong to either a
CVE or a case (exactly one of the two foreign keys is set).
"""

import re
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
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
    case = models.ForeignKey(
        "CVECase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cves",
        verbose_name="Sag",
        help_text="Sagen, der samler vurdering og løsning for denne CVE. Status følger sagen.",
    )

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

    def owner_url(self, name: str, *args) -> str:
        """URL of a per-owner view (links, comments, attachments) for this CVE.

        The same views serve cases under ``case-<name>``; see CVECase.owner_url.
        """
        return reverse(f"cves:{name}", args=(self.pk, *args))

    is_case = False

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

    def set_state(self, new_state: str, user=None, *, note: str = "") -> bool:
        """Move to ``new_state`` and record it on the timeline.

        Moving to solved stamps ``solved_at``/``solved_by``; leaving solved
        clears them. ``note`` is appended to the timeline line (the case
        passes "via sag …"). Returns False (and records nothing) when the
        state does not change.
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
            text=f"Status: {self.State(old_state).label} → {self.State(new_state).label}{note}",
            author=user,
        )
        return True


class CaseConflict(Exception):
    """A CVE is already in another case (a CVE belongs to at most one)."""

    def __init__(self, cves: list["CVE"]):
        self.cves = cves
        super().__init__(", ".join(f"{c.cve_id} (sag #{c.case_id})" for c in cves))


class CVECaseQuerySet(models.QuerySet):
    open_during = CVEQuerySet.open_during

    def open(self) -> "CVECaseQuerySet":
        return self.exclude(state=CVE.State.SOLVED)

    def open_first(self) -> "CVECaseQuerySet":
        rank = Case(
            When(state=CVE.State.PATCHING, then=Value(0)),
            When(state=CVE.State.IDENTIFIED, then=Value(1)),
            default=Value(2),
            output_field=IntegerField(),
        )
        return self.annotate(state_rank=rank).order_by("state_rank", "-updated_at")


class CVECase(models.Model):
    """A case: CVEs that share one assessment, one fix and one set of documents.

    The case's state is the truth for its CVEs: changing it moves every
    member CVE too (each CVE's timeline notes that it came via the case),
    and a CVE added to a case takes the case's state. When solved, the
    ``resolution`` says how: patched, or not affected at all.
    """

    State = CVE.State

    class Resolution(models.TextChoices):
        PATCHED = "patched", "Patchet"
        NOT_AFFECTED = "not_affected", "Ikke berørt"

    title = models.CharField(verbose_name="Titel", max_length=200,
                             help_text="Fx \"eMudhra CA-kompromittering\" eller \"Linux-kerne, oktober 2026\".")
    assessment = models.TextField(verbose_name="Vurdering", blank=True,
                                  help_text="Er vi berørt, og hvorfor (ikke)? Markdown virker.")
    solution = models.TextField(verbose_name="Løsning / handling", blank=True,
                                help_text="Hvad er gjort eller skal gøres. Markdown virker.")
    state = models.CharField(verbose_name="Status", max_length=12, choices=CVE.State.choices,
                             default=CVE.State.IDENTIFIED)
    resolution = models.CharField(verbose_name="Udfald", max_length=16, choices=Resolution.choices, blank=True)
    source = models.CharField(verbose_name="Kilde", max_length=40, blank=True,
                              help_text="Hvor advarslen kom fra, fx CFCS, Harbinger eller en leverandør.")
    reference = models.CharField(verbose_name="Reference", max_length=100, blank=True,
                                 help_text="Kildens eget id, fx CFCS-advarslens nummer og dato. "
                                           "Til advarsler uden CVE-nummer.")
    source_url = models.URLField(verbose_name="Kildelink", blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="cve_cases_created", verbose_name="Oprettet af")
    created_at = models.DateTimeField(verbose_name="Oprettet", default=timezone.now)
    updated_at = models.DateTimeField(verbose_name="Opdateret", auto_now=True)
    solved_at = models.DateTimeField(verbose_name="Løst", null=True, blank=True)
    solved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="cve_cases_solved", verbose_name="Løst af")

    objects = CVECaseQuerySet.as_manager()

    class Meta:
        verbose_name = "CVE-sag"
        verbose_name_plural = "CVE-sager"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"Sag #{self.pk}: {self.title}"

    is_case = True

    def get_absolute_url(self) -> str:
        return reverse("cves:case-detail", kwargs={"pk": self.pk})

    def owner_url(self, name: str, *args) -> str:
        return reverse(f"cves:case-{name}", args=(self.pk, *args))

    @property
    def is_open(self) -> bool:
        return self.state != self.State.SOLVED

    state_color = CVE.state_color
    solved_within = CVE.solved_within

    @property
    def source_label(self) -> str:
        """``source`` for display: the stored machine values read as names."""
        return {"harbinger": "Harbinger", "api": "API"}.get(self.source, self.source)

    @property
    def outcome_label(self) -> str:
        """"Løst — patchet", "Løst — ikke berørt", or the plain state label."""
        if self.state == self.State.SOLVED and self.resolution:
            return f"{self.get_state_display()} — {self.get_resolution_display().lower()}"
        return self.get_state_display()

    def touch(self) -> None:
        self.updated_at = timezone.now()
        CVECase.objects.filter(pk=self.pk).update(updated_at=self.updated_at)

    def _log(self, text: str, user=None, *, state: bool = True) -> None:
        CVEComment.objects.create(case=self, kind=CVEComment.Kind.STATE if state else CVEComment.Kind.COMMENT,
                                  text=text, author=user)

    def set_state(self, new_state: str, user=None, *, resolution: str = "") -> bool:
        """Move the case (and every CVE in it) to ``new_state``.

        ``resolution`` only applies when solving; leaving solved clears it.
        Returns False when neither the state nor the resolution changed.
        """
        if new_state not in self.State.values:
            raise ValueError(f"Unknown CVE state: {new_state!r}")
        if resolution and resolution not in self.Resolution.values:
            raise ValueError(f"Unknown resolution: {resolution!r}")
        if new_state != self.State.SOLVED:
            resolution = ""
        old_label = self.outcome_label
        if new_state == self.state and resolution == self.resolution:
            return False
        if new_state != self.state:
            if new_state == self.State.SOLVED:
                self.solved_at, self.solved_by = timezone.now(), user
            else:
                self.solved_at, self.solved_by = None, None
        self.state, self.resolution = new_state, resolution
        self.save(update_fields=["state", "resolution", "solved_at", "solved_by", "updated_at"])
        self._log(f"Status: {old_label} → {self.outcome_label}", user)
        for cve in self.cves.all():
            cve.set_state(new_state, user, note=f" (via sag #{self.pk})")
        return True

    def add_cves(self, cves, user=None) -> list["CVE"]:
        """Add CVEs to the case; they take the case's state.

        Raises CaseConflict (adding nothing) if any is in another case.
        Returns the CVEs that were actually added (not already members).
        """
        cves = list(cves)
        taken = [c for c in cves if c.case_id and c.case_id != self.pk]
        if taken:
            raise CaseConflict(taken)
        added = [c for c in cves if c.case_id != self.pk]
        for cve in added:
            cve.case = self
            cve.save(update_fields=["case", "updated_at"])
            CVEComment.objects.create(cve=cve, kind=CVEComment.Kind.STATE, author=user,
                                      text=f"Føjet til sag #{self.pk}: {self.title}")
            cve.set_state(self.state, user, note=f" (via sag #{self.pk})")
        if added:
            self._log("Tilføjet: " + ", ".join(c.cve_id for c in added), user)
        return added

    def remove_cve(self, cve: "CVE", user=None) -> bool:
        """Take a CVE out of the case. Its state stays as it is."""
        if cve.case_id != self.pk:
            return False
        cve.case = None
        cve.save(update_fields=["case", "updated_at"])
        CVEComment.objects.create(cve=cve, kind=CVEComment.Kind.STATE, author=user,
                                  text=f"Fjernet fra sag #{self.pk}: {self.title}")
        self._log(f"Fjernet: {cve.cve_id}", user)
        return True


class _OwnedMixin:
    """Shared by links, comments and attachments, which belong to a CVE or a case."""

    @property
    def owner(self):
        return self.cve if self.cve_id else self.case


def _exactly_one_owner(name: str) -> models.CheckConstraint:
    return models.CheckConstraint(
        condition=(Q(cve__isnull=False, case__isnull=True) | Q(cve__isnull=True, case__isnull=False)),
        name=name,
    )


class CVELink(_OwnedMixin, models.Model):
    """A reference for a CVE — advisory, vendor note, ticket, …"""

    cve = models.ForeignKey(CVE, on_delete=models.CASCADE, null=True, blank=True, related_name="links", verbose_name="CVE")
    case = models.ForeignKey(CVECase, on_delete=models.CASCADE, null=True, blank=True, related_name="links", verbose_name="Sag")
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
        constraints = [_exactly_one_owner("cvelink_one_owner")]

    def __str__(self) -> str:
        return self.label or self.url

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.owner.touch()


class CVEComment(_OwnedMixin, models.Model):
    """One entry on a CVE's timeline: a comment or a state change."""

    class Kind(models.TextChoices):
        COMMENT = "comment", "Kommentar"
        STATE = "state", "Statusændring"

    cve = models.ForeignKey(CVE, on_delete=models.CASCADE, null=True, blank=True, related_name="comments", verbose_name="CVE")
    case = models.ForeignKey(CVECase, on_delete=models.CASCADE, null=True, blank=True, related_name="comments", verbose_name="Sag")
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
        constraints = [_exactly_one_owner("cvecomment_one_owner")]

    def __str__(self) -> str:
        label = self.cve.cve_id if self.cve_id else f"Sag #{self.case_id}"
        return f"{label}: {self.text[:40]}"

    @property
    def is_state_change(self) -> bool:
        return self.kind == self.Kind.STATE

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.owner.touch()


def weeklog_cves(weeklog) -> dict:
    """Template context for a week log's CVE section.

    Every CVE that was unsolved at some point during the log's ISO week,
    open ones first, and likewise every case (``week_cases``) — a case can
    hold no CVEs at all, e.g. a CFCS warning without a CVE number. Each
    carries ``solved_this_week`` for the "Løst denne uge" mark. Shared by
    the week log page and the HTML/PDF export.
    """
    start, end = iso_week_bounds(weeklog.year, weeklog.week_number)
    cves = list(CVE.objects.open_during(start, end).select_related("case").open_first())
    for cve in cves:
        cve.solved_this_week = cve.solved_within(start, end)
    cases = list(CVECase.objects.open_during(start, end).prefetch_related("cves").open_first())
    for case in cases:
        case.solved_this_week = case.solved_within(start, end)
    return {"week_cves": cves, "week_cases": cases, "week_vuln_count": len(cves) + len(cases)}


class CVEFileStorage(FileSystemStorage):
    """Storage rooted at CVE_FILES_DIR, resolved at run time so tests and
    Docker can point it elsewhere (same pattern as apps.images)."""

    @property
    def base_location(self):  # type: ignore[override]
        return str(settings.CVE_FILES_DIR)

    @property
    def location(self):  # type: ignore[override]
        return str(settings.CVE_FILES_DIR)


def _attachment_path(instance: "CVEAttachment", filename: str) -> str:
    # Random key, not the uploaded name: the original name is kept in
    # ``original_name`` for display/download only.
    return f"{instance.uploaded_at:%Y/%m}/{instance.key}.{instance.kind or 'pdf'}"


def _new_key() -> str:
    return secrets.token_hex(16)


class CVEAttachment(_OwnedMixin, models.Model):
    """A PDF, ODT document or Outlook mail (.msg) attached to a CVE, with its TLP marking.

    PDFs are served inline for the lightbox. A .msg can't be shown by a
    browser, so its headers and plain-text body are extracted at upload
    (``email_*``) and shown as a preview; the original is offered as a
    download. PDFs found inside a mail are stored as their own attachments
    with ``parent`` pointing at it. An .odt has no preview: clicking it
    downloads it. Content is checked, not just the name: ``%PDF-`` for
    PDFs, an OLE compound file with MAPI properties for .msg, and a zip
    whose ``mimetype`` member names an OpenDocument text for .odt.
    Never served from static/media.
    """

    class Kind(models.TextChoices):
        PDF = "pdf", "PDF"
        MSG = "msg", "Outlook-mail"
        ODT = "odt", "ODT-dokument"

    class TLP(models.TextChoices):
        # FIRST TLP 2.0. Empty = not marked.
        CLEAR = "clear", "TLP:CLEAR"
        GREEN = "green", "TLP:GREEN"
        AMBER = "amber", "TLP:AMBER"
        AMBER_STRICT = "amber_strict", "TLP:AMBER+STRICT"
        RED = "red", "TLP:RED"

    cve = models.ForeignKey(CVE, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments", verbose_name="CVE")
    case = models.ForeignKey(CVECase, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments", verbose_name="Sag")
    key = models.CharField(max_length=32, unique=True, default=_new_key, editable=False)
    file = models.FileField(storage=CVEFileStorage(), upload_to=_attachment_path, max_length=200)
    original_name = models.CharField(verbose_name="Filnavn", max_length=255)
    title = models.CharField(
        verbose_name="Titel", max_length=200, blank=True,
        help_text="Fx \"FE-CSIRT advisory 2026-0142\". Tom = filnavnet.",
    )
    source = models.CharField(
        verbose_name="Kilde", max_length=100, blank=True, help_text="Fx FE-CSIRT (CSIRT@fe-ddis.dk).",
    )
    tlp = models.CharField(verbose_name="TLP", max_length=20, choices=TLP.choices, blank=True)
    size = models.PositiveIntegerField(verbose_name="Størrelse (bytes)", default=0)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", verbose_name="Uploadet af",
    )
    uploaded_at = models.DateTimeField(verbose_name="Uploadet", default=timezone.now)
    kind = models.CharField(verbose_name="Type", max_length=3, choices=Kind.choices, default=Kind.PDF)
    # For .msg: what the mail said, extracted once at upload (shown escaped).
    email_subject = models.CharField(verbose_name="Mail: emne", max_length=500, blank=True)
    email_from = models.CharField(verbose_name="Mail: fra", max_length=300, blank=True)
    email_to = models.TextField(verbose_name="Mail: til", blank=True)
    email_sent = models.DateTimeField(verbose_name="Mail: sendt", null=True, blank=True)
    email_body = models.TextField(verbose_name="Mail: tekst", blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="extracted",
        verbose_name="Fra mail", help_text="Sat på PDF'er, der blev pakket ud af en vedhæftet mail.",
    )

    class Meta:
        ordering = ["uploaded_at", "pk"]
        verbose_name = "Vedhæftet PDF"
        verbose_name_plural = "Vedhæftede PDF'er"
        constraints = [_exactly_one_owner("cveattachment_one_owner")]

    def __str__(self) -> str:
        return self.display_title

    @property
    def display_title(self) -> str:
        return self.title or (self.email_subject if self.kind == self.Kind.MSG else "") or self.original_name

    @property
    def is_msg(self) -> bool:
        return self.kind == self.Kind.MSG

    @property
    def is_odt(self) -> bool:
        return self.kind == self.Kind.ODT

    def get_download_url(self) -> str:
        return self.get_absolute_url() + "?download=1"

    def get_view_url(self) -> str:
        """What the lightbox shows: the PDF itself, or the mail preview page."""
        if self.is_msg:
            return self.owner.owner_url("attachment-preview", self.key)
        return self.get_absolute_url()

    @property
    def tlp_badge_class(self) -> str:
        """CSS modifier for the TLP badge (colours follow FIRST TLP 2.0)."""
        return f"tlp-{self.tlp}" if self.tlp else ""

    def get_absolute_url(self) -> str:
        return self.owner.owner_url("attachment", self.key)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.owner.touch()

    def delete(self, *args, **kwargs):
        storage, name = self.file.storage, self.file.name
        result = super().delete(*args, **kwargs)
        if name:
            storage.delete(name)  # don't leave an orphaned (possibly TLP:AMBER) file on disk
        self.owner.touch()
        return result
