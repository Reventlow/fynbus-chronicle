"""Turn an uploaded presentation into a PDF the player can show.

Browsers cannot display .pptx/.ppt/.odp, so on upload each presentation
is converted with LibreOffice running headless in the web container. The
result is stored as ``CourseMaterial.preview``; the original stays the
download. Conversion runs on a copy in a private temp directory with its
own LibreOffice profile, so parallel conversions do not share a profile
lock and nothing is written beside the stored file. Macros never run:
headless conversion does not execute document macros.
"""

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files import File

from .filetypes import extension
from .models import CourseMaterial

logger = logging.getLogger(__name__)


def soffice_path() -> str | None:
    return shutil.which(settings.COURSE_SOFFICE)


def make_preview(item: CourseMaterial) -> str | None:
    """Convert ``item``'s presentation to PDF and store it as its preview.

    Returns None on success, or a Danish reason on failure (also saved in
    ``preview_error`` so the page can show it). Never raises for a bad file.
    """
    if item.kind != CourseMaterial.Kind.SLIDES or not item.file:
        return None
    error = _convert(item)
    item.preview_error = error or ""
    item.save(update_fields=["preview", "preview_error"])
    return error


def _convert(item: CourseMaterial) -> str | None:
    soffice = soffice_path()
    if not soffice:
        return "LibreOffice er ikke installeret, så præsentationen kan ikke vises. Den kan stadig hentes."
    with tempfile.TemporaryDirectory(prefix="chronicle-slides-") as tmp:
        tmpdir = Path(tmp)
        src = tmpdir / f"slides{extension(item.original_name or item.file.name)}"
        with item.file.open("rb") as f, open(src, "wb") as out:
            shutil.copyfileobj(f, out)
        cmd = [
            soffice,
            f"-env:UserInstallation=file://{tmpdir / 'profile'}",
            "--headless", "--norestore", "--nologo", "--nolockcheck",
            "--convert-to", "pdf", "--outdir", str(tmpdir / "out"), str(src),
        ]
        try:
            subprocess.run(
                cmd, capture_output=True, timeout=settings.COURSE_CONVERT_TIMEOUT, check=False,
                env={**os.environ, "HOME": str(tmpdir)},
            )
        except subprocess.TimeoutExpired:
            logger.warning("courses: converting %s timed out", item.key)
            return f"Konverteringen tog mere end {settings.COURSE_CONVERT_TIMEOUT} sekunder og blev opgivet."
        except OSError:
            logger.exception("courses: could not start LibreOffice for %s", item.key)
            return "LibreOffice kunne ikke startes."
        pdf = tmpdir / "out" / "slides.pdf"
        if not pdf.exists() or pdf.stat().st_size == 0:
            logger.warning("courses: LibreOffice made no PDF for %s", item.key)
            return "LibreOffice kunne ikke læse præsentationen. Den kan stadig hentes."
        with open(pdf, "rb") as f:
            if f.read(5) != b"%PDF-":
                return "LibreOffice lavede ikke en gyldig PDF."
            f.seek(0)
            if item.preview:
                item.preview.delete(save=False)
            item.preview.save("preview.pdf", File(f), save=False)
    return None
