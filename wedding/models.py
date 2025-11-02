from __future__ import annotations

import random
import string
from typing import final, override

# Create your models here.
# wedding/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class InvitationTier(models.TextChoices):
    FAIRE_PART = "F", _("Faire-Part uniquement")
    MESSE = "M", _("Messe")
    COCKTAIL = "K", _("Cocktail")
    DINNER = "D", _("Dinner")
    MAIRIE = "R", _("Mairie")


def generate_short_code(length: int = 8) -> str:
    """
    Generates a random short alphanumeric code (e.g., A78DB2C9).
    """
    characters = string.ascii_uppercase + string.digits

    # Generate the code
    code = "".join(random.choice(characters) for _ in range(length))

    # Optional: Format the code with a hyphen for readability (e.g., A78D-B2C9)
    # We will store it without the hyphen in the DB for easier lookup.

    # Ensure the code is unique before returning
    if Group.objects.filter(invitation_code=code).exists():
        # Recursively call if the generated code already exists (unlikely with length 8)
        return generate_short_code(length)

    return code


@final
class Group(models.Model):
    """
    Represents a family or group that gets one invitation.
    """

    guests: models.Manager[Guest]

    id = models.AutoField(primary_key=True)
    # Core Info
    group_name = models.CharField(
        max_length=255, help_text="e.g., 'La Famille XXX' ou 'Alice & Bob'"
    )

    # Invitation Details
    invitation_tier = models.CharField(
        max_length=1,
        choices=InvitationTier.choices,
        default=InvitationTier.FAIRE_PART,
    )
    invitation_code = models.CharField(
        max_length=8,
        editable=False,
        default=generate_short_code,
        unique=True,
        help_text="The unique code for their RSVP link.",
    )

    # RSVP Response (filled by the guest)
    rsvp_submitted = models.BooleanField(default=False)
    requests_sleeping = models.BooleanField(
        default=False, verbose_name="Requires on-site sleeping"
    )
    group_message = models.TextField(
        blank=True,
        verbose_name="Message for the couple",
        help_text="Dietary restrictions, songs, or just a nice note!",
    )
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)

    @override
    def __str__(self):
        return self.group_name

    @property
    def guest_count(self) -> int:
        return self.guests.count()

    @override
    def clean(self):
        """Ensure at least one guest in the group has an email address."""
        # Check if the group has been saved and has guests associated
        if self.id:
            # Check if any guest in this group has a non-empty email
            if (
                not self.guests.filter(email__isnull=False)
                .filter(email__gt="")
                .exists()
            ):
                raise ValidationError(
                    "At least one guest in this group must have an email address."
                )

    @property
    def formatted_code(self) -> str:
        """Returns the invitation code formatted with a hyphen for readability."""
        return f"{self.invitation_code[:4]}-{self.invitation_code[4:]}"


@final
class Guest(models.Model):
    """
    An individual guest, part of a Group.
    """

    id = models.AutoField(primary_key=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="guests")

    # Guest Info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    is_child = models.BooleanField(default=False, verbose_name="Mineure/Enfant")
    is_babysitted = models.BooleanField(
        default=False, verbose_name="Besoin de baby-sitting"
    )

    email = models.EmailField(
        blank=True, null=True, max_length=254, help_text="Email de contact."
    )
    #
    # RSVP Status (filled by the guest)
    is_attending_ceremony = models.BooleanField(
        default=False, verbose_name="Participe à la Cérémonie"
    )
    is_attending_mairie = models.BooleanField(
        default=False, verbose_name="Participe à la Mairie"
    )
    is_attending_cocktail = models.BooleanField(
        default=False, verbose_name="Participe au Cocktail"
    )
    is_attending_dinner = models.BooleanField(
        default=False, verbose_name="Participe au Dîner"
    )

    dietary_restrictions = models.CharField(
        max_length=255, blank=True, verbose_name="Allergies / Régimes alimentaires"
    )

    @override
    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"
