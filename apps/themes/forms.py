"""Forms for the themes management page."""

from django import forms

from .models import ThemeSchedule


class ThemeScheduleForm(forms.ModelForm):
    """Add or edit a date range during which a theme overrides user pref."""

    class Meta:
        model = ThemeSchedule
        fields = ["start_date", "end_date", "recurs_annually", "label"]
        widgets = {
            "start_date": forms.DateInput(
                attrs={"type": "date", "class": "input-field"}
            ),
            "end_date": forms.DateInput(
                attrs={"type": "date", "class": "input-field"}
            ),
            "label": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "fx 'Star Wars Day' eller 'Julestemning uge 51-52'",
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        recurring = cleaned.get("recurs_annually")
        if not start or not end:
            return cleaned
        if recurring:
            # For annual schedules, only month/day matter; allow ranges that
            # wrap a year boundary (Dec 27 → Jan 3) without raising here.
            return cleaned
        if end < start:
            raise forms.ValidationError("Slut-datoen skal være efter start-datoen.")
        return cleaned
