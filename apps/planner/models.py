"""Models for the Planner board.

Four groups:

* **The connections** (:class:`PlannerConnection`,
  :class:`PlannerUserConnection`, :class:`PendingSignIn`): the service
  account (reads the plan) and each editor's own account (makes that
  editor's changes, so Planner and Purview record the right person). The
  web container receives Microsoft's one-time code and stores it *sealed*
  (PendingSignIn); the sync container, which alone has the private key and
  the client secret, redeems it and keeps the resulting token cache sealed.
  The web container can write these but read none of them.
* **Changes** (:class:`PlannerChange`, :class:`PlannerLink`): what an
  editor did on the board, queued for the sync container, and the links
  between Planner cards and Chronicle's priorities and cases.
* **The mirror** (:class:`PlannerPlan`, :class:`PlannerBucket`,
  :class:`PlannerTask`, :class:`PlannerPerson`): a read-only copy of the
  plan that the board renders, refreshed by the sync job.
* **Sync bookkeeping** (:class:`SyncState`): when the last run was, what
  went wrong, and the "Synk nu" request queue.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Longest description kept from Planner (text from outside Chronicle).
DESCRIPTION_MAX = 4000


class PlannerConnection(models.Model):
    """The connected service account and its sealed token cache (singleton)."""

    account_upn = models.CharField("Konto", max_length=255, blank=True)
    account_oid = models.CharField("Entra-objekt-id", max_length=64, blank=True)
    home_account_id = models.CharField(max_length=255, blank=True)
    sealed_token_cache = models.TextField(blank=True, help_text="Sealed for the sync container; unreadable here.")
    connected_at = models.DateTimeField(null=True, blank=True)
    connected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    last_token_ok_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = "Planner-forbindelse"
        verbose_name_plural = "Planner-forbindelse"

    def __str__(self) -> str:
        return self.account_upn or "Ikke forbundet"

    @classmethod
    def get(cls) -> PlannerConnection:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_connected(self) -> bool:
        return bool(self.sealed_token_cache and self.home_account_id)


class PlannerUserConnection(models.Model):
    """One editor's own Microsoft sign-in, used for that editor's changes.

    Same fields as :class:`PlannerConnection`; there is one per user. The
    sync container never falls back to the service account for a change.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="planner_connection")
    account_upn = models.CharField("Konto", max_length=255, blank=True)
    account_oid = models.CharField("Entra-objekt-id", max_length=64, blank=True)
    home_account_id = models.CharField(max_length=255, blank=True)
    sealed_token_cache = models.TextField(blank=True, help_text="Sealed for the sync container; unreadable here.")
    connected_at = models.DateTimeField(null=True, blank=True)
    last_token_ok_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = "Personlig Planner-forbindelse"
        verbose_name_plural = "Personlige Planner-forbindelser"

    def __str__(self) -> str:
        return f"{self.user} → {self.account_upn or 'ikke forbundet'}"

    @property
    def is_connected(self) -> bool:
        return bool(self.sealed_token_cache and self.home_account_id)


