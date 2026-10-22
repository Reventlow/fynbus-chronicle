"""Forms for the CVE section."""

from django import forms

from django.conf import settings

from .models import CVE, CVEAttachment, CVEComment, CVELink, normalise_cve_id


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


class CVEAttachmentForm(forms.ModelForm):
    """Upload one PDF (e.g. an FE-CSIRT advisory) with title, source and TLP."""

    class Meta:
        model = CVEAttachment
        fields = ["file", "title", "source", "tlp"]
        widgets = {
            "file": forms.ClearableFileInput(attrs={"class": "input-field", "accept": "application/pdf,.pdf"}),
            "title": forms.TextInput(attrs={"class": "input-field", "placeholder": "Titel (valgfri, ellers filnavnet)"}),
            "source": forms.TextInput(attrs={"class": "input-field", "placeholder": "Kilde, fx FE-CSIRT"}),
            "tlp": forms.Select(attrs={"class": "input-field"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tlp"].choices = [("", "TLP: ikke angivet")] + list(CVEAttachment.TLP.choices)

    def clean_file(self):
        upload = self.cleaned_data.get("file")
        if not upload:
            raise forms.ValidationError("Vælg en PDF-fil.")
        if not upload.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Kun PDF-filer kan vedhæftes.")
        limit = settings.CVE_ATTACHMENT_MAX_BYTES
        if upload.size > limit:
            raise forms.ValidationError(f"Filen er for stor (maks. {limit // (1024 * 1024)} MB).")
        head = upload.read(5)
        upload.seek(0)
        if head != b"%PDF-":  # the extension alone proves nothing
            raise forms.ValidationError("Filen er ikke en gyldig PDF.")
        return upload
