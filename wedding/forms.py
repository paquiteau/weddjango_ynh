from django import forms
from django.forms import BaseInlineFormSet, ModelForm, ValidationError, inlineformset_factory
from .models import Group, Guest


class GuestInlineFormSet(BaseInlineFormSet):
    """
    Custom formset to enforce that at least one guest in the group has an email address.
    """
    def clean(self):
        # 1. Call the parent clean method first
        super().clean() 
        
        if any(self.errors):
            return
            
        has_email = False

        # 2. Iterate over forms and check for email, respecting deletion status
        for form in self.forms:
            # Check if the form is valid and not marked for deletion
            if form.cleaned_data:
                # The Admin sets 'DELETE' in cleaned_data if the form's checkbox is checked
                # We only proceed if 'DELETE' is False (i.e., the guest is being kept)
                is_deleted = form.cleaned_data.get('DELETE')
                
                if not is_deleted:
                    email_data = form.cleaned_data.get('email')
                    if email_data:
                        has_email = True
                        break # Found an email and an address we can stop checking
                
        # 3. Raise the ValidationError if validation fails
        if not has_email:
            raise ValidationError(
                "Au moins un invité du Groupe doit avoir une adresse e-mail et une adresse postale renseignées."
            )

class GroupRSVPForm(ModelForm):
    """Form for guests to update group-level information."""
    class Meta:
        model = Group
        fields = [
            'address_line_1', 
            'address_line_2', 
            'city', 
            'postal_code', 
            'country',
            'requests_sleeping_friday',
            'requests_sleeping_saturday',
            'group_message'
        ]
        labels = {
            'requests_sleeping_friday': "Nous souhaitons loger sur place la nuit de vendredi à samedi (si disponible).",
            'requests_sleeping_saturday': "Nous souhaitons loger sur place la nuit de samedi à dimanche (si disponible).",
        }
        widgets = {
            'group_message': forms.Textarea(attrs={'rows': 3}),
        }

# --- NEW: Form for Individual Guest RSVP/Update ---
class GuestRSVPForm(ModelForm):
    """Form for guests to update their email and attendance."""
    class Meta:
        model = Guest
        fields = [
            # Personal Updatable Info
            'status',
            'email',
            'dietary_restrictions',
            'babysitting_notes',
            'song_request',
            # Attendance for Events (Attendance fields will be dynamic in the view)
            'is_attending_ceremony',
            'is_attending_mairie',
            'is_attending_cocktail',
            'is_attending_dinner',
        ]
        # Make the attendance fields checkboxes instead of generic booleans
        widgets = {
            'is_attending_ceremony': forms.CheckboxInput(),
            'is_attending_mairie': forms.CheckboxInput(),
            'is_attending_cocktail': forms.CheckboxInput(),
            'is_attending_dinner': forms.CheckboxInput(),
            'babysitting_notes': forms.Textarea(attrs={'rows': 2}),
        }


class RSVPLookupForm(forms.Form):
    """Form used on the manual code-entry page to find a Group by its invitation code."""
    code = forms.CharField(
        max_length=4,
        label="Votre code d'invitation",
        widget=forms.HiddenInput(),
    )

    def clean_code(self) -> str:
        return self.cleaned_data['code'].strip().upper()

# --- CREATE the Formset Factory ---
# This factory creates the formset needed by the view
GuestFormSet = inlineformset_factory(
    Group, 
    Guest, 
    form=GuestRSVPForm, 
    formset=GuestInlineFormSet, # Use custom formset for email validation
    extra=0, # Do not show empty extra forms
    can_delete=False # Guests cannot be removed from the list
)
