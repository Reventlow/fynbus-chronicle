"""
Django forms for the tasks application.

Provides form classes for Task, TaskNote, TaskNoteAttachment,
and TaskStatus with custom widgets styled for the Scandinavian theme.
"""

import os

from django import forms
from django.contrib.auth.models import User

from .models import Task, TaskNote, TaskNoteAttachment


APPROVER_CHOICES = [
    ("Anna Lise", "Anna Lise"),
    ("Dennis", "Dennis"),
    ("Morten", "Morten"),
    ("Peter", "Peter"),
    ("Gorm", "Gorm"),
]


class TaskForm(forms.ModelForm):
    """Form for creating and editing tasks."""

    approvers = forms.MultipleChoiceField(
        label="Godkendere",
        choices=APPROVER_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "checkbox-field"}
        ),
    )

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "status",
            "planned_start",
            "planned_end",
            "approvers",
            "assigned_to",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Opgavens titel",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 4,
                    "placeholder": "Beskrivelse af opgaven...",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "select-field",
                }
            ),
            "planned_start": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "input-field",
                    "type": "date",
                }
            ),
            "planned_end": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "input-field",
                    "type": "date",
                }
            ),
            "assigned_to": forms.CheckboxSelectMultiple(
                attrs={
                    "class": "checkbox-field",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        """Set queryset for assigned_to and load approvers from CSV."""
        super().__init__(*args, **kwargs)
        active_users = User.objects.filter(is_active=True).order_by("first_name")
        self.fields["assigned_to"].queryset = active_users
        # Load comma-separated approvers string into multi-select initial value
        if self.instance and self.instance.pk and self.instance.approvers:
            self.initial["approvers"] = [
                name.strip() for name in self.instance.approvers.split(",") if name.strip()
            ]

    def clean_approvers(self):
        """Convert selected list back to comma-separated string."""
        selected = self.cleaned_data.get("approvers", [])
        return ", ".join(selected)


class TaskNoteForm(forms.ModelForm):
    """Form for creating and editing task notes."""

    class Meta:
        model = TaskNote
        fields = ["subject", "text"]
        widgets = {
            "subject": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Emne for noten",
                }
            ),
            "text": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 6,
                    "placeholder": "Skriv note i markdown...",
                }
            ),
        }


class TaskNoteAttachmentForm(forms.Form):
    """Form for uploading file attachments to task notes."""

    file = forms.FileField(
        label="Fil",
        widget=forms.ClearableFileInput(
            attrs={
                "class": "input-field",
            }
        ),
    )

    def clean_file(self):
        """Validate that the file extension is allowed."""
        uploaded_file = self.cleaned_data.get("file")
        if uploaded_file:
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext not in TaskNoteAttachment.ALLOWED_EXTENSIONS:
                raise forms.ValidationError(
                    f"Filtypen '{ext}' er ikke tilladt. "
                    f"Tilladte typer: {', '.join(TaskNoteAttachment.ALLOWED_EXTENSIONS)}"
                )
        return uploaded_file


class TaskStatusForm(forms.ModelForm):
    """Form for changing task status inline."""

    class Meta:
        model = Task
        fields = ["status"]
        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "select-field",
                }
            ),
        }
