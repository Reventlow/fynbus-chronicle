"""Upload and serve images pasted into description fields."""

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, UnidentifiedImageError

from apps.accounts.permissions import editor_required
from apps.logbook.templatetags.markdown_extras import render_markdown

from .models import PastedImage

# A full-screen screenshot on a 4K display as PNG is ~5–8 MB.
MAX_BYTES = 15 * 1024 * 1024
# Guard against decompression bombs: a tiny file declaring huge dimensions.
MAX_PIXELS = 50_000_000


def _error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


@login_required
@editor_required
@require_POST
def upload(request: HttpRequest) -> HttpResponse:
    """Accept one image as ``image`` in a multipart POST, answer with its URL.

    The format is decided by Pillow reading the bytes, not by the file name
    or the Content-Type the browser sent, so only real PNG/JPEG/GIF/WebP
    images are stored and they are served back with a matching type.
    """
    upload = request.FILES.get("image")
    if upload is None:
        return _error("Intet billede i forespørgslen.")
    if upload.size > MAX_BYTES:
        return _error(f"Billedet er for stort (maks. {MAX_BYTES // (1024 * 1024)} MB).", 413)

    try:
        with Image.open(upload) as img:
            fmt = img.format
            width, height = img.size
            if width * height > MAX_PIXELS:
                return _error("Billedet har for mange pixels.")
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        return _error("Filen er ikke et billede, Chronicle kan vise.")
    if fmt not in PastedImage.FORMATS:
        return _error("Kun PNG, JPEG, GIF og WebP understøttes.")

    upload.seek(0)
    image = PastedImage(
        content_type=PastedImage.FORMATS[fmt][1],
        width=width,
        height=height,
        uploaded_by=request.user,
        created_at=timezone.now(),  # the file path is derived from it
    )
    image.file.save("pasted", upload, save=False)
    image.save()
    return JsonResponse(
        {"url": image.get_absolute_url(), "markdown": image.markdown(), "width": width, "height": height},
        status=201,
    )


@login_required
@require_GET
def view(request: HttpRequest, key: str) -> HttpResponse:
    """Serve an image to any logged-in user (viewers included).

    The key never changes and the bytes behind it never change, so the
    browser may keep it for a long time — but only privately.
    """
    image = get_object_or_404(PastedImage, key=key)
    try:
        handle = image.file.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(handle, content_type=image.content_type)
    response["Content-Disposition"] = f'inline; filename="{image.key}.{image.extension}"'
    response["Cache-Control"] = "private, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# Descriptions are short; this only stops the preview being used to make the
# server render megabytes of Markdown.
MAX_PREVIEW_CHARS = 100_000


@login_required
@editor_required
@require_POST
def preview(request: HttpRequest) -> HttpResponse:
    """Render a description as the detail page will, for the live preview.

    Goes through the same ``render_markdown`` filter (and so the same nh3
    sanitising) as the saved description, so what the preview shows is
    exactly what will be shown after saving.
    """
    text = request.POST.get("text", "")[:MAX_PREVIEW_CHARS]
    return HttpResponse(render_markdown(text), content_type="text/html; charset=utf-8")
