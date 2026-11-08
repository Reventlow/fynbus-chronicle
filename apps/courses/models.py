"""Course material (Kursusmateriale): folders of videos, slides, PDFs and links.

A ``CourseFolder`` is a bucket such as "Anthropic" or "Microsoft 365"; a
``CourseMaterial`` is one item in it. Files live under COURSE_FILES_DIR
(beside the database, on the persisted volume) and are served by a view,
never by the static or media file server. Anyone can browse, watch and
download, without logging in; only editors can change anything.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .filetypes import TYPES, extension


def _new_key() -> str:
    return secrets.token_hex(16)


def _ascii_slug(text: str, fallback: str) -> str:
    """ASCII slug from a Danish name (æøå → ae/oe/aa)."""
    for a, b in (("æ", "ae"), ("ø", "oe"), ("å", "aa"), ("Æ", "Ae"), ("Ø", "Oe"), ("Å", "Aa")):
        text = text.replace(a, b)
    return slugify(text) or fallback


class CourseFileStorage(FileSystemStorage):
    """Storage rooted at COURSE_FILES_DIR, resolved at run time so tests and
    Docker can point it elsewhere."""

    @property
    def base_location(self):  # type: ignore[override]
        return str(settings.COURSE_FILES_DIR)

    @property
    def location(self):  # type: ignore[override]
        return str(settings.COURSE_FILES_DIR)


def _material_path(instance: "CourseMaterial", filename: str) -> str:
    # Named by the random key, not the folder, so moving an item to another
    # folder never has to move the file.
    return f"{instance.key[:2]}/{instance.key}{extension(filename)}"


def _preview_path(instance: "CourseMaterial", filename: str) -> str:
    return f"{instance.key[:2]}/{instance.key}.preview.pdf"


class CourseFolder(models.Model):
    name = models.CharField("Navn", max_length=100, unique=True)
    slug = models.SlugField("Slug", max_length=120, unique=True)
    description = models.CharField(
        "Beskrivelse", max_length=300, blank=True, help_text="Én linje om, hvad mappen indeholder."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kursusmappe"
        verbose_name_plural = "Kursusmapper"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.unique_slug(self.name)
        super().save(*args, **kwargs)

    # First path segments under /kursus/ that are not folders (see urls.py).
    RESERVED_SLUGS = {"fil", "visning", "element", "hentning"}

    @classmethod
    def unique_slug(cls, name: str, exclude_pk: int | None = None) -> str:
        base = _ascii_slug(name, "mappe")[:110]
        slug, n = base, 2
        while slug in cls.RESERVED_SLUGS or cls.objects.filter(slug=slug).exclude(pk=exclude_pk).exists():
            slug = f"{base}-{n}"
            n += 1
        return slug

    def get_absolute_url(self) -> str:
        return reverse("courses:folder", kwargs={"slug": self.slug})


class CourseMaterial(models.Model):
    """One video, presentation, PDF or link. A link has a URL and no file;
    everything else has a file and no URL."""

    class Kind(models.TextChoices):
        VIDEO = "video", "Video"
        SLIDES = "slides", "Præsentation"
        PDF = "pdf", "PDF"
        LINK = "link", "Link"

    folder = models.ForeignKey(CourseFolder, on_delete=models.CASCADE, related_name="materials", verbose_name="Mappe")
    kind = models.CharField("Type", max_length=10, choices=Kind.choices)
    title = models.CharField("Titel", max_length=200)
    description = models.CharField("Beskrivelse", max_length=500, blank=True)
    key = models.CharField(max_length=32, unique=True, default=_new_key, editable=False)
    file = models.FileField(storage=CourseFileStorage(), upload_to=_material_path, max_length=200, blank=True)
    original_name = models.CharField("Filnavn", max_length=255, blank=True)
    size = models.PositiveBigIntegerField("Størrelse (bytes)", default=0)
    url = models.URLField("Link", max_length=1000, blank=True)
    # Presentations only: a PDF rendition made with LibreOffice at upload,
    # which the player shows slide by slide (browsers cannot show .pptx).
    preview = models.FileField(storage=CourseFileStorage(), upload_to=_preview_path, max_length=200, blank=True)
    preview_error = models.CharField("Visningsfejl", max_length=300, blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="Tilføjet af",
    )
    added_at = models.DateTimeField("Tilføjet", default=timezone.now)

    class Meta:
        verbose_name = "Kursusmateriale"
        verbose_name_plural = "Kursusmateriale"
        ordering = ["added_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(kind="link") & ~models.Q(url="") & models.Q(file=""))
                | (~models.Q(kind="link") & models.Q(url="") & ~models.Q(file="")),
                name="coursematerial_link_xor_file",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def is_link(self) -> bool:
        return self.kind == self.Kind.LINK

    @property
    def file_type(self):
        return TYPES.get(extension(self.original_name or self.file.name))

    @property
    def format_label(self) -> str:
        if self.is_link:
            return "Link"
        ft = self.file_type
        return ft.label if ft else self.get_kind_display()

    @property
    def content_type(self) -> str:
        ft = self.file_type
        return ft.content_type if ft else "application/octet-stream"

    @property
    def opens_in_browser(self) -> bool:
        """Videos and PDFs can be sent to the browser as they are."""
        return self.kind in (self.Kind.VIDEO, self.Kind.PDF)

    @property
    def playable(self) -> bool:
        """Shown in the player: videos, PDFs, and presentations once they have a PDF rendition."""
        return self.opens_in_browser or (self.kind == self.Kind.SLIDES and bool(self.preview))

    @property
    def slides_url(self) -> str:
        """The PDF the player renders page by page, or "" for a video or link."""
        if self.kind == self.Kind.PDF:
            return self.get_file_url()
        if self.kind == self.Kind.SLIDES and self.preview:
            return reverse("courses:preview", kwargs={"key": self.key})
        return ""

    def get_file_url(self) -> str:
        return reverse("courses:file", kwargs={"key": self.key})

    def get_download_url(self) -> str:
        return self.get_file_url() + "?download=1"

    def get_player_url(self) -> str:
        return reverse("courses:player", kwargs={"slug": self.folder.slug, "key": self.key})

    @property
    def href(self) -> str:
        """Where clicking the title goes: the player, the link itself, or a download."""
        if self.is_link:
            return self.url
        return self.get_player_url() if self.playable else self.get_download_url()


class CourseImport(models.Model):
    """A file being fetched from a link into a folder ("Hent fra link").

    Lives only while the fetch runs or after it failed: on success the
    material is created and this row is deleted (see fetch.py).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Venter"
        RUNNING = "running", "Henter"
        FAILED = "failed", "Fejlede"

    # A fetch with no progress for this long died with its worker (e.g. a
    # redeploy) and is shown as failed, so it can be retried.
    STALLED_AFTER = timedelta(minutes=10)

    folder = models.ForeignKey(CourseFolder, on_delete=models.CASCADE, related_name="imports")
    url = models.URLField("Link til filen", max_length=1000)
    title = models.CharField("Titel", max_length=200, blank=True)
    description = models.CharField("Beskrivelse", max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    error = models.CharField(max_length=300, blank=True)
    bytes_done = models.PositiveBigIntegerField(default=0)
    bytes_total = models.PositiveBigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Hentning fra link"
        verbose_name_plural = "Hentninger fra link"
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return self.title or self.url

    @property
    def is_failed(self) -> bool:
        return self.status == self.Status.FAILED or self.is_stalled

    @property
    def is_stalled(self) -> bool:
        return self.status != self.Status.FAILED and timezone.now() - self.updated_at > self.STALLED_AFTER

    @property
    def shown_error(self) -> str:
        if self.is_stalled:
            return "Hentningen blev afbrudt (fx af en genstart). Prøv igen."
        return self.error

    @property
    def percent(self) -> int | None:
        if self.bytes_total:
            return min(100, round(self.bytes_done * 100 / self.bytes_total))
        return None


@receiver(post_delete, sender=CourseMaterial)
def _delete_file(sender, instance: CourseMaterial, **kwargs) -> None:
    """Remove the stored files with the row, also when a whole folder is deleted."""
    if instance.file:
        instance.file.delete(save=False)
    if instance.preview:
        instance.preview.delete(save=False)
