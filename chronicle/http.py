"""HTTP helpers shared by apps that serve stored files through a view.

Files uploaded to Chronicle (report videos, course material) never go
through the static or media file server: a view checks access first and
then hands the file to ``serve_file``.
"""

import os
import re

from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    StreamingHttpResponse,
)
from django.utils.http import content_disposition_header

_RANGE = re.compile(r"bytes=(\d*)-(\d*)$")


def serve_file(
    request: HttpRequest,
    path: str,
    *,
    content_type: str,
    filename: str,
    as_attachment: bool = False,
) -> HttpResponse:
    """Send the file at ``path``, honouring a single HTTP Range request.

    Range support is what lets a browser seek in a video without first
    downloading all of it. ``filename`` is what the browser saves it as;
    non-ASCII names are encoded per RFC 6266. Raises Http404 if the file
    is missing on disk.
    """
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise Http404 from exc

    m = _RANGE.match(request.META.get("HTTP_RANGE", ""))
    if m and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
        else:  # "bytes=-N": the last N bytes
            start, end = max(0, size - int(m.group(2))), size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{size}"
            return resp
        length = end - start + 1

        def chunks(f, remaining, block=512 * 1024):
            with f:
                f.seek(start)
                while remaining > 0:
                    data = f.read(min(block, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        resp = StreamingHttpResponse(chunks(open(path, "rb"), length), status=206, content_type=content_type)
        resp["Content-Range"] = f"bytes {start}-{end}/{size}"
        resp["Content-Length"] = str(length)
    else:
        resp = FileResponse(open(path, "rb"), content_type=content_type)
        resp["Content-Length"] = str(size)
    resp["Accept-Ranges"] = "bytes"
    resp["Content-Disposition"] = content_disposition_header(as_attachment, filename)
    resp["X-Content-Type-Options"] = "nosniff"
    resp["X-Robots-Tag"] = "noindex, nofollow"
    resp["Cache-Control"] = "private, no-store"
    return resp
