"""Forms for the CVE section."""

from django import forms

from django.conf import settings

from .models import CVE, CVEAttachment, CVECase, CVEComment, CVELink, normalise_cve_id


class CVECreateForm(forms.ModelForm):
    """Register a CVE by hand (or from a prefilled link).

    ``source_url`` is hidden: it is carried over from the query string when
    another tool, such as Harbinger, links to the form.
    """

    comment = forms.CharField(
        label="Første kommentar",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "textarea-field",
                "rows": 4,
                "placeholder": "Valgfrit — hvad ved vi, hvem er berørt? Markdown virker.",
            }
        ),
    )

    class Meta:
        model = CVE
        fields = ["cve_id", "subject", "cvss", "severity", "cvefeed_url", "source_url"]
        widgets = {
            "cve_id": forms.TextInput(
                attrs={"class": "input-field", "placeholder": "CVE-2026-109618", "autofocus": True}
            ),
            "subject": forms.TextInput(attrs={"class": "input-field", "maxlength": 300}),
            "cvss": forms.NumberInput(
                attrs={"class": "input-field", "step": "0.1", "min": "0", "max": "10"}
            ),
            "severity": forms.Select(attrs={"class": "select-field"}),
            "cvefeed_url": forms.URLInput(
                attrs={"class": "input-field", "placeholder": "Udfyldes automatisk"}
            ),
            "source_url": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["severity"].required = False
        self.fields["severity"].choices = [("", "Udled af CVSS")] + list(CVE.Severity.choices)

    def clean_cve_id(self) -> str:
        return normalise_cve_id(self.cleaned_data.get("cve_id", ""))

    def clean_cvss(self):
        cvss = self.cleaned_data.get("cvss")
        if cvss is not None and not (0 <= cvss <= 10):
            raise forms.ValidationError("CVSS skal ligge mellem 0,0 og 10,0.")
        return cvss


class CVEEditForm(forms.ModelForm):
    """Edit the descriptive fields; the id and state are not edited here."""

    class Meta:
        model = CVE
        fields = ["subject", "cvss", "severity", "cvefeed_url"]
        widgets = CVECreateForm.Meta.widgets

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["severity"].required = False
        self.fields["severity"].choices = [("", "Udled af CVSS")] + list(CVE.Severity.choices)
        self.fields["severity"].help_text = "Lad stå tom for at udlede den af CVSS."

    clean_cvss = CVECreateForm.clean_cvss


class CVELinkForm(forms.ModelForm):
    class Meta:
        model = CVELink
        fields = ["url", "label"]
        widgets = {
            "url": forms.URLInput(attrs={"class": "input-field", "placeholder": "https://…"}),
            "label": forms.TextInput(
                attrs={"class": "input-field", "placeholder": "Beskrivelse (valgfri)"}
            ),
        }


class CVECommentForm(forms.ModelForm):
    class Meta:
        model = CVEComment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 3,
                    "placeholder": "Skriv en kommentar — Markdown virker.",
                }
            ),
        }


ODT_MIMETYPE = b"application/vnd.oasis.opendocument.text"


def _is_odt(upload) -> bool:
    """True if ``upload`` is an OpenDocument text: a zip whose ``mimetype``
    member says so (the ODF spec puts it first, uncompressed). Only that one
    small member is read, so a zip bomb is never unpacked."""
    import zipfile

    try:
        with zipfile.ZipFile(upload) as archive:
            info = archive.getinfo("mimetype")
            if info.file_size > 100:
                return False
            return archive.read(info).strip() == ODT_MIMETYPE
    except (zipfile.BadZipFile, KeyError, OSError, RuntimeError, NotImplementedError):
        return False
    finally:
        upload.seek(0)


