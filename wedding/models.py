from __future__ import annotations

import random
import string
from typing import final

# Create your models here.
# wedding/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class InvitationTier(models.TextChoices):
    FAIRE_PART = "F", _("Faire-Part uniquement")
    MESSE = "M", _("Messe (+ Faire-Part)")
    COCKTAIL = "K", _("Cocktail (+ Messe + Faire-Part)")
    REPAS = "D", _("Repas (+ Cocktail + Messe + Faire-Part)")
    MAIRIE = "R", _("Mairie (+ Dinner + Cocktail + Messe + Faire-Part)")


class StatusChoices(models.TextChoices):
    ENFANT = "C", _("Enfant")
    ADULTE = "A", _("Adulte")
    BABYSITTED = "B", _("Enfant qui a besoin d'un baby-sitting")


def generate_short_code(length: int = 4) -> str:
    """
    Generates a random short alphanumeric code (e.g., A78D).
    """
    characters = string.ascii_uppercase + string.digits

    # Generate the code
    code = "".join(random.choice(characters) for _ in range(length))

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
        max_length=255, help_text="e.g., 'La Famille XXX' ou 'Marine & Pierre-Antoine"
    )

    address_line_1 = models.CharField(
        max_length=255, blank=True, verbose_name="Addresse (1)"
    )
    address_line_2 = models.CharField(
        max_length=255, blank=True, verbose_name="Addresse (2)"
    )
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    postal_code = models.CharField(
        max_length=20, blank=True, verbose_name="Code Postal"
    )
    country = models.CharField(max_length=100, blank=True, verbose_name="Pays")

    # Invitation Details
    invitation_tier = models.CharField(
        max_length=1,
        choices=InvitationTier.choices,
        default=InvitationTier.FAIRE_PART,
    )
    invitation_code = models.CharField(
        max_length=4,
        editable=False,
        default=generate_short_code,
        unique=True,
        help_text="The unique code for their RSVP link.",
    )

    # RSVP Response (filled by the guest)
    rsvp_submitted = models.BooleanField(default=False)
    requests_sleeping_friday = models.BooleanField(
        default=False, verbose_name="Nuit de vendredi à samedi sur place"
    )
    requests_sleeping_saturday = models.BooleanField(
        default=False, verbose_name="Nuit de samedi à dimanche sur place"
    )
    group_message = models.TextField(
        blank=True,
        verbose_name="Un message pour les mariés",
        help_text="Ce qui est important pour vous, quelque chose à prendre en compte, ou juste un petit mot!",
    )
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)

    def __str__(self):
        return self.group_name

    @property
    def guest_count(self) -> int:
        return self.guests.count()

    def clean(self):
        """Ensure at least one guest in the group has an email address."""
        # Check if the group has been saved and has guests associated
        if self.id and not (
            self.guests.filter(email__isnull=False).filter(email__gt="").exists()
        ):
            raise ValidationError(
                "Au moins un invité doit avoir son adresse mail renseignée."
            )



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

    status = models.CharField(
        choices=StatusChoices.choices,
        max_length=1,
        default=StatusChoices.ADULTE,
        verbose_name="Je suis un(e)",
    )

    email = models.EmailField(
        blank=True, null=True, max_length=254, help_text="Email de contact."
    )
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

    babysitting_notes = models.TextField(
        blank=True, verbose_name="Besoins spécifiques (baby-sitting)"
    )

    song_request = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Une chanson pour la soirée",
        help_text="Un morceau qui vous ferait danser !",
    )

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"
