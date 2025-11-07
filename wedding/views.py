from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.urls import reverse
from .models import Group, Guest, InvitationTier
from .forms import GroupRSVPForm, GuestFormSet # Import the new forms/formset
from datetime import datetime

# --- Invitation Tier Map ---
# Maps the Group.InvitationTier code to the fields that should be visible/editable
TIER_MAP = {
    InvitationTier.FAIRE_PART: [], # Announcement Only - no attendance fields visible
    InvitationTier.MESSE: ['is_attending_ceremony'],
    InvitationTier.COCKTAIL: ['is_attending_ceremony', 'is_attending_cocktail'],
    InvitationTier.REPAS: ['is_attending_ceremony', 'is_attending_cocktail', 'is_attending_dinner'],
    InvitationTier.MAIRIE: ['is_attending_ceremony', 'is_attending_cocktail', 'is_attending_dinner'],
}

def rsvp_view(request: HttpRequest, invitation_code: str) -> HttpResponse:
    group = get_object_or_404(Group, invitation_code=invitation_code)
    
    # Determine the attendance fields visible based on the group's invitation tier
    attendance_fields: list[str]= TIER_MAP.get(group.invitation_tier, [])

    if request.method == 'POST':
        group_form = GroupRSVPForm(request.POST, instance=group)
        guest_formset = GuestFormSet(request.POST, instance=group)

        if group_form.is_valid() and guest_formset.is_valid():
            try:
                with transaction.atomic():
                    # Save Group form (updates address, sleeping, and message)
                    group_instance: Group = group_form.save(commit=False)
                    group_instance.rsvp_submitted = True
                    group_instance.submitted_at = datetime.now()
                    group_instance.save()
                    
                    # Save Guest formset (updates attendance, email, dietary restrictions)
                    guest_formset.save()

                    # Redirect to thank you page
                    return redirect(reverse('rsvp_thanks'))
            except Exception as e:
                # Handle database errors if necessary
                pass 
    else:
        group_form = GroupRSVPForm(instance=group)
        guest_formset = GuestFormSet(instance=group)

    context = {
        'group': group,
        'group_form': group_form,
        'guest_formset': guest_formset,
        'attendance_fields': attendance_fields, # Pass the visible fields list for template use
        'rsvp_code': group.formatted_code,
    }
    return render(request, 'wedding/rsvp_form.html', context)

def rsvp_thanks_view(request : HttpRequest) -> HttpResponse:
    return render(request, 'wedding/rsvp_thanks.html')


def homepage_view(request: HttpRequest) -> HttpResponse:
    """The main info page for the wedding."""
    # You can add context here: schedule, location, etc.
    return render(request, 'wedding/homepage.html')

def gift_list_view(request: HttpRequest) -> HttpResponse:
    """The wedding gift list page."""
    return render(request, 'wedding/gift_list.html')
