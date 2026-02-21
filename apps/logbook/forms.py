"""
Django forms for the logbook application.

Provides form classes for WeekLog, PriorityItem, Absence, and Incident
models with custom widgets styled for the Scandinavian theme.
"""

from django import forms
from django.utils import timezone

from .models import Absence, Incident, PriorityItem, WeekLog


class WeekLogForm(forms.ModelForm):
    """Form for creating and editing week logs."""

    class Meta:
        model = WeekLog
        fields = [
            "year",
            "week_number",
            "helpdesk_new",
            "helpdesk_closed",
            "helpdesk_open",
            "summary",
        ]
        widgets = {
            "year": forms.NumberInput(
                attrs={
                    "class": "input-field",
                    "min": 2024,
                    "max": 2100,
                }
            ),
            "week_number": forms.NumberInput(
                attrs={
                    "class": "input-field",
                    "min": 1,
                    "max": 53,
                }
            ),
            "helpdesk_new": forms.NumberInput(
                attrs={
                    "class": "input-field",
                    "min": 0,
                }
            ),
            "helpdesk_closed": forms.NumberInput(
                attrs={
                    "class": "input-field",
                    "min": 0,
                }
            ),
            "helpdesk_open": forms.NumberInput(
                attrs={
                    "class": "input-field",
                    "min": 0,
                }
            ),
            "summary": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 4,
                    "placeholder": "Beskriv ugens vigtigste aktiviteter...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        """Set default values for year and week."""
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            now = timezone.now()
            iso_cal = now.isocalendar()
            self.fields["year"].initial = iso_cal.year
            self.fields["week_number"].initial = iso_cal.week


class PriorityItemForm(forms.ModelForm):
    """Form for creating and editing priority items."""

    class Meta:
        model = PriorityItem
        fields = ["title", "priority", "status", "description", "notes"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Opgavens titel",
                }
            ),
            "priority": forms.Select(
                attrs={
                    "class": "select-field",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "select-field",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 3,
                    "placeholder": "Beskrivelse af opgaven...",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 2,
                    "placeholder": "Eventuelle noter...",
                }
            ),
        }


class AbsenceForm(forms.ModelForm):
    """Form for creating and editing absences."""

    class Meta:
        model = Absence
        fields = ["staff_name", "absence_type", "start_date", "end_date", "notes"]
        widgets = {
            "staff_name": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Medarbejderens navn",
                }
            ),
            "absence_type": forms.Select(
                attrs={
                    "class": "select-field",
                }
            ),
            "start_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "input-field",
                    "type": "date",
                }
            ),
            "end_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "input-field",
                    "type": "date",
                }
            ),
            "notes": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Eventuelle noter",
                }
            ),
        }

    def clean(self):
        """Validate that end date is not before start date."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError(
                "Slutdato kan ikke være før startdato.",
                code="invalid_date_range",
            )

        return cleaned_data


class MeetingMinutesForm(forms.ModelForm):
    """Form for editing meeting attendees and minutes inline."""

    class Meta:
        model = WeekLog
        fields = [
            "meeting_skipped",
            "meeting_skipped_reason",
            "meeting_attendees",
            "meeting_minutes",
        ]
        widgets = {
            "meeting_skipped": forms.HiddenInput(),
            "meeting_skipped_reason": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "F.eks. helligdag, ferie, ingen agenda...",
                }
            ),
            "meeting_attendees": forms.HiddenInput(),
            "meeting_minutes": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 6,
                    "placeholder": "Referat af mandagsmødet...",
                    "x-ref": "minutesTextarea",
                    "@input": "minutesText = $event.target.value",
                }
            ),
        }


class IncidentForm(forms.ModelForm):
    """Form for creating and editing incidents."""

    class Meta:
        model = Incident
        fields = [
            "title",
            "incident_type",
            "severity",
            "description",
            "occurred_at",
            "resolved",
            "resolution",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Hændelsens titel",
                }
            ),
            "incident_type": forms.Select(
                attrs={
                    "class": "select-field",
                }
            ),
            "severity": forms.Select(
                attrs={
                    "class": "select-field",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 4,
                    "placeholder": "Beskriv hændelsen...",
                }
            ),
            "occurred_at": forms.DateTimeInput(
                attrs={
                    "class": "input-field",
                    "type": "datetime-local",
                }
            ),
            "resolved": forms.CheckboxInput(
                attrs={
                    "class": "checkbox-field",
                }
            ),
            "resolution": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 3,
                    "placeholder": "Beskriv løsningen...",
                }
            ),
        }
