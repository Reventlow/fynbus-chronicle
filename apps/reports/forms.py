from django import forms

from .models import Report


class ReportUploadForm(forms.ModelForm):
    """Upload a standalone HTML file as a report (editors only)."""

    file = forms.FileField(
        label="HTML-fil",
        help_text="En selvstændig .html-fil med egen CSS og JS. Højst 16 MB.",
    )

    video = forms.FileField(
        label="Video (valgfri)", required=False,
        help_text="MP4 af rapporten, vises under siden med en download-knap. Højst 300 MB.",
    )

    class Meta:
        model = Report
        fields = ["title", "description", "is_public"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input", "placeholder": "Fx Oktober 2026 – et kig et år tilbage"}),
            "description": forms.TextInput(attrs={"class": "input", "placeholder": "Én linje om, hvad rapporten viser"}),
        }

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > 16 * 1024 * 1024:
            raise forms.ValidationError("Filen er større end 16 MB.")
        name = (f.name or "").lower()
        if not (name.endswith(".html") or name.endswith(".htm")):
            raise forms.ValidationError("Kun .html-filer.")
        try:
            self.cleaned_data["html_text"] = f.read().decode("utf-8")
        except UnicodeDecodeError as e:
            raise forms.ValidationError("Filen skal være UTF-8.") from e
        return f

    def clean_video(self):
        v = self.cleaned_data.get("video")
        if not v:
            return v
        if v.size > 300 * 1024 * 1024:
            raise forms.ValidationError("Videoen er større end 300 MB.")
        if not (v.name or "").lower().endswith(".mp4"):
            raise forms.ValidationError("Kun .mp4-videoer.")
        return v
