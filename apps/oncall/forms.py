"""Forms for the on-call duty application."""

from datetime import datetime, time, timedelta

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from .models import week_span


class UserChoiceField(forms.ModelChoiceField):
    """User dropdown labelled with the site-wide display name convention."""

    def label_from_instance(self, user: User) -> str:
        return user.get_full_name() or user.username


class OnCallAssignForm(forms.Form):
    """Assign/switch the on-call person for one week (FR #5).

    Monday at 00:00 means the whole week; a later date (and optional
    time) performs a mid-week handover, splitting the coverage. Picking
    "— Ledig —" frees the week from the chosen moment.
    """

    user = UserChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("first_name", "username"),
        required=False,
        label="Medarbejder",
        empty_label="— Ledig —",
        widget=forms.Select(attrs={"class": "select-field"}),
    )
    effective_date = forms.DateField(
        label="Fra dato",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "input-field"}),
    )
    effective_time = forms.TimeField(
        label="Fra kl.",
        required=False,
        input_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "input-field"}),
    )
    notes = forms.CharField(
        label="Noter",
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "input-field", "placeholder": "Valgfri note"}),
    )

    def __init__(self, year: int, week: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.year = year
        self.week = week
        self.week_start, self.week_end = week_span(year, week)
        monday = self.week_start.date()
        sunday = monday + timedelta(days=6)
        self.fields["effective_date"].widget.attrs.update(
            {"min": monday.isoformat(), "max": sunday.isoformat()}
        )

    def clean(self):
        cleaned = super().clean()
        effective_date = cleaned.get("effective_date")
        if effective_date is None:
            return cleaned
        effective_time = cleaned.get("effective_time") or time.min
        effective_at = timezone.make_aware(
            datetime.combine(effective_date, effective_time),
            timezone.get_default_timezone(),
        )
        if not (self.week_start <= effective_at < self.week_end):
            raise forms.ValidationError(
                "Datoen skal ligge inden for ugen (mandag til søndag).",
                code="outside_week",
            )
        cleaned["effective_at"] = effective_at
        return cleaned
