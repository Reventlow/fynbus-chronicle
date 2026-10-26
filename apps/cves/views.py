"""CVE views — list, detail, create/edit, state changes, cases, and the
HTMX inline add/delete of links, comments and attachments.

Links, comments and attachments belong to a CVE or to a case ("owner").
The same views serve both: the case routes pass ``kind="case"`` (see
urls.py) and :func:`_owner` resolves the right object.

Everyone logged in can read; writes need an editor (Viewer group members
get 403 before anything is written).
"""

from datetime import timedelta

from django.conf import settings
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

from .forms import (
    CVEAttachmentForm, CVECaseAddForm, CVECaseForm, CVECommentForm, CVECreateForm, CVEEditForm, CVELinkForm,
)
from .models import CVE, CaseConflict, CVEAttachment, CVECase, CVEComment, CVELink, normalise_cve_id

# Solved CVEs older than this drop off the list unless "Alle" is picked.
SOLVED_WINDOW_DAYS = 90


def _owner(pk: int, kind: str = "cve"):
    """The CVE or case that a link/comment/attachment URL refers to."""
    return get_object_or_404(CVECase if kind == "case" else CVE, pk=pk)


def _owned_by(owner) -> dict:
    """Filter kwargs selecting rows that belong to ``owner``."""
    return {"case": owner} if owner.is_case else {"cve": owner}

@login_required
def cve_list(request: HttpRequest) -> HttpResponse:
    """All CVEs, open ones first.

    ``?q=`` searches id and subject. ``?state=`` narrows to one state, or
    ``all`` to include solved CVEs older than SOLVED_WINDOW_DAYS days.
    """
    qs = CVE.objects.select_related("created_by", "case")
    q = (request.GET.get("q") or "").strip()
    state = request.GET.get("state") or ""

    if q:
        qs = qs.filter(Q(cve_id__icontains=q) | Q(subject__icontains=q) | Q(case__title__icontains=q)
                       | Q(case__reference__icontains=q))
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
            "open_cases": CVECase.objects.open().open_first().prefetch_related("cves"),
        },
    )


class CVEDetailView(LoginRequiredMixin, DetailView):
    model = CVE
    template_name = "cves/detail.html"
    context_object_name = "cve"

    def get_queryset(self):
        return CVE.objects.select_related("created_by", "solved_by", "case")

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        context["owner"] = self.object
        context["open_cases"] = CVECase.objects.open().order_by("-updated_at") if not self.object.case_id else []
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
    if cve.case_id:
        messages.error(request, f"{cve.cve_id} er en del af sag #{cve.case_id} — skift status på sagen.")
        return redirect(cve.case.get_absolute_url())
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


def _inline_add(request, owner, *, form, row_template, row_name, form_template, container_id, empty_id):
    """Shared success / error responses for the inline add forms."""
    if not form.is_valid():
        response = render(request, form_template, {"owner": owner, "form": form})
        response["HX-Retarget"] = f"#{container_id}"
        response["HX-Reswap"] = "outerHTML"
        return response
    obj = form.instance
    row_html = render_to_string(row_template, {"owner": owner, row_name: obj}, request=request)
    fresh_form = render_to_string(
        form_template, {"owner": owner, "form": type(form)(), "oob": True}, request=request
    )
    empty_oob = f'<p id="{empty_id}" hx-swap-oob="delete"></p>'
    return HttpResponse(row_html + fresh_form + empty_oob)


