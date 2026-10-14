"""Images pasted (Ctrl+V) or dropped into a description field.

The browser uploads the image the moment it is pasted and writes a Markdown
reference, ``![billede](/images/<key>/)``, into the textarea at the cursor.
The description itself stays plain text; the image lives here, keyed by a
random hex string so its address cannot be guessed or enumerated.

Images are not tied to the task or feature request they were pasted into:
the description is free text and can be copied, edited or abandoned before
it is saved. An image whose reference was deleted from the text simply
stays on disk — they are small, and nothing links to them any more.

Files sit in ``IMAGE_FILES_DIR`` (beside the database, on the persisted
volume in Docker) and are served by a login-gated view, never as static
media: production has no media server, and these are internal screenshots.
"""

import secrets

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse


def _new_key() -> str:
    return secrets.token_hex(16)


class ImageFileStorage(FileSystemStorage):
    """Storage rooted at IMAGE_FILES_DIR, resolved at run time so tests and
    Docker can point it elsewhere."""

    @property
    def base_location(self):  # type: ignore[override]
        return str(settings.IMAGE_FILES_DIR)

    @property
    def location(self):  # type: ignore[override]
        return str(settings.IMAGE_FILES_DIR)


def _image_path(instance: "PastedImage", filename: str) -> str:
    # The extension comes from the format Pillow detected, not the client.
    return f"{instance.created_at:%Y/%m}/{instance.key}.{instance.extension}"


class PastedImage(models.Model):
    """One image uploaded from a description field."""

    # Pillow format name -> (file extension, Content-Type).
    FORMATS = {
        "PNG": ("png", "image/png"),
        "JPEG": ("jpg", "image/jpeg"),
        "GIF": ("gif", "image/gif"),
        "WEBP": ("webp", "image/webp"),
    }

    key = models.CharField(max_length=32, unique=True, default=_new_key, editable=False)
    file = models.FileField(storage=ImageFileStorage(), upload_to=_image_path, max_length=200)
    content_type = models.CharField(max_length=40)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pasted_images",
        verbose_name="Uploadet af",
    )
    created_at = models.DateTimeField(verbose_name="Uploadet", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Indsat billede"
        verbose_name_plural = "Indsatte billeder"

    def __str__(self) -> str:
        return f"{self.key} ({self.width}×{self.height})"

    @property
    def extension(self) -> str:
        for ext, ctype in self.FORMATS.values():
            if ctype == self.content_type:
                return ext
        return "bin"

    def get_absolute_url(self) -> str:
        return reverse("images:view", kwargs={"key": self.key})

    def markdown(self) -> str:
        """The reference the browser inserts into the description."""
        return f"![billede]({self.get_absolute_url()})"
