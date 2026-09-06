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
            "helpdesk_open_0_7",
            "helpdesk_open_8_14",
            "helpdesk_open_15_30",
            "helpdesk_open_31_90",
            "helpdesk_open_91_180",
            "helpdesk_open_181_365",
            "helpdesk_open_over_365",
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
            "helpdesk_open_0_7": forms.NumberInput(
                attrs={"class": "input-field", "min": 0}
            ),
            "helpdesk_open_8_14": forms.NumberInput(
                attrs={"class": "input-field", "min": 0}
            ),
            "helpdesk_open_15_30": forms.NumberInput(
                attrs={"class": "input-field", "min": 0}
            ),
            "helpdesk_open_31_90": forms.NumberInput(
                attrs={"class": "input-field", "min": 0}
            ),
            "helpdesk_open_91_180": forms.NumberInput(
                attrs={"class": "input-field", "min": 0}
            ),
            "helpdesk_open_181_365": forms.NumberInput(
                attrs={"class": "input-field", "min": 0}
            ),
            "helpdesk_open_over_365": forms.NumberInput(
                attrs={"class": "input-field", "min": 0}
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

    def clean(self):
        """Keep the age breakdown consistent with the open-ticket total.

        The breakdown is optional (leave every bucket at 0 and the report
        simply omits the section), but a partially filled breakdown that
        does not add up to "Åbne sager" would be misleading, so it is
        rejected.
        """
        cleaned = super().clean()
        bucket_fields = [field for field, *_ in WeekLog.HELPDESK_AGE_BUCKETS]
        buckets = {field: cleaned.get(field) or 0 for field in bucket_fields}
        total = sum(buckets.values())

        if total and total != (cleaned.get("helpdesk_open") or 0):
            self.add_error(
                None,
                f"Liggetid-opdelingen summer til {total}, "
                f"men der er registreret {cleaned.get('helpdesk_open') or 0} åbne sager. "
                "Ret tallene, så de stemmer (eller lad alle liggetid-felter stå på 0).",
            )

        return cleaned


class PriorityItemForm(forms.ModelForm):
    """Form for the long-lived priority task itself.

    The per-week description lives on PriorityItemAppearance and is
    edited via PriorityItemAppearanceForm, but for convenience this
    form *also* accepts a ``description`` text and the view that
    instantiates it is responsible for routing that string into the
    matching appearance.
    """

    description = forms.CharField(
        label="Beskrivelse (denne uge)",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "textarea-field",
                # Roomy on purpose: this is the only field on the task now,
                # and it holds Markdown — steps, code blocks, tables.
                "rows": 8,
                "placeholder": "Hvad skete der med opgaven i denne uge?",
            }
        ),
        help_text="Bliver gemt på ugens visning af opgaven, så du kan se historikken senere.",
    )

    class Meta:
        model = PriorityItem
        # `notes` is deliberately absent: the team writes everything in the
        # per-week description instead, so the field is no longer editable
        # from the UI. It stays on the model — 23 older tasks still carry
        # notes, and those keep rendering wherever they are shown.
        fields = ["title", "priority", "status"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "input-field", "placeholder": "Opgavens titel"}
            ),
            "priority": forms.Select(attrs={"class": "select-field"}),
            "status": forms.Select(attrs={"class": "select-field"}),
        }


class PriorityItemAppearanceForm(forms.ModelForm):
    """Edit only the per-week description (and optionally re-order)."""

    class Meta:
        from .models import PriorityItemAppearance

        model = PriorityItemAppearance
        fields = ["description"]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 8,
                    "placeholder": "Hvad skete der med opgaven i denne uge?",
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

    occurred_at = forms.DateTimeField(
        label="Tidspunkt",
        widget=forms.DateTimeInput(
            attrs={
                "class": "input-field",
                "type": "datetime-local",
            },
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        localize=False,
    )

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
