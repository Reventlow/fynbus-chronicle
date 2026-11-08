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
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Lower
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import editor_required, is_editor
from chronicle.http import serve_file

from . import convert, fetch
from .filetypes import TYPES, extension
from .forms import FolderForm, MaterialEditForm, MaterialForm
from .models import CourseFolder, CourseImport, CourseLink, CourseMaterial

# (kind, heading) in the order the folder page lists them.
SECTIONS = [
    (CourseMaterial.Kind.VIDEO, "Videoer"),
    (CourseMaterial.Kind.SLIDES, "Præsentationer"),
    (CourseMaterial.Kind.PDF, "PDF'er"),
    (CourseMaterial.Kind.LINK, "Links"),
]


def _limits() -> dict:
    return {"file_limit": settings.COURSE_FILE_MAX_BYTES}


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


def _imports_context(folder) -> dict:
    rows = list(folder.imports.all()) if folder else []
    return {"imports": rows, "import_watch": ",".join(str(i.pk) for i in rows if not i.is_failed)}


_LINK_WORK = ("priority_item", "case")


def _folder_context(request, folder, *, form=None, folder_form=None):
    signed_in = request.user.is_authenticated
    qs = folder.materials.select_related("added_by", "folder")
    if signed_in:
        qs = qs.prefetch_related(Prefetch("links", queryset=CourseLink.objects.select_related(*_LINK_WORK)))
    materials = list(qs)
    sections = []
    for kind, heading in SECTIONS:
        items = [m for m in materials if m.kind == kind]
        if items:
            sections.append({"kind": kind, "heading": heading, "items": items})
    return {
        "folder": folder,
        **_imports_context(folder if is_editor(request.user) else None),
        "sections": sections,
        "count": len(materials),
        "folder_links": list(folder.links.select_related(*_LINK_WORK)) if signed_in else [],
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
    if data.get("fetch_url"):
        imp = CourseImport.objects.create(
            folder=obj, url=data["fetch_url"], title=data["title"], description=data["description"], created_by=request.user,
        )
        fetch.start(imp)
        messages.info(request, "Filen hentes i baggrunden og dukker op i mappen, når den er hentet.")
        if request.htmx:
            resp = HttpResponse(status=204)
            resp["HX-Redirect"] = obj.get_absolute_url()
            return resp
        return redirect(obj)
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
    if item.kind == CourseMaterial.Kind.SLIDES:
        # Synchronous: a typical deck converts in a few seconds, and the
        # upload request already holds the worker. A failure keeps the item
        # (it can still be downloaded) and is shown with a retry button.
        convert.make_preview(item)
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


# (kind order) for the player's playlist: videos, then slides, then PDFs.
_PLAY_ORDER = {CourseMaterial.Kind.VIDEO: 0, CourseMaterial.Kind.SLIDES: 1, CourseMaterial.Kind.PDF: 2}


def player(request: HttpRequest, slug: str, key: str) -> HttpResponse:
    """One video, presentation or PDF, large, with the folder's other items
    as a playlist beside it. Videos get speed control and resume where the
    viewer left off; presentations and PDFs are shown slide by slide."""
    obj = get_object_or_404(CourseFolder, slug=slug)
    item = get_object_or_404(CourseMaterial.objects.select_related("added_by"), folder=obj, key=key)
    if item.is_link:
        return redirect(item.url)
    playlist = sorted(
        (m for m in obj.materials.select_related("folder") if not m.is_link),
        key=lambda m: (_PLAY_ORDER[m.kind], m.added_at, m.pk),
    )
    index = next(i for i, m in enumerate(playlist) if m.pk == item.pk)
    return _noindex(render(request, "courses/player.html", {
        "folder": obj,
        "item": item,
        "playlist": playlist,
        "position": index + 1,
        "previous": playlist[index - 1] if index > 0 else None,
        "next": playlist[index + 1] if index + 1 < len(playlist) else None,
        "can_edit": is_editor(request.user),
    }))


def material_preview(request: HttpRequest, key: str) -> HttpResponse:
    """The PDF rendition of a presentation, for the slide viewer."""
    item = get_object_or_404(CourseMaterial, key=key, kind=CourseMaterial.Kind.SLIDES)
    if not item.preview:
        raise Http404
    stem = (item.original_name or "slides").rsplit(".", 1)[0]
    return serve_file(request, item.preview.path, content_type="application/pdf", filename=f"{stem}.pdf")


@login_required
@editor_required
@require_POST
def material_convert(request: HttpRequest, key: str) -> HttpResponse:
    """Try the PDF conversion of a presentation again."""
    item = get_object_or_404(CourseMaterial.objects.select_related("folder"), key=key, kind=CourseMaterial.Kind.SLIDES)
    error = convert.make_preview(item)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, f"”{item.title}” kan nu vises.")
    return redirect(item.get_player_url())


