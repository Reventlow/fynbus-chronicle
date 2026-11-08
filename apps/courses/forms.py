"""Forms for course folders and material (editors only)."""

from django import forms
from django.conf import settings
from django.template.defaultfilters import filesizeformat

from .filetypes import ACCEPT, TYPES, content_matches, extension
from .models import CourseFolder, CourseMaterial


class FolderForm(forms.ModelForm):
    class Meta:
        model = CourseFolder
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "field", "placeholder": "Fx Anthropic", "autocomplete": "off"}),
            "description": forms.TextInput(attrs={"class": "field", "placeholder": "Fx Claude-kurser og -guides"}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Giv mappen et navn.")
        return name


class MaterialForm(forms.Form):
    """Add one item: either a file (video, presentation, PDF) or a link."""

    title = forms.CharField(
        label="Titel", max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "field", "placeholder": "Tom = filnavnet"}),
    )
    description = forms.CharField(
        label="Beskrivelse", max_length=500, required=False,
        widget=forms.TextInput(attrs={"class": "field", "placeholder": "Valgfri, fx modul 2 af 5"}),
    )
    file = forms.FileField(
        label="Fil", required=False,
        widget=forms.ClearableFileInput(attrs={"class": "field", "accept": ACCEPT}),
    )
    url = forms.URLField(
        label="Link", max_length=1000, required=False, assume_scheme="https",
        widget=forms.URLInput(attrs={"class": "field", "placeholder": "https://…"}),
    )

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if not f:
            return f
        ext = extension(f.name)
        ft = TYPES.get(ext)
        if ft is None:
            raise forms.ValidationError(
                "Filtypen kan ikke lægges op. Brug video (MP4, MOV, M4V, WebM), PowerPoint (PPTX, PPT, PPSX, ODP) eller PDF."
            )
        limit = settings.COURSE_VIDEO_MAX_BYTES if ft.kind == "video" else settings.COURSE_DOCUMENT_MAX_BYTES
        if f.size > limit:
            raise forms.ValidationError(f"Filen er større end {filesizeformat(limit)}.")
        if f.size == 0:
            raise forms.ValidationError("Filen er tom.")
        if not content_matches(ext, f):
            raise forms.ValidationError(f"Filen ligner ikke en {ext[1:].upper()}-fil.")
        return f

    def clean(self):
        data = super().clean()
        has_file, has_url = bool(data.get("file")), bool(data.get("url"))
        if not self.errors:
            if has_file and has_url:
                raise forms.ValidationError("Vælg enten en fil eller et link, ikke begge.")
            if not has_file and not has_url:
                raise forms.ValidationError("Vælg en fil eller skriv et link.")
            if has_url and not data.get("title"):
                self.add_error("title", "Giv linket en titel.")
        return data


class MaterialEditForm(forms.ModelForm):
    url = forms.URLField(
        label="Link", max_length=1000, required=False, assume_scheme="https",
        widget=forms.URLInput(attrs={"class": "field"}),
    )

    class Meta:
        model = CourseMaterial
        # "url" is declared above, not listed here: a model URLField would
        # build a form field with Django 5's deprecated http default.
        fields = ["title", "description", "folder"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "field"}),
            "description": forms.TextInput(attrs={"class": "field"}),
            "folder": forms.Select(attrs={"class": "field"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folder"].empty_label = None
        if self.instance.is_link:
            self.fields["url"].required = True
            self.initial["url"] = self.instance.url
        else:
            del self.fields["url"]

    def save(self, commit=True):
        if "url" in self.fields:
            self.instance.url = self.cleaned_data["url"]
        return super().save(commit)
