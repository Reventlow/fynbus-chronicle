"""Kursusmateriale: folders of course videos, slides, PDFs and links.

Browsing, watching and downloading need no login, so material can be
shared with colleagues who do not use Chronicle; the pages are marked
noindex and hide who uploaded what from anonymous visitors. Editors
(logged-in users not in the Viewer group) create folders and add, edit
and delete items.
Uploads go through HTMX so the page can show a progress bar; a failed
upload re-renders the form in place, a successful one redirects.
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import editor_required, is_editor
from chronicle.http import serve_file

from .filetypes import TYPES, extension
from .forms import FolderForm, MaterialEditForm, MaterialForm
from .models import CourseFolder, CourseMaterial

# (kind, heading) in the order the folder page lists them.
SECTIONS = [
    (CourseMaterial.Kind.VIDEO, "Videoer"),
    (CourseMaterial.Kind.SLIDES, "Præsentationer"),
    (CourseMaterial.Kind.PDF, "PDF'er"),
    (CourseMaterial.Kind.LINK, "Links"),
]


def _limits() -> dict:
    return {"video_limit": settings.COURSE_VIDEO_MAX_BYTES, "document_limit": settings.COURSE_DOCUMENT_MAX_BYTES}


def _counted_folders():
    def count(kind):
        return Count("materials", filter=Q(materials__kind=kind))

    return CourseFolder.objects.annotate(
        n_total=Count("materials"),
        n_video=count(CourseMaterial.Kind.VIDEO),
        n_slides=count(CourseMaterial.Kind.SLIDES),
        n_pdf=count(CourseMaterial.Kind.PDF),
        n_link=count(CourseMaterial.Kind.LINK),
    ).order_by(Lower("name"))  # Meta.ordering is dropped in aggregate queries


def _noindex(resp: HttpResponse) -> HttpResponse:
    resp["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def index(request: HttpRequest) -> HttpResponse:
    form = FolderForm()
    if request.method == "POST":
        if not is_editor(request.user):
            raise PermissionDenied
        form = FolderForm(request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.created_by = request.user
            folder.save()
            messages.success(request, f"Mappen ”{folder.name}” er oprettet.")
            return redirect(folder)
    return _noindex(render(
        request,
        "courses/index.html",
        {"folders": _counted_folders(), "form": form, "can_edit": is_editor(request.user)},
    ))


def _folder_context(request, folder, *, form=None, folder_form=None):
    materials = list(folder.materials.select_related("added_by"))
    sections = []
    for kind, heading in SECTIONS:
        items = [m for m in materials if m.kind == kind]
        if items:
            sections.append({"kind": kind, "heading": heading, "items": items})
    return {
        "folder": folder,
        "sections": sections,
        "count": len(materials),
        "folders": CourseFolder.objects.all(),
        "form": form or MaterialForm(),
        "folder_form": folder_form or FolderForm(instance=folder),
        "can_edit": is_editor(request.user),
        **_limits(),
    }


def folder(request: HttpRequest, slug: str) -> HttpResponse:
    obj = get_object_or_404(CourseFolder, slug=slug)
    return _noindex(render(request, "courses/folder.html", _folder_context(request, obj)))


@login_required
@editor_required
@require_POST
def folder_edit(request: HttpRequest, slug: str) -> HttpResponse:
    obj = get_object_or_404(CourseFolder, slug=slug)
    form = FolderForm(request.POST, instance=obj)
    if not form.is_valid():
        return render(request, "courses/folder.html", _folder_context(request, obj, folder_form=form), status=400)
    folder = form.save(commit=False)
    if "name" in form.changed_data:
        folder.slug = CourseFolder.unique_slug(folder.name, exclude_pk=folder.pk)
    folder.save()
    messages.success(request, "Mappen er gemt.")
    return redirect(folder)


@login_required
@editor_required
@require_POST
def folder_delete(request: HttpRequest, slug: str) -> HttpResponse:
    obj = get_object_or_404(CourseFolder, slug=slug)
    name, n = obj.name, obj.materials.count()
    obj.delete()  # the post_delete signal removes each item's file
    messages.success(request, f"Mappen ”{name}” er slettet" + (f" med {n} element{'er' if n != 1 else ''}." if n else "."))
    return redirect("courses:index")


@login_required
@editor_required
@require_POST
def material_add(request: HttpRequest, slug: str) -> HttpResponse:
    obj = get_object_or_404(CourseFolder, slug=slug)
    form = MaterialForm(request.POST, request.FILES)
    if not form.is_valid():
        resp = render(request, "courses/partials/material_form.html", {"folder": obj, "form": form, **_limits()})
        if not request.htmx:
            messages.error(request, "Elementet blev ikke tilføjet. " + " ".join(e for errs in form.errors.values() for e in errs))
            return redirect(obj)
        return resp
    data = form.cleaned_data
    item = CourseMaterial(folder=obj, title=data["title"], description=data["description"], added_by=request.user)
    upload = data.get("file")
    if upload:
        item.kind = TYPES[extension(upload.name)].kind
        item.original_name = upload.name[:255]
        item.size = upload.size
        item.title = item.title or upload.name.rsplit(".", 1)[0][:200]
        item.file.save(upload.name, upload, save=False)
    else:
        item.kind = CourseMaterial.Kind.LINK
        item.url = data["url"]
    item.save()
    messages.success(request, f"”{item.title}” er tilføjet.")
    if request.htmx:
        resp = HttpResponse(status=204)
        resp["HX-Redirect"] = obj.get_absolute_url()
        return resp
    return redirect(obj)


@login_required
@editor_required
@require_POST
def material_edit(request: HttpRequest, key: str) -> HttpResponse:
    item = get_object_or_404(CourseMaterial.objects.select_related("folder"), key=key)
    form = MaterialEditForm(request.POST, instance=item)
    if not form.is_valid():
        messages.error(request, "Ændringen blev ikke gemt. " + " ".join(e for errs in form.errors.values() for e in errs))
        return redirect(item.folder)
    item = form.save()
    messages.success(request, f"”{item.title}” er gemt.")
    return redirect(item.folder)


@login_required
@editor_required
@require_POST
def material_delete(request: HttpRequest, key: str) -> HttpResponse:
    item = get_object_or_404(CourseMaterial.objects.select_related("folder"), key=key)
    folder, title = item.folder, item.title
    item.delete()
    messages.success(request, f"”{title}” er slettet.")
    return redirect(folder)


def material_file(request: HttpRequest, key: str) -> HttpResponse:
    """The stored file. Videos and PDFs open inline (videos with Range
    support, so the player can seek); presentations always download, and
    ``?download=1`` downloads anything."""
    item = get_object_or_404(CourseMaterial, key=key)
    if item.is_link or not item.file:
        raise Http404
    return serve_file(
        request,
        item.file.path,
        content_type=item.content_type,
        filename=item.original_name or item.file.name.rsplit("/", 1)[-1],
        as_attachment=request.GET.get("download") == "1" or not item.opens_in_browser,
    )
