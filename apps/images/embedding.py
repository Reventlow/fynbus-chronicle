"""Make pasted images travel with an exported document.

Pasted images are served by a login-gated view (``/images/<key>/``), so a
PDF renderer, a downloaded HTML file or a mail client cannot fetch them by
URL. The exports therefore swap each ``<img src="/images/<key>/">`` in the
rendered HTML for the image itself:

``embed_as_data_uris``
    For WeasyPrint (PDF) and the standalone HTML export: the bytes go
    straight into the ``src`` as a ``data:`` URI.

``embed_as_cid``
    For email: Outlook classic refuses ``data:`` URIs, so each image becomes
    a ``cid:`` reference and the caller attaches the returned parts inline,
    the same way the helpdesk charts are sent.

Both set an explicit ``width`` no larger than ``max_width``, and the
matching ``height``. Size attributes are the one sizing hint every target
honours — Outlook ignores CSS ``max-width`` and rescales images that lack a
height — and repeated as an inline style for WeasyPrint, which ignores the
attributes. So a large screenshot cannot run off the page or past the edge of
a mail. A reference to an image that no longer exists is dropped
rather than left as a broken link.
"""

import base64
import re
from dataclasses import dataclass

from .models import PastedImage

# Matches the whole <img> tag the Markdown renderer emits for a pasted image.
_IMG_TAG = re.compile(r'<img\b[^>]*\bsrc="/images/([0-9a-f]{32})/"[^>]*>')
_WIDTH_ATTR = re.compile(r'\swidth="(\d+)"')
_STYLE_ATTR = re.compile(r'\sstyle="[^"]*"')


@dataclass
class InlineImage:
    """One image to attach to a mail, referenced from the body as ``cid:<cid>``."""

    cid: str
    data: bytes
    content_type: str

    @property
    def subtype(self) -> str:
        return self.content_type.split("/", 1)[1]


def _load(keys: set[str]) -> dict[str, tuple[PastedImage, bytes]]:
    """Read every referenced image once; missing rows or files are skipped."""
    found: dict[str, tuple[PastedImage, bytes]] = {}
    for image in PastedImage.objects.filter(key__in=keys):
        try:
            with image.file.open("rb") as handle:
                found[image.key] = (image, handle.read())
        except FileNotFoundError:
            continue
    return found


def _rewrite(html: str, max_width: int, new_src) -> str:
    """Replace each pasted-image tag, given ``new_src(key, image, data)``."""
    keys = set(_IMG_TAG.findall(html))
    if not keys:
        return html
    images = _load(keys)

    def replace(match: re.Match) -> str:
        tag, key = match.group(0), match.group(1)
        if key not in images:
            return ""
        image, data = images[key]
        requested = _WIDTH_ATTR.search(tag)
        width = int(requested.group(1)) if requested else image.width
        width = min(width or max_width, max_width)
        # Outlook (Word) rescales an image by its own DPI unless it has both.
        height = round(image.height * width / image.width) if image.width else 0
        size = f'width="{width}"' + (f' height="{height}"' if height else "")
        # WeasyPrint ignores size attributes (presentational hints) unless
        # asked, so the same size goes in a style as well.
        style = f"width: {width}px; height: {f'{height}px' if height else 'auto'};"
        tag = _WIDTH_ATTR.sub("", tag)
        tag = _STYLE_ATTR.sub("", tag)
        return tag.replace(
            f'src="/images/{key}/"', f'src="{new_src(key, image, data)}" {size} style="{style}"'
        )

    return _IMG_TAG.sub(replace, html)


def embed_as_data_uris(html: str, *, max_width: int) -> str:
    """Inline every pasted image as a ``data:`` URI (PDF, HTML export)."""

    def data_uri(key, image, data):
        return f"data:{image.content_type};base64,{base64.b64encode(data).decode('ascii')}"

    return _rewrite(html, max_width, data_uri)


def embed_as_cid(html: str, *, max_width: int) -> tuple[str, list[InlineImage]]:
    """Point every pasted image at a ``cid:`` and return the parts to attach (email)."""
    parts: dict[str, InlineImage] = {}

    def cid(key, image, data):
        name = f"chronicle-image-{key}"
        parts.setdefault(key, InlineImage(cid=name, data=data, content_type=image.content_type))
        return f"cid:{name}"

    return _rewrite(html, max_width, cid), list(parts.values())