@login_required
@editor_required
@require_POST
def link_create(request: HttpRequest, pk: int, kind: str = "cve") -> HttpResponse:
    owner = _owner(pk, kind)
    form = CVELinkForm(request.POST)
    if form.is_valid():
        for field, value in _owned_by(owner).items():
            setattr(form.instance, field, value)
        form.instance.added_by = request.user
        form.save()
    return _inline_add(
        request,
        owner,
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
def link_delete(request: HttpRequest, pk: int, link_pk: int, kind: str = "cve") -> HttpResponse:
    owner = _owner(pk, kind)
    link = get_object_or_404(CVELink, pk=link_pk, **_owned_by(owner))
    link.delete()
    owner.touch()
    return HttpResponse("")


@login_required
@editor_required
@require_POST
def attachment_create(request: HttpRequest, pk: int, kind: str = "cve") -> HttpResponse:
    """Attach a PDF or an Outlook mail (HTMX multipart POST).

    For a mail, its headers and text are stored for the preview, a TLP
    found in it is used when none was chosen, and every PDF inside it is
    stored as its own attachment (same TLP, ``parent`` = the mail). The
    response holds a row per created attachment, like the links' add form.
    """
    from django.core.files.base import ContentFile

    owner = _owner(pk, kind)
    owned_by = _owned_by(owner)
    form = CVEAttachmentForm(request.POST, request.FILES)
    if not form.is_valid():
        return _inline_add(request, owner, form=form, row_template="cves/partials/cve_attachment_row.html",
                           row_name="attachment", form_template="cves/partials/cve_attachment_form.html",
                           container_id="cve-attachment-form-container", empty_id="no-cve-attachments")
    upload = form.cleaned_data["file"]
    attachment = form.instance
    for field, value in owned_by.items():
        setattr(attachment, field, value)
    attachment.uploaded_by = request.user
    attachment.original_name = upload.name[:255]
    attachment.size = upload.size
    attachment.kind = form.kind
    info = form.msg_info
    if info is not None:
        attachment.email_subject = info.subject[:500]
        attachment.email_from = info.sender[:300]
        attachment.email_to = "; ".join(x for x in (info.to, info.cc and f"Cc: {info.cc}") if x)
        attachment.email_sent = info.sent
        attachment.email_body = info.body
        if not attachment.tlp:
            from .msg import detect_tlp

            attachment.tlp = detect_tlp(info.subject, info.body)
        if not attachment.source and info.sender:
            attachment.source = info.sender[:100]
    attachment.save()
    created = [attachment]
    for part in (info.attachments if info else []):
        if not part.is_pdf or len(part.data) > settings.CVE_ATTACHMENT_MAX_BYTES:
            continue
        child = CVEAttachment(
            **owned_by, kind=CVEAttachment.Kind.PDF, parent=attachment, uploaded_by=request.user,
            title=part.filename[:200], original_name=part.filename[:255], size=len(part.data),
            source=attachment.source, tlp=attachment.tlp,
        )
        child.file.save("part.pdf", ContentFile(part.data), save=True)
        created.append(child)
    rows = "".join(
        render_to_string("cves/partials/cve_attachment_row.html", {"owner": owner, "attachment": a}, request=request)
        for a in created
    )
    fresh_form = render_to_string(
        "cves/partials/cve_attachment_form.html", {"owner": owner, "form": CVEAttachmentForm(), "oob": True}, request=request
    )
    return HttpResponse(rows + fresh_form + '<p id="no-cve-attachments" hx-swap-oob="delete"></p>')


@login_required
@require_GET
@xframe_options_sameorigin  # the CVE page shows it in a lightbox (same-origin iframe)
def attachment_view(request: HttpRequest, pk: int, key: str, kind: str = "cve") -> HttpResponse:
    """Serve a CVE's attachment to any logged-in user (viewers included).

    PDFs inline by default for the lightbox; ``?download=1`` forces a
    download. A .msg is always a download (the lightbox shows the preview
    page instead). ``no-store``: these can be TLP:AMBER advisories, so no
    copies are kept in shared or browser caches.
    """
    attachment = get_object_or_404(CVEAttachment, key=key, **{f"{kind}_id": pk})
    try:
        handle = attachment.file.open("rb")
    except FileNotFoundError:
        raise Http404
    is_msg = attachment.is_msg
    response = FileResponse(
        handle,
        content_type="application/vnd.ms-outlook" if is_msg else "application/pdf",
        as_attachment=is_msg or request.GET.get("download") == "1",
        filename=attachment.original_name or f"{attachment.key}.{attachment.kind}",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@require_GET
@xframe_options_sameorigin  # shown inside the lightbox iframe
def attachment_preview(request: HttpRequest, pk: int, key: str, kind: str = "cve") -> HttpResponse:
    """Readable preview of an attached Outlook mail for the lightbox.

    Headers and the plain-text body that were extracted at upload, always
    escaped (the mail's own HTML is never rendered), plus links to the PDFs
    that were unpacked from it.
    """
    attachment = get_object_or_404(CVEAttachment, key=key, kind=CVEAttachment.Kind.MSG, **{f"{kind}_id": pk})
    response = render(request, "cves/attachment_preview.html", {
        "attachment": attachment,
        "parts": attachment.extracted.all(),
    })
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@editor_required
@require_http_methods(["DELETE", "POST"])
def attachment_delete(request: HttpRequest, pk: int, key: str, kind: str = "cve") -> HttpResponse:
    attachment = get_object_or_404(CVEAttachment, key=key, **{f"{kind}_id": pk})
    attachment.delete()  # removes the file from disk too
    return HttpResponse("")


@login_required
@editor_required
@require_POST
def comment_create(request: HttpRequest, pk: int, kind: str = "cve") -> HttpResponse:
    owner = _owner(pk, kind)
    form = CVECommentForm(request.POST)
    if form.is_valid():
        for field, value in _owned_by(owner).items():
            setattr(form.instance, field, value)
        form.instance.author = request.user
        form.save()
    return _inline_add(
        request,
        owner,
        form=form,
        row_template="cves/partials/cve_comment_row.html",
        row_name="comment",
        form_template="cves/partials/cve_comment_form.html",
        container_id="cve-comment-form-container",
        empty_id="no-cve-comments",
    )


# -------------------------------------------------------------------------
# Cases: CVEs that share one assessment, one fix and one set of documents
# -------------------------------------------------------------------------


def _resolve_cve_ids(raw: str, *, subject: str, user) -> tuple[list[CVE], list[str]]:
    """CVEs for the ids in ``raw`` (any separators), creating unknown ones.

    Returns (cves, invalid tokens). New CVEs get ``subject`` (the case
    title) and a timeline note that they were created with the case.
    """
    import re

    cves, invalid = [], []
    for token in re.split(r"[\s,;]+", raw or ""):
        if not token:
            continue
        try:
            cve_id = normalise_cve_id(token)
        except ValidationError:
            invalid.append(token)
            continue
        cve = CVE.objects.filter(cve_id=cve_id).first()
        if cve is None:
            cve = CVE.objects.create(cve_id=cve_id, subject=subject[:300], created_by=user)
            CVEComment.objects.create(cve=cve, text="Oprettet sammen med sagen.", author=user)
        if cve not in cves:
            cves.append(cve)
    return cves, invalid


@login_required
def case_list(request: HttpRequest) -> HttpResponse:
    """All cases, open ones first. ``?state=all`` includes old solved ones;
    ``?q=`` searches title, source, reference and member CVE ids in every state."""
    qs = CVECase.objects.prefetch_related("cves")
    state = request.GET.get("state") or ""
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(source__icontains=q) | Q(reference__icontains=q)
                       | Q(cves__cve_id__icontains=q)).distinct()
    elif state != "all":
        cutoff = timezone.now() - timedelta(days=SOLVED_WINDOW_DAYS)
        qs = qs.filter(~Q(state=CVE.State.SOLVED) | Q(solved_at__gte=cutoff) | Q(updated_at__gte=cutoff))
    return render(request, "cves/case_list.html", {
        "cases": qs.open_first(),
        "state": state,
        "q": q,
        "solved_window_days": SOLVED_WINDOW_DAYS,
        "open_count": CVECase.objects.open().count(),
    })


class CVECaseDetailView(LoginRequiredMixin, DetailView):
    model = CVECase
    template_name = "cves/case_detail.html"
    context_object_name = "case"

    def get_queryset(self):
        return CVECase.objects.select_related("created_by", "solved_by")

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        case = self.object
        context.update({
            "owner": case,
            "cves": case.cves.order_by("-cvss", "cve_id"),
            "links": case.links.select_related("added_by"),
            "attachments": case.attachments.select_related("uploaded_by"),
            "attachment_form": CVEAttachmentForm(),
            "comments": case.comments.select_related("author"),
            "link_form": CVELinkForm(),
            "comment_form": CVECommentForm(),
            "add_form": CVECaseAddForm(),
            "outcomes": CASE_OUTCOMES,
        })
        return context


# The state buttons on a case: (state, resolution, label).
CASE_OUTCOMES = [
    (CVE.State.IDENTIFIED, "", "Identificeret"),
    (CVE.State.PATCHING, "", "Patcher"),
    (CVE.State.SOLVED, CVECase.Resolution.PATCHED, "Løst — patchet"),
    (CVE.State.SOLVED, CVECase.Resolution.NOT_AFFECTED, "Løst — ikke berørt"),
]


class CVECaseCreateView(EditorRequiredMixin, CreateView):
    """Start a case, optionally with CVE ids (``?cve_ids=`` prefills them,
    which the "Ny sag" button on a CVE page uses)."""

    model = CVECase
    form_class = CVECaseForm
    template_name = "cves/case_form.html"

    def get_initial(self) -> dict:
        initial = super().get_initial()
        if self.request.GET.get("cve_ids"):
            initial["cve_ids"] = self.request.GET["cve_ids"]
            first = CVE.objects.filter(cve_id=self.request.GET["cve_ids"].split(",")[0].strip().upper()).first()
            if first:
                initial["title"] = first.subject
        return initial

    def form_valid(self, form):
        from django.db import transaction

        cves = form.cleaned_data["cves"]
        taken = [c for c in cves if c.case_id]
        if taken:
            form.add_error("cve_ids", "Allerede i en anden sag: " + ", ".join(f"{c.cve_id} (sag #{c.case_id})" for c in taken))
            return self.form_invalid(form)
        with transaction.atomic():
            form.instance.created_by = self.request.user
            self.object = form.save()
            new_cves, _ = _resolve_cve_ids(form.cleaned_data["cve_ids"], subject=self.object.title, user=self.request.user)
            self.object.add_cves(new_cves, self.request.user)
        messages.success(self.request, f"Sag #{self.object.pk} er oprettet.")
        return redirect(self.object.get_absolute_url())


class CVECaseUpdateView(EditorRequiredMixin, UpdateView):
    model = CVECase
    form_class = CVECaseForm
    template_name = "cves/case_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["with_cves"] = False  # members are managed on the case page
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, f"Sag #{self.object.pk} er opdateret.")
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return self.object.get_absolute_url()


