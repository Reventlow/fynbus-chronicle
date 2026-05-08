"""Forms for the feature-request app."""

from django import forms

from .models import FeatureRequest


class FeatureRequestForm(forms.ModelForm):
    """Submit / edit a feature request. Status + resolution_notes only
    appear on the edit form for editors via the views."""

    class Meta:
        model = FeatureRequest
        fields = ["title", "description", "category", "importance", "triggers_version_bump"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Kort titel — fx 'Tilføj eksport som CSV'",
                    "maxlength": 200,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 6,
                    "placeholder": (
                        "Hvad ønskes der? Hvorfor? Du kan paste links til GitHub-"
                        "issues, screenshots, Figma osv. — de bliver klikbare."
                    ),
                }
            ),
            "category": forms.Select(attrs={"class": "select-field"}),
            "importance": forms.Select(attrs={"class": "select-field"}),
            "triggers_version_bump": forms.CheckboxInput(attrs={"class": "checkbox-field"}),
        }


class FeatureRequestEditForm(forms.ModelForm):
    """Editor-only edit form — adds status, resolution_notes, order."""

    class Meta:
        model = FeatureRequest
        fields = [
            "title",
            "description",
            "category",
            "importance",
            "status",
            "triggers_version_bump",
            "resolution_notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input-field", "maxlength": 200}),
            "description": forms.Textarea(
                attrs={"class": "textarea-field", "rows": 6}
            ),
            "category": forms.Select(attrs={"class": "select-field"}),
            "importance": forms.Select(attrs={"class": "select-field"}),
            "status": forms.Select(attrs={"class": "select-field"}),
            "triggers_version_bump": forms.CheckboxInput(attrs={"class": "checkbox-field"}),
            "resolution_notes": forms.Textarea(
                attrs={
                    "class": "textarea-field",
                    "rows": 4,
                    "placeholder": "Hvad blev løsningen? PR-nummer / version osv.",
                }
            ),
        }
