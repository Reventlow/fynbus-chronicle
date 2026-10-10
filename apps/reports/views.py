"""Report pages: list for logged-in users, standalone rendering, public token link.

Rendering deliberately bypasses ``base.html``: a report is a complete
document with its own styling, so it gets neither the nav nor any of the
site's theme tokens. If the stored HTML is not already a full document, it
is wrapped in a minimal skeleton with the report title.
"""

import os
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import editor_required, is_editor

from .forms import ReportUploadForm
from .models import Report

_SKELETON = (
    '<!doctype html><html lang="da"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    "<title>{title}</title></head><body>{body}</body></html>"
)


def render_report(report: Report, *, public: bool) -> HttpResponse:
    """Serve the report as its own document. Never indexed, never cached by shared caches."""
    html = report.html
    if not html.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        html = _SKELETON.format(title=report.title.replace("<", "&lt;"), body=html)
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Cache-Control"] = "private, no-store" if public else "private, max-age=0"
    response["Referrer-Policy"] = "no-referrer"  # the token must never leak via Referer
    return response


@login_required
def report_list(request: HttpRequest) -> HttpResponse:
    reports = Report.objects.select_related("created_by")
    return render(
        request,
        "reports/list.html",
        {"reports": reports, "form": ReportUploadForm(), "is_editor": is_editor(request.user)},
    )


def report_view(request: HttpRequest, slug: str) -> HttpResponse:
    """The readable address. Open to everyone while the report is public;
    otherwise it behaves like any other Chronicle page and asks for login."""
    report = get_object_or_404(Report, slug=slug)
    if report.is_public:
        return render_report(report, public=True)
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    return render_report(report, public=False)


def _serve_video(request: HttpRequest, report: Report) -> HttpResponse:
    """Stream the attached MP4 with HTTP Range support, so the browser can
    seek. ``?download=1`` sends it as an attachment named after the slug."""
    if not report.video:
        raise Http404
    path = report.video.path
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise Http404 from exc
    filename = f"{report.slug}.mp4"
    disposition = ("attachment" if request.GET.get("download") == "1" else "inline") + f'; filename="{filename}"'
    range_header = request.META.get("HTTP_RANGE", "")
    m = re.match(r"bytes=(\d*)-(\d*)$", range_header)
    if m and (m.group(1) or m.group(2)):
        start = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2)))
        end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
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

        resp = StreamingHttpResponse(chunks(open(path, "rb"), length), status=206, content_type="video/mp4")
        resp["Content-Range"] = f"bytes {start}-{end}/{size}"
        resp["Content-Length"] = str(length)
    else:
        resp = FileResponse(open(path, "rb"), content_type="video/mp4")
        resp["Content-Length"] = str(size)
    resp["Accept-Ranges"] = "bytes"
    resp["Content-Disposition"] = disposition
    resp["X-Robots-Tag"] = "noindex, nofollow"
    resp["Cache-Control"] = "private, no-store"
    return resp


def report_video(request: HttpRequest, slug: str) -> HttpResponse:
    report = get_object_or_404(Report, slug=slug)
    if not report.is_public and not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    return _serve_video(request, report)


def report_public_video(request: HttpRequest, token: str) -> HttpResponse:
    report = Report.objects.filter(public_token=token, is_public=True).first()
    if report is None:
        raise Http404
    return _serve_video(request, report)


def report_public(request: HttpRequest, token: str) -> HttpResponse:
    """The token link, kept for links already sent out. A private report
    answers 404, not 403, so an old link confirms nothing."""
    report = Report.objects.filter(public_token=token, is_public=True).first()
    if report is None:
        raise Http404
    return render_report(report, public=True)


@login_required
@editor_required
@require_POST
def report_upload(request: HttpRequest) -> HttpResponse:
    form = ReportUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = "; ".join(f"{field}: {', '.join(errs)}" for field, errs in form.errors.items())
        messages.error(request, f"Rapporten blev ikke gemt. {errors}")
        return redirect("reports:list")
    replace_slug = (request.POST.get("replace") or "").strip()
    html = form.cleaned_data["html_text"]
    if replace_slug:
        report = get_object_or_404(Report, slug=replace_slug)
        report.title = form.cleaned_data["title"]
        report.description = form.cleaned_data["description"]
        report.is_public = form.cleaned_data["is_public"]
        report.html = html
        if form.cleaned_data.get("video"):
            report.video = form.cleaned_data["video"]
        report.save()
        messages.success(request, f"”{report.title}” er opdateret.")
    else:
        report = form.save(commit=False)
        report.html = html
        report.created_by = request.user
        report.save()  # slug first, the video path is derived from it
        if form.cleaned_data.get("video"):
            report.video = form.cleaned_data["video"]
            report.save(update_fields=["video", "updated_at"])
        messages.success(request, f"”{report.title}” er lagt op.")
    return redirect("reports:list")


@login_required
@editor_required
@require_POST
def report_visibility(request: HttpRequest, slug: str) -> HttpResponse:
    report = get_object_or_404(Report, slug=slug)
    report.is_public = request.POST.get("public") == "1"
    report.save(update_fields=["is_public", "updated_at"])
    messages.success(
        request,
        f"”{report.title}” er nu {'offentlig på sit link' if report.is_public else 'kun for indloggede'}.",
    )
    return redirect("reports:list")


@login_required
@editor_required
@require_POST
def report_rotate(request: HttpRequest, slug: str) -> HttpResponse:
    report = get_object_or_404(Report, slug=slug)
    report.rotate_token()
    messages.success(request, f"Nyt offentligt link til ”{report.title}”. Det gamle virker ikke længere.")
    return redirect("reports:list")


@login_required
@editor_required
@require_POST
def report_delete(request: HttpRequest, slug: str) -> HttpResponse:
    report = get_object_or_404(Report, slug=slug)
    title = report.title
    report.delete()
    messages.success(request, f"”{title}” er slettet.")
    return redirect("reports:list")
