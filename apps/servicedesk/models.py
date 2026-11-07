"""A ServiceDesk ticket linked to a Chronicle priority or case."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


def ticket_url(sdp_id: int) -> str:
    """The request in ServiceDesk Plus, or "" without SERVICEDESK_URL."""
    base = (getattr(settings, "SERVICEDESK_URL", "") or "").rstrip("/")
    return f"{base}/WorkOrder.do?woMode=viewWO&woID={sdp_id}" if base else ""


class TicketLink(models.Model):
    """One ticket linked to one prioriteret opgave or one sag.

    ``sdp_id`` is a plain id, not a foreign key to the mirror: mirror rows
    are pruned when a ticket ages out of the statistics window, the link
    stays. ``subject`` keeps the ticket's subject for that case.

    Linking (and unlinking) adds an internal note to the ticket in
    ServiceDesk with a link back here. ``note_added_at`` is set once that
    note is in; ``note_error`` says why it isn't, until a retry succeeds.
    """

    sdp_id = models.PositiveIntegerField(verbose_name="ServiceDesk-id", db_index=True)
    subject = models.CharField(verbose_name="Emne", max_length=255, blank=True)
    priority_item = models.ForeignKey("logbook.PriorityItem", null=True, blank=True,
                                      on_delete=models.CASCADE, related_name="ticket_links")
    case = models.ForeignKey("cves.CVECase", null=True, blank=True,
                             on_delete=models.CASCADE, related_name="ticket_links")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    note_added_at = models.DateTimeField(verbose_name="Note tilføjet", null=True, blank=True)
    note_error = models.CharField(verbose_name="Notefejl", max_length=300, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "ServiceDesk-link"
        verbose_name_plural = "ServiceDesk-links"
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(priority_item__isnull=False, case__isnull=True)
                           | models.Q(priority_item__isnull=True, case__isnull=False)),
                name="ticket_link_one_target"),
            models.UniqueConstraint(fields=["sdp_id", "priority_item"], name="ticket_link_unique_priority"),
            models.UniqueConstraint(fields=["sdp_id", "case"], name="ticket_link_unique_case"),
        ]

    def __str__(self) -> str:
        return f"#{self.sdp_id} → {self.target_label}"

    @property
    def target(self):
        return self.priority_item or self.case

    @property
    def target_label(self) -> str:
        if self.priority_item_id:
            return f"Prioriteret opgave #{self.priority_item_id}"
        return f"Sag #{self.case_id}"

    @property
    def target_title(self) -> str:
        target = self.target
        return target.title if target is not None else ""

    @property
    def target_url(self) -> str:
        if self.priority_item_id:
            return reverse("logbook:priority-item-history", args=[self.priority_item_id])
        return reverse("cves:case-detail", kwargs={"pk": self.case_id})

    @property
    def ticket_url(self) -> str:
        return ticket_url(self.sdp_id)
