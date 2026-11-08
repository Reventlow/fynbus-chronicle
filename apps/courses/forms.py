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
    """Add one item: a file uploaded from this computer, a file fetched by
    the server from a link ("Hent fra link"), or a link kept as a link."""

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
    fetch_url = forms.URLField(
        label="Link til filen", max_length=1000, required=False, assume_scheme="https",
        widget=forms.URLInput(attrs={"class": "field", "placeholder": "https://…/kursus.mp4"}),
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
        limit = settings.COURSE_FILE_MAX_BYTES
        if f.size > limit:
            raise forms.ValidationError(f"Filen er større end {filesizeformat(limit)}.")
        if f.size == 0:
            raise forms.ValidationError("Filen er tom.")
        if not content_matches(ext, f):
            raise forms.ValidationError(f"Filen ligner ikke en {ext[1:].upper()}-fil.")
        return f

    def clean_fetch_url(self):
        url = self.cleaned_data.get("fetch_url")
        if url:
            from .fetch import FetchError, check_url

            try:
                check_url(url)
            except FetchError as e:
                raise forms.ValidationError(str(e)) from None
        return url

    def clean(self):
        data = super().clean()
        given = [k for k in ("file", "fetch_url", "url") if data.get(k)]
        if not self.errors:
            if len(given) > 1:
                raise forms.ValidationError("Vælg én ting: en fil, et link til en fil eller et link, ikke flere.")
            if not given:
                raise forms.ValidationError("Vælg en fil eller skriv et link.")
            if given == ["url"] and not data.get("title"):
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
