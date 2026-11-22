"""Forms for the CVE section."""

from django import forms
from django.db.models import Q

from django.conf import settings

from .models import CVE, CVEAttachment, CVECase, CVEComment, CVELink, CVETask, normalise_cve_id


class _CaseChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, case) -> str:
        state = "" if case.is_open else f" ({case.get_state_display().lower()})"
        return f"#{case.pk} · {case.title[:70]}{state}"


class CVECreateForm(forms.ModelForm):
    """Register a CVE by hand (or from a prefilled link).

    ``source_url`` is hidden: it is carried over from the query string when
    another tool, such as Harbinger, links to the form.

    ``sag``: every CVE belongs to a sag. Empty (the default) starts a new
    vulnerability sag for it; otherwise it joins the chosen one. Only open
    vulnerability sager are offered: joining a færdigbehandlet sag would close
    the new CVE at once (it takes the sag's state), and hændelser and planlagt
    arbejde hold no CVEs.
    """

    sag = _CaseChoiceField(
        label="Sag",
        queryset=CVECase.objects.none(),
        required=False,
        empty_label="Ny sag med denne CVE",
        help_text="Alle CVE'er hører til en sag, hvor vurdering, løsning og delopgaver samles. "
                  "Vælg en eksisterende sag, hvis samme opdatering lukker den.",
        widget=forms.Select(attrs={"class": "select-field"}),
    )

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
        self.fields["sag"].queryset = CVECase.objects.holding_cves().open().open_first()

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
    """Create or edit a case. ``with_cves=False`` drops the id field (edit).

    Only a vulnerability sag holds CVEs, and only a hændelse has the incident
    fields (Tidspunkt, Alvorlighed, Berørte). The template shows each set for
    its kind only (Alpine, following the Type radio); without JavaScript every
    field shows, so ``clean`` blanks the incident fields on the other kinds
    and refuses CVE ids on a hændelse or planlagt arbejde.
    """

    INCIDENT_FIELDS = ("occurred_at", "severity", "affected")

    occurred_at = forms.DateTimeField(
        label="Tidspunkt", required=False, localize=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(attrs={"class": "input-field", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        help_text=CVECase._meta.get_field("occurred_at").help_text,
    )

    cve_ids = forms.CharField(
        label="CVE'er", required=False, widget=CVE_IDS_WIDGET,
        help_text="Kendte CVE'er flyttes ind i sagen; ukendte oprettes med sagens titel. En CVE kan kun være i én sag. "
                  "Tom er fint: en advarsel uden CVE-nummer bliver en sag uden CVE'er.",
    )

    class Meta:
        model = CVECase
        fields = ["kind", "title", "occurred_at", "severity", "affected", "due_date", "source", "reference",
                  "source_url", "assessment", "solution"]
        widgets = {
            "kind": forms.RadioSelect(),
            "title": forms.TextInput(attrs={"class": "input-field", "maxlength": 200, "autofocus": True}),
            "severity": forms.Select(attrs={"class": "select-field"}),
            "affected": forms.TextInput(attrs={"class": "input-field", "maxlength": 300,
                                               "placeholder": "Fx Rejseplan-skærme på Odense Banegård, alle chauffører"}),
            "due_date": forms.DateInput(format="%Y-%m-%d", attrs={"class": "input-field", "type": "date"}),
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
        else:
            # Hidden ids are not sent when another kind is chosen (case_form.html follows the Type radio).
            self.fields["cve_ids"].widget = forms.Textarea(attrs={
                **CVE_IDS_WIDGET.attrs, "x-bind:disabled": "kind !== 'vulnerability'"})
        # Absent (old clients, the CVE page's "Ny sag") means a vulnerability.
        self.fields["kind"].required = False
        self.fields["severity"].choices = [("", "Ikke angivet")] + list(CVECase.Severity.choices)
        # The assessment's example follows the Type radio (x-bind, see case_form.html).
        self.fields["assessment"].widget.attrs["x-bind:placeholder"] = (
            "kind === 'incident' ? 'Hvad skete der, hvordan opdagede vi det, og hvad er konsekvensen?' "
            ": (kind === 'task' ? 'Hvad skal gøres, og hvorfor?' "
            ": 'Er vi berørt? Hvilke systemer, versioner, hvad er tjekket?')"
        )

    def clean_kind(self) -> str:
        return self.cleaned_data.get("kind") or (self.instance.kind if self.instance.pk else CVECase.Kind.VULNERABILITY)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind != CVECase.Kind.INCIDENT:
            cleaned["occurred_at"], cleaned["severity"], cleaned["affected"] = None, "", ""
        if kind and kind != CVECase.Kind.VULNERABILITY:
            label = CVECase.Kind(kind).label
            if cleaned.get("cve_ids"):
                # A form error, not a field error: the CVE'er field is hidden for this kind.
                self.add_error(None, f"{label} kan ikke have CVE'er. Vælg Sårbarhed, eller fjern CVE'erne.")
            elif self.instance.pk and kind != self.instance.kind and self.instance.cves.exists():
                # Only a change of kind is refused; an older hændelse with CVEs can still be edited.
                self.add_error("kind", f"Sagen har CVE'er og kan ikke blive {label.lower()}. "
                                       "Tag CVE'erne ud af sagen først.")
        return cleaned


class CVECaseAddForm(_CVEIdsMixin, forms.Form):
    cve_ids = forms.CharField(label="Tilføj CVE'er", widget=forms.TextInput(attrs={
        "class": "input-field", "placeholder": "CVE-2026-… (flere adskilt af komma)"}))


class CVETaskEditForm(forms.ModelForm):
    """Edit a delopgave's title, assignee and deadline (1.26.0). Status and
    note keep their own form on the sag page, as they drive the gate."""

    due_date = forms.DateField(
        label="Frist", required=False, localize=False, input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"class": "field", "type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = CVETask
        fields = ["title", "assignee", "due_date"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "field", "maxlength": 200, "style": "width: 100%;"}),
            "assignee": forms.Select(attrs={"class": "field"}),
        }

    def __init__(self, *args, **kwargs):
        from django.contrib.auth import get_user_model

        super().__init__(*args, **kwargs)
        # Active users, plus the current assignee even if since deactivated (else the form could not be saved).
        self.fields["assignee"].queryset = get_user_model().objects.filter(
            Q(is_active=True) | Q(pk=self.instance.assignee_id)).order_by("username")
        self.fields["assignee"].empty_label = "Ingen ansvarlig"
        self.fields["assignee"].label_from_instance = lambda u: u.get_full_name() or u.username
