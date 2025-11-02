"""Views for handling wedding RSVP and related pages."""

from django.shortcuts import render, get_object_or_404, redirect
from django.forms import modelformset_factory
from django.utils import timezone
from django.http import HttpRequest, HttpResponse
from .models import Group, Guest
from .forms import GroupRSVPForm, GuestRSVPForm

def rsvp_view(request: HttpRequest, invitation_code: str) -> HttpResponse:
    """
    The main RSVP view, driven by the unique invitation code.
    """
    group = get_object_or_404(Group, invitation_code=invitation_code)
    
    # Create a FormSet for all guests in this group
    GuestFormSet = modelformset_factory(
        Guest, 
        form=GuestRSVPForm, 
        extra=0  # Don't show any extra blank forms
    )
    
    # Get the tier for this group to hide/show form fields
    tier = group.invitation_tier

    if request.method == 'POST':
        group_form = GroupRSVPForm(request.POST, instance=group, prefix='group')
        guest_formset = GuestFormSet(
            request.POST, 
            queryset=group.guests.all(), 
            prefix='guest'
        )
        
        if group_form.is_valid() and guest_formset.is_valid():
            # Save the group-level info
            group_instance = group_form.save(commit=False)
            group_instance.rsvp_submitted = True  # Mark as submitted!
            group_instance.submitted_at = timezone.now()
            group_instance.save()
            
            # Save all the individual guest info
            guest_formset.save()
            
            return redirect('rsvp_thanks') # Redirect to a "Thank You" page

    else:
        # GET request: Show the blank forms
        group_form = GroupRSVPForm(instance=group, prefix='group')
        guest_formset = GuestFormSet(
            queryset=group.guests.all(), 
            prefix='guest'
        )

    context = {
        'group': group,
        'group_form': group_form,
        'guest_formset': guest_formset,
        'invitation_tier': tier,
    }
    return render(request, 'wedding/rsvp_form.html', context)


def rsvp_thanks_view(request: HttpRequest) -> HttpResponse:
    """A simple 'Thank You' page."""
    return render(request, 'wedding/rsvp_thanks.html')

def homepage_view(request: HttpRequest) -> HttpResponse:
    """The main info page for the wedding."""
    # You can add context here: schedule, location, etc.
    return render(request, 'wedding/homepage.html')

def gift_list_view(request: HttpRequest) -> HttpResponse:
    """The wedding gift list page."""
    return render(request, 'wedding/gift_list.html')