@login_required
@editor_required
@require_POST
def case_state(request: HttpRequest, pk: int) -> HttpResponse:
    """Move a case and all its CVEs (``POST state`` + optional ``resolution``)."""
    case = get_object_or_404(CVECase, pk=pk)
    new_state = request.POST.get("state", "")
    resolution = request.POST.get("resolution", "")
    if new_state not in CVE.State.values or (resolution and resolution not in CVECase.Resolution.values):
        return HttpResponse("Ugyldig status", status=400)
    if case.set_state(new_state, request.user, resolution=resolution):
        messages.success(request, f"Sag #{case.pk}: {case.outcome_label}.")
    return redirect(case.get_absolute_url())


@login_required
@editor_required
@require_POST
def case_add_cves(request: HttpRequest, pk: int) -> HttpResponse:
    """Add CVEs by id to a case (unknown ids are created)."""
    case = get_object_or_404(CVECase, pk=pk)
    form = CVECaseAddForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors["cve_ids"][0])
        return redirect(case.get_absolute_url())
    taken = [c for c in form.cleaned_data["cves"] if c.case_id and c.case_id != case.pk]
    if taken:
        messages.error(request, "Allerede i en anden sag: " + ", ".join(f"{c.cve_id} (sag #{c.case_id})" for c in taken))
        return redirect(case.get_absolute_url())
    cves, _ = _resolve_cve_ids(form.cleaned_data["cve_ids"], subject=case.title, user=request.user)
    added = case.add_cves(cves, request.user)
    if added:
        messages.success(request, "Tilføjet: " + ", ".join(c.cve_id for c in added))
    return redirect(case.get_absolute_url())


@login_required
@editor_required
@require_POST
def case_remove_cve(request: HttpRequest, pk: int, cve_pk: int) -> HttpResponse:
    case = get_object_or_404(CVECase, pk=pk)
    cve = get_object_or_404(CVE, pk=cve_pk, case=case)
    case.remove_cve(cve, request.user)
    messages.success(request, f"{cve.cve_id} er taget ud af sagen.")
    return redirect(case.get_absolute_url())


@login_required
@editor_required
@require_POST
def cve_join_case(request: HttpRequest, pk: int) -> HttpResponse:
    """From a CVE page: put this CVE into an open case (``POST case``)."""
    cve = get_object_or_404(CVE, pk=pk)
    case = get_object_or_404(CVECase, pk=request.POST.get("case") or 0)
    try:
        case.add_cves([cve], request.user)
    except CaseConflict:
        messages.error(request, f"{cve.cve_id} er allerede i sag #{cve.case_id}.")
        return redirect(cve.get_absolute_url())
    messages.success(request, f"{cve.cve_id} er føjet til sag #{case.pk}.")
    return redirect(case.get_absolute_url())
