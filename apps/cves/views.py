"""CVE views — list, detail, create/edit, state changes and the HTMX
inline add/delete of links and comments.

Everyone logged in can read; writes need an editor (Viewer group members
get 403 before anything is written).
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.generic import CreateView, DetailView, UpdateView

from apps.accounts.permissions import EditorRequiredMixin, editor_required

from .forms import CVEAttachmentForm, CVECommentForm, CVECreateForm, CVEEditForm, CVELinkForm
from .models import CVE, CVEAttachment, CVEComment, CVELink, normalise_cve_id

# Solved CVEs older than this drop off the list unless "Alle" is picked.
SOLVED_WINDOW_DAYS = 90

@login_required
def cve_list(request: HttpRequest) -> HttpResponse:
    """All CVEs, open ones first.

    ``?q=`` searches id and subject. ``?state=`` narrows to one state, or
    ``all`` to include solved CVEs older than SOLVED_WINDOW_DAYS days.
    """
    qs = CVE.objects.select_related("created_by")
    q = (request.GET.get("q") or "").strip()
    state = request.GET.get("state") or ""

    if q:
        qs = qs.filter(Q(cve_id__icontains=q) | Q(subject__icontains=q))
    if state in CVE.State.values:
        qs = qs.filter(state=state)
    elif state != "all":
        cutoff = timezone.now() - timedelta(days=SOLVED_WINDOW_DAYS)
        qs = qs.filter(~Q(state=CVE.State.SOLVED) | Q(solved_at__gte=cutoff) | Q(updated_at__gte=cutoff))

    return render(
        request,
        "cves/list.html",
        {
            "cves": qs.open_first(),
            "q": q,
            "state": state,
            "states": CVE.State.choices,
            "solved_window_days": SOLVED_WINDOW_DAYS,
            "open_count": CVE.objects.open().count(),
            "patching_count": CVE.objects.filter(state=CVE.State.PATCHING).count(),
        },
    )


class CVEDetailView(LoginRequiredMixin, DetailView):
    model = CVE
    template_name = "cves/detail.html"
    context_object_name = "cve"

    def get_queryset(self):
        return CVE.objects.select_related("created_by", "solved_by")

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["links"] = self.object.links.select_related("added_by")
        context["attachments"] = self.object.attachments.select_related("uploaded_by")
        context["attachment_form"] = CVEAttachmentForm()
        context["comments"] = self.object.comments.select_related("author")
        context["link_form"] = CVELinkForm()
        context["comment_form"] = CVECommentForm()
        context["states"] = CVE.State.choices
        return context


class CVECreateView(EditorRequiredMixin, CreateView):
    """Register a CVE. Prefilled from the query string, so other tools can
    link here; an id that already exists sends the user to that CVE."""

    model = CVE
    form_class = CVECreateForm
    template_name = "cves/form.html"

    PREFILL_FIELDS = ("cve_id", "subject", "cvss", "severity", "cvefeed_url", "source_url")

    def _existing(self, raw_id: str) -> CVE | None:
        try:
            cve_id = normalise_cve_id(raw_id)
        except ValidationError:
            return None
        return CVE.objects.filter(cve_id=cve_id).first()

    def _redirect_existing(self, cve: CVE) -> HttpResponse:
        messages.info(self.request, f"{cve.cve_id} findes allerede — her er den.")
        return redirect(cve.get_absolute_url())

    def get(self, request, *args, **kwargs):
        existing = self._existing(request.GET.get("cve_id", ""))
        if existing:
            return self._redirect_existing(existing)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        existing = self._existing(request.POST.get("cve_id", ""))
        if existing:
            return self._redirect_existing(existing)
        return super().post(request, *args, **kwargs)

    def get_initial(self) -> dict:
        initial = super().get_initial()
        for field in self.PREFILL_FIELDS:
            value = (self.request.GET.get(field) or "").strip()
            if value:
                initial[field] = value
        if "cve_id" in initial:
            initial["cve_id"] = initial["cve_id"].upper()
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        if form.instance.source_url and not form.instance.source:
            form.instance.source = "harbinger"
        response = super().form_valid(form)
        comment = (form.cleaned_data.get("comment") or "").strip()
        if comment:
            CVEComment.objects.create(cve=self.object, text=comment, author=self.request.user)
        messages.success(self.request, f"{self.object.cve_id} er oprettet.")
        return response

    def get_success_url(self) -> str:
        return self.object.get_absolute_url()


class CVEUpdateView(EditorRequiredMixin, UpdateView):
    model = CVE
    form_class = CVEEditForm
    template_name = "cves/form.html"

    def form_valid(self, form):
        messages.success(self.request, f"{self.object.cve_id} er opdateret.")
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return self.object.get_absolute_url()


@login_required
@editor_required
@require_POST
def set_state(request: HttpRequest, pk: int) -> HttpResponse:
    """Move a CVE to the state in ``POST['state']``."""
    cve = get_object_or_404(CVE, pk=pk)
    new_state = request.POST.get("state", "")
    if new_state not in CVE.State.values:
        return HttpResponse("Ugyldig status", status=400)
    if cve.set_state(new_state, request.user):
        messages.success(request, f"{cve.cve_id}: {cve.get_state_display()}.")
    return redirect(cve.get_absolute_url())


# -------------------------------------------------------------------------
# HTMX: links and comments
#
# The add form is always on the page. A valid POST returns the new row
# (swapped into the list) plus an out-of-band fresh form and removal of the
# empty-state line; an invalid one re-renders the form in place via
# HX-Retarget / HX-Reswap.
# -------------------------------------------------------------------------


def _inline_add(request, cve, *, form, row_template, row_name, form_template, container_id, empty_id):
    """Shared success / error responses for the inline add forms."""
    if not form.is_valid():
        response = render(request, form_template, {"cve": cve, "form": form})
        response["HX-Retarget"] = f"#{container_id}"
        response["HX-Reswap"] = "outerHTML"
        return response
    obj = form.instance
    row_html = render_to_string(row_template, {"cve": cve, row_name: obj}, request=request)
    fresh_form = render_to_string(
        form_template, {"cve": cve, "form": type(form)(), "oob": True}, request=request
    )
    empty_oob = f'<p id="{empty_id}" hx-swap-oob="delete"></p>'
    return HttpResponse(row_html + fresh_form + empty_oob)


@login_required
@editor_required
@require_POST
def link_create(request: HttpRequest, pk: int) -> HttpResponse:
    cve = get_object_or_404(CVE, pk=pk)
    form = CVELinkForm(request.POST)
    if form.is_valid():
        form.instance.cve = cve
        form.instance.added_by = request.user
        form.save()
    return _inline_add(
        request,
        cve,
        form=form,
        row_template="cves/partials/cve_link_row.html",
        row_name="link",
        form_template="cves/partials/cve_link_form.html",
        container_id="cve-link-form-container",
        empty_id="no-cve-links",
    )


@login_required
@editor_required
@require_http_methods(["DELETE", "POST"])
def link_delete(request: HttpRequest, pk: int, link_pk: int) -> HttpResponse:
    link = get_object_or_404(CVELink, pk=link_pk, cve_id=pk)
    cve = link.cve
    link.delete()
    cve.touch()
    return HttpResponse("")


@login_required
@editor_required
@require_POST
def attachment_create(request: HttpRequest, pk: int) -> HttpResponse:
    """Attach a PDF (HTMX multipart POST); returns the new row like links do."""
    cve = get_object_or_404(CVE, pk=pk)
    form = CVEAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        upload = form.cleaned_data["file"]
        form.instance.cve = cve
        form.instance.uploaded_by = request.user
        form.instance.original_name = upload.name[:255]
        form.instance.size = upload.size
        form.save()
    return _inline_add(
        request,
        cve,
        form=form,
        row_template="cves/partials/cve_attachment_row.html",
        row_name="attachment",
        form_template="cves/partials/cve_attachment_form.html",
        container_id="cve-attachment-form-container",
        empty_id="no-cve-attachments",
    )


@login_required
@require_GET
@xframe_options_sameorigin  # the CVE page shows it in a lightbox (same-origin iframe)
def attachment_view(request: HttpRequest, pk: int, key: str) -> HttpResponse:
    """Serve a CVE's PDF to any logged-in user (viewers included).

    Inline by default for the lightbox; ``?download=1`` forces a download.
    ``no-store``: these can be TLP:AMBER advisories, so no copies are kept in
    shared or browser caches.
    """
    attachment = get_object_or_404(CVEAttachment, cve_id=pk, key=key)
    try:
        handle = attachment.file.open("rb")
    except FileNotFoundError:
        raise Http404
    response = FileResponse(
        handle,
        content_type="application/pdf",
        as_attachment=request.GET.get("download") == "1",
        filename=attachment.original_name or f"{attachment.key}.pdf",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@editor_required
@require_http_methods(["DELETE", "POST"])
def attachment_delete(request: HttpRequest, pk: int, key: str) -> HttpResponse:
    attachment = get_object_or_404(CVEAttachment, cve_id=pk, key=key)
    attachment.delete()  # removes the file from disk too
    return HttpResponse("")


@login_required
@editor_required
@require_POST
def comment_create(request: HttpRequest, pk: int) -> HttpResponse:
    cve = get_object_or_404(CVE, pk=pk)
    form = CVECommentForm(request.POST)
    if form.is_valid():
        form.instance.cve = cve
        form.instance.author = request.user
        form.save()
    return _inline_add(
        request,
        cve,
        form=form,
        row_template="cves/partials/cve_comment_row.html",
        row_name="comment",
        form_template="cves/partials/cve_comment_form.html",
        container_id="cve-comment-form-container",
        empty_id="no-cve-comments",
    )