class PendingSignIn(models.Model):
    """A sign-in handed from the web container to the sync container.

    ``sealed`` holds Microsoft's code, the PKCE verifier and the redirect
    URI, sealed with the public key; the sync container clears it once
    redeemed. A code is valid for about ten minutes, so older ones fail.
    ``for_user`` set means an editor's own account; empty means the
    service account.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Venter"
        DONE = "done", "Forbundet"
        FAILED = "failed", "Fejlede"

    EXPIRES_AFTER = timedelta(minutes=9)

    sealed = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    handled_at = models.DateTimeField(null=True, blank=True)
    for_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.CASCADE, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Planner-login under behandling"
        verbose_name_plural = "Planner-logins under behandling"

    @property
    def is_expired(self) -> bool:
        return timezone.now() - self.created_at > self.EXPIRES_AFTER


class PlannerPlan(models.Model):
    """The mirrored plan: its title and label names."""

    id = models.CharField(primary_key=True, max_length=64)
    title = models.CharField(max_length=255, blank=True)
    # {"category1": "Ubehandlet", ...}; unnamed labels are left out.
    labels = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.title or self.id


class PlannerBucket(models.Model):
    """A column on the board."""

    id = models.CharField(primary_key=True, max_length=64)
    plan = models.ForeignKey(PlannerPlan, on_delete=models.CASCADE, related_name="buckets")
    name = models.CharField(max_length=255)
    order_hint = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["order_hint"]

    def __str__(self) -> str:
        return self.name


class PlannerPerson(models.Model):
    """Display names for assignees, looked up once per Entra object id."""

    id = models.CharField(primary_key=True, max_length=64)
    display_name = models.CharField(max_length=255)
    looked_up_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return self.display_name

    @property
    def initials(self) -> str:
        parts = [p for p in self.display_name.split() if p[:1].isalpha()]
        return ("".join(p[0] for p in parts[:2]) or "?").upper()


class PlannerTask(models.Model):
    """A card on the board, as Planner last reported it."""

    id = models.CharField(primary_key=True, max_length=64)
    plan = models.ForeignKey(PlannerPlan, on_delete=models.CASCADE, related_name="tasks")
    bucket = models.ForeignKey(PlannerBucket, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="tasks")
    title = models.CharField(max_length=500)
    percent_complete = models.PositiveSmallIntegerField(default=0)
    priority = models.PositiveSmallIntegerField(default=5)
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    order_hint = models.CharField(max_length=255, blank=True)
    assignee_ids = models.JSONField(default=list, blank=True)
    label_keys = models.JSONField(default=list, blank=True)  # ["category1", ...]
    checklist_total = models.PositiveSmallIntegerField(default=0)
    checklist_open = models.PositiveSmallIntegerField(default=0)
    reference_count = models.PositiveSmallIntegerField(default=0)
    has_description = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    etag = models.CharField(max_length=255, blank=True)
    details_etag = models.CharField(max_length=255, blank=True)
    details_synced_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["order_hint"]

    def __str__(self) -> str:
        return self.title

    # Planner's priority is 0-10; its UI shows four levels.
    @property
    def priority_label(self) -> str:
        if self.priority <= 1:
            return "Haster"
        if self.priority <= 4:
            return "Vigtig"
        if self.priority <= 7:
            return "Middel"
        return "Lav"

    @property
    def is_complete(self) -> bool:
        return self.percent_complete >= 100

    @property
    def is_in_progress(self) -> bool:
        return 0 < self.percent_complete < 100

    @property
    def is_overdue(self) -> bool:
        return bool(self.due_date and not self.is_complete and self.due_date < timezone.localdate())

    @property
    def checklist_done(self) -> int:
        return self.checklist_total - self.checklist_open


class SyncState(models.Model):
    """When the Planner sync last ran, and whether someone asked for a run (singleton)."""

    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    last_full_details_at = models.DateTimeField(null=True, blank=True)
    next_due_at = models.DateTimeField(null=True, blank=True)
    running_since = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    last_counts = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Planner-synkronisering"
        verbose_name_plural = "Planner-synkronisering"

    @classmethod
    def get(cls) -> SyncState:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_requested(self) -> bool:
        """A "Synk nu" that the sync container has not started yet."""
        return bool(self.requested_at and (not self.last_attempt_at or self.requested_at > self.last_attempt_at))


class PlannerChange(models.Model):
    """A change an editor made on the board, waiting for the sync container.

    The web container records it (and shows it on the board straight
    away); the sync container makes it in Planner with that editor's own
    connection, then updates the mirror from Planner's answer.

    ``payload`` per kind:

    * complete / reopen: ``{}``
    * move: ``{"bucket_id", "order_hint"}`` (Planner's ``"<prev> <next>!"``)
    * create: ``{"bucket_id", "title"}``; ``task_id`` is filled in when done
    * link: ``{"url", "alias", "label"}``: a reference back to Chronicle
      and a label on the card
    * progress: ``{"percent"}``: a linked priority or case changed status
      in Chronicle (two-way sync, :mod:`apps.planner.linksync`)
    * create may also carry ``{"link": {"priority_item"|"case": id}, "url",
      "alias", "label", "description", "percent", "due"}``: "Opret i
      Planner" from a Chronicle priority or case
    """

    class Kind(models.TextChoices):
        COMPLETE = "complete", "Fuldfør"
        REOPEN = "reopen", "Genåbn"
        MOVE = "move", "Flyt"
        CREATE = "create", "Opret"
        LINK = "link", "Link til Chronicle"
        PROGRESS = "progress", "Status fra Chronicle"

    class Status(models.TextChoices):
        PENDING = "pending", "Venter"
        DONE = "done", "Gennemført"
        FAILED = "failed", "Fejlede"

    # After this long without the sync container, the board stops waiting.
    WAIT_AT_MOST = timedelta(minutes=3)

    kind = models.CharField(max_length=10, choices=Kind.choices)
    task_id = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Planner-ændring"
        verbose_name_plural = "Planner-ændringer"

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.task_id or self.payload.get('title', '')}"

    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING

    @property
    def still_waiting(self) -> bool:
        """Pending and recent enough that the board keeps polling."""
        return self.is_pending and timezone.now() - self.created_at < self.WAIT_AT_MOST


class PlannerLink(models.Model):
    """A Planner card linked to a Chronicle priority or case.

    ``task_id`` is a plain id, not a foreign key: the link outlives the
    mirror row if the card is deleted in Planner. ``task_title`` keeps the
    name for that case.
    """

    task_id = models.CharField(max_length=64, db_index=True)
    task_title = models.CharField(max_length=500, blank=True)
    priority_item = models.ForeignKey("logbook.PriorityItem", null=True, blank=True,
                                      on_delete=models.CASCADE, related_name="planner_links")
    case = models.ForeignKey("cves.CVECase", null=True, blank=True,
                             on_delete=models.CASCADE, related_name="planner_links")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    # Two-way status sync: the state each side had when last in step
    # ("not_started" / "in_progress" / "done"; empty until first seen).
    planner_state = models.CharField(max_length=12, blank=True)
    chronicle_state = models.CharField(max_length=12, blank=True)
    # Why the last Chronicle change didn't reach Planner, if it didn't.
    sync_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Planner-link"
        verbose_name_plural = "Planner-links"
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(priority_item__isnull=False, case__isnull=True)
                           | models.Q(priority_item__isnull=True, case__isnull=False)),
                name="planner_link_one_target"),
            models.UniqueConstraint(fields=["task_id", "priority_item"], name="planner_link_unique_priority"),
            models.UniqueConstraint(fields=["task_id", "case"], name="planner_link_unique_case"),
        ]

    def __str__(self) -> str:
        return f"{self.task_title or self.task_id} → {self.target_label}"

    @property
    def target(self):
        return self.priority_item or self.case

    @property
    def target_label(self) -> str:
        if self.priority_item_id:
            return f"Prioriteret opgave #{self.priority_item_id}"
        return f"Sag #{self.case_id}"

    @property
    def target_url(self) -> str:
        from django.urls import reverse
        if self.priority_item_id:
            return reverse("logbook:priority-item-history", args=[self.priority_item_id])
        return reverse("cves:case-detail", kwargs={"pk": self.case_id})

    @property
    def task_url(self) -> str:
        """The card in Planner's web app."""
        return task_url(self.task_id)


def task_url(task_id: str) -> str:
    """Planner's link to one task (the form "Copy link to task" gives)."""
    return f"https://tasks.office.com/{settings.PLANNER_TENANT_ID}/Home/Task/{task_id}"