@login_required
@editor_required
def imports(request: HttpRequest, slug: str) -> HttpResponse:
    """The "Hentes fra link" card, polled while a fetch runs. When a fetch
    the page was watching has finished, the whole page reloads so the new
    item shows in its section."""
    obj = get_object_or_404(CourseFolder, slug=slug)
    rows = list(obj.imports.all())
    watched = {int(k) for k in request.GET.get("watch", "").split(",") if k.isdigit()}
    still_running = {i.pk for i in rows if not i.is_failed}
    if watched - still_running:
        resp = HttpResponse(status=204)
        resp["HX-Refresh"] = "true"
        return resp
    return render(request, "courses/partials/imports.html", {"folder": obj, **_imports_context(obj)})


@login_required
@editor_required
@require_POST
def import_retry(request: HttpRequest, pk: int) -> HttpResponse:
    imp = get_object_or_404(CourseImport.objects.select_related("folder"), pk=pk)
    CourseImport.objects.filter(pk=imp.pk).update(status=CourseImport.Status.PENDING, error="", updated_at=timezone.now())
    fetch.start(imp)
    return redirect(imp.folder)


@login_required
@editor_required
@require_POST
def import_delete(request: HttpRequest, pk: int) -> HttpResponse:
    imp = get_object_or_404(CourseImport.objects.select_related("folder"), pk=pk)
    folder = imp.folder
    imp.delete()
    return redirect(folder)


# --- links to priorities and cases ------------------------------------------------


def _link_targets() -> dict:
    """What a course item can be tied to. Unlike ServiceDesk links, finished
    work counts: a course is often linked after the fact ("Deltog i …").
    Open priorities and cases first, then the most recently finished ones."""
    from apps.cves.models import CVE, CVECase
    from apps.logbook.models import PriorityItem

    live = PriorityItem.objects.active()
    return {
        "priorities": live.exclude(status=PriorityItem.Status.COMPLETED).order_by("title")[:300],
        "done_priorities": live.filter(status=PriorityItem.Status.COMPLETED).order_by("-last_active_at")[:200],
        "cases": CVECase.objects.open().order_by("-updated_at")[:300],
        "done_cases": CVECase.objects.filter(state=CVE.State.SOLVED).order_by("-solved_at")[:200],
    }


def _course_side(slug: str | None, key: str | None) -> dict:
    if key:
        return {"material": get_object_or_404(CourseMaterial.objects.select_related("folder"), key=key)}
    return {"folder": get_object_or_404(CourseFolder, slug=slug)}


def _back(side: dict) -> str:
    folder = side["material"].folder if "material" in side else side["folder"]
    anchor = f"#m-{side['material'].key}" if "material" in side else ""
    return folder.get_absolute_url() + anchor


@login_required
@editor_required
def link(request: HttpRequest, slug: str | None = None, key: str | None = None) -> HttpResponse:
    """GET: the picker (loaded into the row). POST ``target=p<pk>|c<pk>``: tie
    the folder or item to that priority or case."""
    from apps.cves.models import CVECase
    from apps.logbook.models import PriorityItem

    side = _course_side(slug, key)
    if request.method != "POST":
        return render(request, "courses/partials/link_form.html", {
            **side, **_link_targets(), "action": request.path,
        })
    target = request.POST.get("target", "")
    work = {}
    if target[:1] == "p" and target[1:].isdigit():
        work["priority_item"] = get_object_or_404(PriorityItem, pk=int(target[1:]))
    elif target[:1] == "c" and target[1:].isdigit():
        work["case"] = get_object_or_404(CVECase, pk=int(target[1:]))
    else:
        messages.error(request, "Vælg en prioriteret opgave eller en sag.")
        return redirect(_back(side))
    obj, created = CourseLink.objects.get_or_create(**side, **work, defaults={"created_by": request.user})
    if created:
        messages.success(request, f"Knyttet til {obj.work_label}.")
    else:
        messages.info(request, "Det er allerede knyttet.")
    return redirect(_back(side))


@login_required
@editor_required
@require_POST
def unlink(request: HttpRequest, pk: int) -> HttpResponse:
    obj = get_object_or_404(CourseLink.objects.select_related("folder", "material__folder"), pk=pk)
    side = {"material": obj.material} if obj.material_id else {"folder": obj.folder}
    obj.delete()
    messages.success(request, "Linket er fjernet.")
    nxt = request.POST.get("next", "")
    if nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect(_back(side))
