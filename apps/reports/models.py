"""Standalone report pages published inside Chronicle.

A ``Report`` is a self-contained HTML document (its own CSS and JS, no
Chronicle chrome, none of the site's theme tokens) that editors upload or
push through the API — the animated year-in-review, a one-off analysis, a
slide deck exported as HTML. Reports are listed under the "Rapporter" menu
for logged-in users. A report marked public needs no login: both its
readable address (``/reports/<slug>/``) and its token link
(``/reports/p/<token>/``) open for anyone, so it can be sent to people who
do not use Chronicle. Making it private again closes both at once.

The token link exists for links already sent out and as an address that
does not reveal the title; it is long (32 url-safe characters) and can be
rotated.
"""

import secrets

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


def _new_token() -> str:
    return secrets.token_urlsafe(24)  # 32 characters


class ReportFileStorage(FileSystemStorage):
    """Storage rooted at REPORT_FILES_DIR, resolved at run time so tests and
    Docker can point it elsewhere. Files are served by a view with the same
    access rules as the report, never by the static file server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def base_location(self):  # type: ignore[override]
        return str(settings.REPORT_FILES_DIR)

    @property
    def location(self):  # type: ignore[override]
        return str(settings.REPORT_FILES_DIR)


def _video_path(instance: "Report", filename: str) -> str:
    return f"{instance.slug}/video.mp4"


class Report(models.Model):
    title = models.CharField("Titel", max_length=200)
    slug = models.SlugField("Slug", max_length=220, unique=True, allow_unicode=False)
    description = models.CharField(
        "Beskrivelse", max_length=300, blank=True, help_text="Én linje under titlen i listen."
    )
    html = models.TextField(
        "HTML",
        help_text=(
            "Hele sidens indhold som selvstændig HTML. Serveres uden Chronicles layout og farver; "
            "<title> og <style> må ligge øverst i indholdet."
        ),
    )
    is_public = models.BooleanField(
        "Offentligt link",
        default=False,
        help_text="Når sand kan rapporten åbnes uden login på det ugættelige link.",
    )
    public_token = models.CharField(max_length=64, unique=True, default=_new_token, editable=False)
    video = models.FileField(
        "Video",
        upload_to=_video_path,
        storage=ReportFileStorage(),
        blank=True,
        help_text="Valgfri MP4 af rapporten. Vises under siden og kan downloades.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reports"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rapport"
        verbose_name_plural = "Rapporter"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.unique_slug(self.title)
        super().save(*args, **kwargs)

    @classmethod
    def unique_slug(cls, title: str) -> str:
        """ASCII slug from a Danish title (æøå → ae/oe/aa), de-duplicated with a counter."""
        base = slugify(title.replace("æ", "ae").replace("ø", "oe").replace("å", "aa").replace("Æ", "Ae").replace("Ø", "Oe").replace("Å", "Aa")) or "rapport"
        slug, n = base, 2
        while cls.objects.filter(slug=slug).exists():
            slug = f"{base}-{n}"
            n += 1
        return slug

    def get_absolute_url(self) -> str:
        return reverse("reports:view", kwargs={"slug": self.slug})

    def get_public_path(self) -> str:
        return reverse("reports:public", kwargs={"token": self.public_token})

    def get_video_path(self) -> str:
        return reverse("reports:video", kwargs={"slug": self.slug})

    def rotate_token(self) -> None:
        """Issue a new public link; the old one stops working at once."""
        self.public_token = _new_token()
        self.save(update_fields=["public_token", "updated_at"])