class CVEAttachmentForm(forms.ModelForm):
    """Upload one PDF, ODT document or Outlook mail (.msg), with title, source and TLP.

    After ``is_valid()``, ``kind`` is "pdf", "odt" or "msg" and, for a mail,
    ``msg_info`` holds what was read from it (see apps.cves.msg).
    """

    class Meta:
        model = CVEAttachment
        fields = ["file", "title", "source", "tlp"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"class": "input-field", "accept": "application/pdf,.pdf,.odt,application/vnd.oasis.opendocument.text,.msg,application/vnd.ms-outlook"}),
            "title": forms.TextInput(attrs={"class": "input-field", "placeholder": "Titel (valgfri)"}),
            "source": forms.TextInput(attrs={"class": "input-field", "placeholder": "Kilde, fx FE-CSIRT"}),
            "tlp": forms.Select(attrs={"class": "input-field"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tlp"].choices = [("", "TLP: ikke angivet")] + list(CVEAttachment.TLP.choices)
        self.kind = CVEAttachment.Kind.PDF
        self.msg_info = None

    def clean_file(self):
        from . import msg as msg_reader

        upload = self.cleaned_data.get("file")
        if not upload:
            raise forms.ValidationError("Vælg en PDF, et ODT-dokument eller en Outlook-mail (.msg).")
        name = upload.name.lower()
        if not name.endswith((".pdf", ".odt", ".msg")):
            raise forms.ValidationError("Kun PDF-filer, ODT-dokumenter (.odt) og Outlook-mails (.msg) kan vedhæftes.")
        limit = settings.CVE_ATTACHMENT_MAX_BYTES
        if upload.size > limit:
            raise forms.ValidationError(f"Filen er for stor (maks. {limit // (1024 * 1024)} MB).")
        head = upload.read(8)
        upload.seek(0)
        if name.endswith(".pdf"):
            if head[:5] != b"%PDF-":  # the extension alone proves nothing
                raise forms.ValidationError("Filen er ikke en gyldig PDF.")
            self.kind = CVEAttachment.Kind.PDF
            return upload
        if name.endswith(".odt"):
            if not _is_odt(upload):
                raise forms.ValidationError("Filen er ikke et gyldigt ODT-dokument.")
            self.kind = CVEAttachment.Kind.ODT
            return upload
        try:
            self.msg_info = msg_reader.parse(upload)
        except msg_reader.MsgError:
            raise forms.ValidationError("Filen er ikke en Outlook-mail (.msg), der kan læses.") from None
        finally:
            upload.seek(0)
        self.kind = CVEAttachment.Kind.MSG
        return upload


def _parse_cve_ids(raw: str) -> list[str]:
    """Normalised, de-duplicated CVE ids from free text (spaces, commas,
    semicolons or newlines). Raises ValidationError naming bad tokens."""
    import re

    ids, bad = [], []
    for token in re.split(r"[\s,;]+", raw or ""):
        if not token:
            continue
        try:
            cve_id = normalise_cve_id(token)
        except forms.ValidationError:
            bad.append(token)
            continue
        if cve_id not in ids:
            ids.append(cve_id)
    if bad:
        raise forms.ValidationError("Ikke gyldige CVE-id'er: " + ", ".join(bad[:10]))
    return ids


class _CVEIdsMixin:
    """Validates ``cve_ids`` and exposes the existing CVEs as ``cleaned_data['cves']``.

    Unknown ids are allowed (the view creates them with the case title).
    """

    def clean_cve_ids(self) -> str:
        ids = _parse_cve_ids(self.cleaned_data.get("cve_ids", ""))
        self.cleaned_data["cves"] = list(CVE.objects.filter(cve_id__in=ids))
        return ",".join(ids)


CVE_IDS_WIDGET = forms.Textarea(attrs={
    "class": "textarea-field", "rows": 3,
    "placeholder": "CVE-2026-115557, CVE-2026-111943 — ét eller flere, adskilt af komma eller linjeskift",
})


class CVECaseForm(_CVEIdsMixin, forms.ModelForm):
    """Create or edit a case. ``with_cves=False`` drops the id field (edit)."""

    cve_ids = forms.CharField(
        label="CVE'er", required=False, widget=CVE_IDS_WIDGET,
        help_text="Kendte CVE'er flyttes ind i sagen; ukendte oprettes med sagens titel. En CVE kan kun være i én sag. "
                  "Tom er fint: en advarsel uden CVE-nummer bliver en sag uden CVE'er.",
    )

    class Meta:
        model = CVECase
        fields = ["title", "source", "reference", "source_url", "assessment", "solution"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input-field", "maxlength": 200, "autofocus": True}),
            "source": forms.TextInput(attrs={"class": "input-field", "maxlength": 40, "list": "case-sources",
                                             "placeholder": "CFCS"}),
            "reference": forms.TextInput(attrs={"class": "input-field", "maxlength": 100,
                                                "placeholder": "Fx CFCS-advarsel 2026-10-24"}),
            "source_url": forms.URLInput(attrs={"class": "input-field", "placeholder": "https://"}),
            "assessment": forms.Textarea(attrs={"class": "textarea-field", "rows": 5,
                                                "placeholder": "Er vi berørt? Hvilke systemer, versioner, hvad er tjekket?"}),
            "solution": forms.Textarea(attrs={"class": "textarea-field", "rows": 5,
                                              "placeholder": "Hvad er gjort eller skal gøres — opdatering, konfiguration, ansvarlig."}),
        }

    def __init__(self, *args, with_cves: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        if not with_cves:
            del self.fields["cve_ids"]


class CVECaseAddForm(_CVEIdsMixin, forms.Form):
    cve_ids = forms.CharField(label="Tilføj CVE'er", widget=forms.TextInput(attrs={
        "class": "input-field", "placeholder": "CVE-2026-… (flere adskilt af komma)"}))
