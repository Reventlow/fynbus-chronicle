"""Report pages: list for logged-in users, standalone rendering, public token link.

Rendering deliberately bypasses ``base.html``: a report is a complete
document with its own styling, so it gets neither the nav nor any of the
site's theme tokens. If the stored HTML is not already a full document, it
is wrapped in a minimal skeleton with the report title.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import editor_required, is_editor
from chronicle.http import serve_file

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


def _report_for(request: HttpRequest, slug: str) -> Report | None:
    """Look up a report by slug for this visitor, or ``None`` to ask for login.

    Signed-in users get the report or a 404. Anonymous visitors get the
    report only while it is public; an unknown slug and a private one both
    send them to the login page, so the answer never tells which slugs exist.
    """
    if request.user.is_authenticated:
        return get_object_or_404(Report, slug=slug)
    return Report.objects.filter(slug=slug, is_public=True).first()


def report_view(request: HttpRequest, slug: str) -> HttpResponse:
    """The readable address. Open to everyone while the report is public;
    otherwise it behaves like any other Chronicle page and asks for login."""
    report = _report_for(request, slug)
    if report is None:
        return redirect_to_login(request.get_full_path())
    return render_report(report, public=report.is_public)


def _serve_video(request: HttpRequest, report: Report) -> HttpResponse:
    """Stream the attached MP4 with HTTP Range support, so the browser can
    seek. ``?download=1`` sends it as an attachment named after the slug."""
    if not report.video:
        raise Http404
    return serve_file(
        request,
        report.video.path,
        content_type="video/mp4",
        filename=f"{report.slug}.mp4",
        as_attachment=request.GET.get("download") == "1",
    )


def report_video(request: HttpRequest, slug: str) -> HttpResponse:
    report = _report_for(request, slug)
    if report is None:
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
