"""Report pages: list for logged-in users, standalone rendering, public token link.

Rendering deliberately bypasses ``base.html``: a report is a complete
document with its own styling, so it gets neither the nav nor any of the
site's theme tokens. If the stored HTML is not already a full document, it
is wrapped in a minimal skeleton with the report title.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
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


@login_required
def report_view(request: HttpRequest, slug: str) -> HttpResponse:
    return render_report(get_object_or_404(Report, slug=slug), public=False)


def report_public(request: HttpRequest, token: str) -> HttpResponse:
    """The no-login link. A private report answers 404, not 403, so the
    existence of a report is never confirmed to someone holding an old link."""
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
        report.save()
        messages.success(request, f"”{report.title}” er opdateret.")
    else:
        report = form.save(commit=False)
        report.html = html
        report.created_by = request.user
        report.save()
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
