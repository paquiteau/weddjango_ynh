from typing import final
from django import forms
from django.forms import ModelForm
from .models import Group, Guest


@final
class GroupRSVPForm(ModelForm):
    """
    Form for the Group-level questions (sleeping, message).
    """

    @final
    class Meta:
        model = Group
        fields = ["requests_sleeping", "group_message"]
        widgets = {
            "requests_sleeping": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "group_message": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }


class GuestRSVPForm(ModelForm):
    """
    Form for each individual Guest (attending status, diet).
    """

    @final
    class Meta:
        model = Guest
        fields = [
            "is_attending_ceremony",
            "is_attending_cocktail",
            "is_attending_dinner",
            "dietary_restrictions",
        ]
        widgets = {
            "is_attending_ceremony": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "is_attending_cocktail": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "is_attending_dinner": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "dietary_restrictions": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
        }
