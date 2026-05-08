"""Forms for the themes management page."""

from django import forms

from .models import ThemeSchedule


class ThemeScheduleForm(forms.ModelForm):
    """Add or edit a date range during which a theme overrides user pref."""

    class Meta:
        model = ThemeSchedule
        fields = ["start_date", "end_date", "label"]
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
                    "placeholder": "fx 'Star Wars Day 2027' eller 'Julestemning uge 51-52'",
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("Slut-datoen skal være efter start-datoen.")
        return cleaned
