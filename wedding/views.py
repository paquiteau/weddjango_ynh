import logging

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (  # Import the new forms/formset
    GroupRSVPForm,
    GuestFormSet,
    RSVPLookupForm,
)
from .models import Group, InvitationTier

logger = logging.getLogger(__name__)

# --- Invitation Tier Map ---
# Maps the Group.InvitationTier code to the fields that should be visible/editable
TIER_MAP = {
    InvitationTier.FAIRE_PART: [], # Announcement Only - no attendance fields visible
    InvitationTier.MESSE: ['is_attending_ceremony'],
    InvitationTier.COCKTAIL: ['is_attending_ceremony', 'is_attending_cocktail'],
    InvitationTier.REPAS: ['is_attending_ceremony', 'is_attending_cocktail', 'is_attending_dinner', 'is_attending_brunch'],
    InvitationTier.MAIRIE: ['is_attending_mairie', 'is_attending_ceremony', 'is_attending_cocktail', 'is_attending_dinner', 'is_attending_brunch'],
}

def rsvp_view(request: HttpRequest, invitation_code: str) -> HttpResponse:
    group = get_object_or_404(Group, invitation_code=invitation_code)

    # Determine the attendance fields visible based on the group's invitation tier
    attendance_fields: list[str]= TIER_MAP.get(group.invitation_tier, [])
    is_closed = timezone.now() > settings.RSVP_DEADLINE

    if request.method == 'POST' and not is_closed:
        group_form = GroupRSVPForm(request.POST, instance=group)
        guest_formset = GuestFormSet(request.POST, instance=group)

        if group_form.is_valid() and guest_formset.is_valid():
            try:
                with transaction.atomic():
                    # Save Group form (updates address, sleeping, and message)
                    group_instance: Group = group_form.save(commit=False)
                    group_instance.rsvp_submitted = True
                    group_instance.submitted_at = timezone.now()
                    group_instance.save()

                    # Save Guest formset (updates attendance, email, dietary restrictions)
                    guest_formset.save()

                    # Redirect to thank you page
                    return redirect(reverse('rsvp_thanks'))
            except Exception:
                logger.exception("Failed to save RSVP for group %s", group.invitation_code)
                messages.error(
                    request,
                    "Une erreur est survenue lors de l'enregistrement de votre réponse. "
                    "Merci de réessayer, ou de nous contacter si le problème persiste.",
                )
    else:
        group_form = GroupRSVPForm(instance=group)
        guest_formset = GuestFormSet(instance=group)
        if request.method == 'POST' and is_closed:
            messages.error(request, "La période de réponse est close, votre modification n'a pas été enregistrée.")

    if is_closed:
        for field in group_form.fields.values():
            field.disabled = True
        for form in guest_formset.forms:
            for field in form.fields.values():
                field.disabled = True

    context = {
        'group': group,
        'group_form': group_form,
        'guest_formset': guest_formset,
        'attendance_fields': attendance_fields, # Pass the visible fields list for template use
        'rsvp_code': group.invitation_code,
        'is_closed': is_closed,
    }
    return render(request, 'wedding/rsvp_form.html', context)

def rsvp_thanks_view(request : HttpRequest) -> HttpResponse:
    return render(request, 'wedding/rsvp_thank.html')


def rsvp_lookup_view(request: HttpRequest) -> HttpResponse:
    """Lets an invitee find their RSVP form by typing in their invitation code."""
    if request.method == 'POST':
        form = RSVPLookupForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            if Group.objects.filter(invitation_code=code).exists():
                return redirect(reverse('rsvp', kwargs={'invitation_code': code}))
            form.add_error('code', "Ce code n'a pas été reconnu, merci de le vérifier.")
    else:
        form = RSVPLookupForm()

    return render(request, 'wedding/rsvp_lookup.html', {'form': form})


def homepage_view(request: HttpRequest) -> HttpResponse:
    """The main info page for the wedding."""
    # You can add context here: schedule, location, etc.
    return render(request, 'wedding/homepage.html', {'lookup_form': RSVPLookupForm()})

def gift_list_view(request: HttpRequest) -> HttpResponse:
    """The wedding gift list page."""
    return render(request, 'wedding/gift_list.html')
