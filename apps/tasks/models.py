"""
Models for the FynBus Chronicle tasks application.

These models track IT tasks and projects including:
- Tasks with status workflow and assignment
- State change audit log
- Notes with markdown content
- File attachments on notes
"""

import os

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class Task(models.Model):
    """
    Represents an IT task or project to be tracked.

    Tasks flow through a status workflow from todo through
    completion, with optional approval steps.
    """

    class Status(models.TextChoices):
        TODO = "todo", "Todo"
        DOING = "doing", "I gang"
        PAUSED = "paused", "Pause"
        TESTING = "testing", "Test"
        APPROVAL = "approval", "Godkendelse"
        COMPLETE = "complete", "Færdig"

    title = models.CharField(
        verbose_name="Titel",
        max_length=200,
    )
    description = models.TextField(
        verbose_name="Beskrivelse",
        blank=True,
    )
    status = models.CharField(
        verbose_name="Status",
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )
    planned_start = models.DateField(
        verbose_name="Planlagt start",
        null=True,
        blank=True,
    )
    planned_end = models.DateField(
        verbose_name="Planlagt slut",
        null=True,
        blank=True,
    )
    approvers = models.ManyToManyField(
        User,
        related_name="approved_tasks",
        verbose_name="Godkendere",
        blank=True,
    )
    assigned_to = models.ManyToManyField(
        User,
        related_name="assigned_tasks",
        verbose_name="Tildelt",
        blank=True,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks_created",
        verbose_name="Oprettet af",
    )
    created_at = models.DateTimeField(
        verbose_name="Oprettet",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        verbose_name="Opdateret",
        auto_now=True,
    )
    order = models.PositiveIntegerField(
        verbose_name="Rækkefølge",
        default=0,
    )

    class Meta:
        ordering = ["planned_start", "created_at"]
        verbose_name = "Opgave"
        verbose_name_plural = "Opgaver"

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        """Return URL for viewing this task."""
        return reverse("tasks:task-detail", kwargs={"pk": self.pk})


class TaskStateChange(models.Model):
    """
    Audit log for task status changes.

    Records each transition including who made the change
    and when it occurred.
    """

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="state_changes",
        verbose_name="Opgave",
    )
    from_state = models.CharField(
        verbose_name="Fra status",
        max_length=20,
        choices=Task.Status.choices,
        blank=True,
    )
    to_state = models.CharField(
        verbose_name="Til status",
        max_length=20,
        choices=Task.Status.choices,
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_state_changes",
        verbose_name="Ændret af",
    )
    changed_at = models.DateTimeField(
        verbose_name="Ændret",
        auto_now_add=True,
    )

    class Meta:
        ordering = ["changed_at"]
        verbose_name = "Statusændring"
        verbose_name_plural = "Statusændringer"

    def __str__(self) -> str:
        return f"{self.task}: {self.from_state} → {self.to_state}"


class TaskNote(models.Model):
    """
    A note attached to a task.

    Notes support markdown content and can have file attachments.
    """

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="notes",
        verbose_name="Opgave",
    )
    subject = models.CharField(
        verbose_name="Emne",
        max_length=200,
    )
    text = models.TextField(
        verbose_name="Tekst",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_notes",
        verbose_name="Forfatter",
    )
    created_at = models.DateTimeField(
        verbose_name="Oprettet",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        verbose_name="Opdateret",
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Note"
        verbose_name_plural = "Noter"

    def __str__(self) -> str:
        return self.subject


class TaskNoteAttachment(models.Model):
    """
    File attachment on a task note.

    Validates file extensions against an allowed list to prevent
    upload of potentially dangerous file types.
    """

    ALLOWED_EXTENSIONS = [
        ".png", ".jpg", ".jpeg", ".gif",
        ".pdf", ".doc", ".docx",
        ".ppt", ".pptx",
        ".xls", ".xlsx",
        ".md",
    ]

    note = models.ForeignKey(
        TaskNote,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Note",
    )
    file = models.FileField(
        verbose_name="Fil",
        upload_to="tasks/attachments/%Y/%m/",
    )
    filename = models.CharField(
        verbose_name="Filnavn",
        max_length=255,
    )
    uploaded_at = models.DateTimeField(
        verbose_name="Uploadet",
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "Vedhæftet fil"
        verbose_name_plural = "Vedhæftede filer"

    def __str__(self) -> str:
        return self.filename

    def clean(self):
        """Validate that the file extension is allowed."""
        if self.file:
            ext = os.path.splitext(self.file.name)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                raise ValidationError(
                    f"Filtypen '{ext}' er ikke tilladt. "
                    f"Tilladte typer: {', '.join(self.ALLOWED_EXTENSIONS)}"
                )
