from typing import override

from django.contrib import admin, messages
from django.http import HttpRequest
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

from .forms import GuestInlineFormSet
from .models import Group, Guest
from .utils import generate_qr_code_data # Import the utility function

class SimpleWeddingAdminSite(admin.AdminSite):
    """
    Custom AdminSite to hide the default User and Group models.
    """
    site_header = "Wedding Site Administration" # Customize the header text
    site_title = "Wedding Admin" # Customize the browser title

    @override
    def has_permission(self, request: HttpRequest) -> bool:
        # We need the user to be a superuser or staff to access the admin
        return request.user.is_active and request.user.is_staff

# Instantiate your custom site
wedding_admin_site = SimpleWeddingAdminSite(name='wedding_admin')

class GuestInline(admin.StackedInline):
    """
    Allows editing Guest models directly inside the Group admin page.
    """

    model = Guest
    extra= 1  # Show 1 blank slot for a new guest
    fields = (("first_name", "last_name", "status"), "dietary_restrictions", "email")
    verbose_name = "Guest"
    verbose_name_plural = "Guests in this Group"
    formset = GuestInlineFormSet

@admin.register(Group, site=wedding_admin_site) # Register Group model with the custom site
class GroupAdmin(admin.ModelAdmin):
    """
    The admin configuration for the Group model.
    """

    actions = ["send_invitations_action"]
    # 1. NEW ADMIN ACTION METHOD
    @admin.action(description='Send Email Invitation')
    def send_invitations_action(self, request, queryset):
        total_sent = 0
        total_skipped = 0
        
        for group in queryset:
            # Get the primary contact email (the first one found)
            contact_guest = group.guests.filter(email__isnull=False).filter(email__gt='').first()
            
            if not contact_guest:
                messages.warning(request, f'Skipping {group.group_name}: No contact email found for any guest.')
                total_skipped += 1
                continue

            recipient_email = contact_guest.email
            
            try:
                # 2. Generate QR Code Data (In Memory)
                qr_buffer = generate_qr_code_data(group.invitation_code)
                qr_cid = f'qr_code_{group.invitation_code}' 

                # 3. Render Email Content
                context = {
                    'group': group,
                    'contact_name': contact_guest.first_name,
                    'qr_cid': qr_cid,
                }
                html_content = render_to_string('wedding/email/invitation_email.html', context)
                text_content = render_to_string('wedding/email/invitation_email.txt', context)

                # 4. Create and Send Email Object
                msg = EmailMultiAlternatives(
                    subject=f"You're Invited! Wedding RSVP for the {group.group_name}",
                    body=text_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient_email],
                )
                msg.attach_alternative(html_content, "text/html")

                # Attach QR Code Inline
                msg.attach(
                    filename=f'qrcode_{group.invitation_code}.png',
                    content=qr_buffer.read(),
                    mimetype='image/png',
                )

                msg.send()
                total_sent += 1
                
            except Exception as e:
                messages.error(request, f'Failed to send email to {group.group_name} at {recipient_email}: {e}')
                total_skipped += 1

        if total_sent > 0:
            messages.success(request, f'Successfully sent invitations to {total_sent} group(s).')
        
        if total_skipped > 0:
             messages.info(request, f'{total_skipped} group(s) were skipped due to errors or missing email addresses.')
        
        # Prevent the action from redirecting away from the changelist view
        return None
    

    @admin.display(description='RSVP Link')
    def rsvp_link_display(self, obj:Group) -> str:
        if obj.invitation_code:
            url = reverse('rsvp', kwargs={'invitation_code': obj.invitation_code})
            # full_url = request.build_absolute_uri(url) # Requires access to 'request'
            # Return safe HTML for a clickable link
            return mark_safe(f'<a href="{url}" target="_blank">/rsvp/{obj.formatted_code}/</a>')
        return "Code not yet generated" # Should not happen with current model default
    
    # What to show in the main list
    list_display = (
        "group_name",
        "invitation_tier",
        "guest_count",
        "get_group_email",
        "rsvp_submitted",
        "requests_sleeping",
    )

    # Filters (with Django 5.0+ facet counts)
    list_filter = ("invitation_tier", "rsvp_submitted", "requests_sleeping")

    # Search functionality
    search_fields = ("group_name", "guests__first_name", "guests__last_name")

    # Add the GuestInline to the Group's edit page
    inlines = [GuestInline]

    # Organize the edit page
    fieldsets = (
        ("Group Info", {"fields": ("group_name", "invitation_tier")}),
        (
           "RSVP Response",
            {
                "fields": (
                    "rsvp_submitted",
                    "requests_sleeping",
                    "group_message",
                    "submitted_at",
                )
            },
        ),
        (
            "Invitation Link",
            {
                "fields": ("rsvp_link_display",),
            },
        ),
    )
    # only for creation of the group:
    add_fieldsets = (
        (None, {
            'fields': ('group_name', 'invitation_tier'),
            'description': 'Enter the group name and select the invitation tier. RSVP data will appear after the guests reply.',
        }),
        # RSVP RESPONSE FIELDS ARE OMITTED HERE
    )
    # Make these fields read-only in the admin
    readonly_fields = ("rsvp_link_display", "submitted_at")
# 
# This method tells Django Admin which fieldsets to use for new objects

    @override
    def get_fieldsets(self, request:HttpRequest, obj:Group | None = None):  # pyright: ignore[reportIncompatibleMethodOverride]
        if obj is None:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    @admin.display(description='RSVP Code')
    def get_formatted_code(self, obj:Group) -> str:
        return obj.formatted_code
    # A helper function for the 'guest_count' in list_display
    @admin.display(description="Guest Count")
    def guest_count(self, obj: Group) -> int:
        return obj.guests.count()

    @admin.display(description='Contact Email')
    def get_group_email(self, obj:Group):
        """Displays the email of the first guest in the group who has one."""
        first_guest_with_email = obj.guests.filter(email__isnull=False).filter(email__gt='').first()
        return first_guest_with_email.email if first_guest_with_email else "NO EMAIL SET"

