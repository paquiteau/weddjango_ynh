from typing import final, override

from django.contrib import admin
from django.http import HttpRequest
from .models import Group, Guest

# wedding/admin.py (UPDATED)

from django.contrib import admin
from django.contrib.auth.models import User, Group as AuthGroup # Renaming to avoid confusion
from .models import Group, Guest
from django.db.models import Count

class SimpleWeddingAdminSite(admin.AdminSite):
    """
    Custom AdminSite to hide the default User and Group models.
    """
    site_header = "Wedding Site Administration" # Customize the header text
    site_title = "Wedding Admin" # Customize the browser title

    # Automatically unregister the default auth models
    def has_permission(self, request):
        # We need the user to be a superuser or staff to access the admin
        return request.user.is_active and request.user.is_staff

# Instantiate your custom site
wedding_admin_site = SimpleWeddingAdminSite(name='wedding_admin')

class GuestInline(admin.TabularInline):
    """
    Allows editing Guest models directly inside the Group admin page.
    """

    model = Guest
    extra= 1  # Show 1 blank slot for a new guest
    fields = ("first_name", "last_name", "is_child", "dietary_restrictions", "email")
    verbose_name = "Guest"
    verbose_name_plural = "Guests in this Group"


@admin.register(Group, site=wedding_admin_site) # Register Group model with the custom site
class GroupAdmin(admin.ModelAdmin):
    """
    The admin configuration for the Group model.
    """

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
           http://localhost:8000/ "RSVP Response",
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
                "description": "Send this link to the guest: /rsvp/INVITATION_CODE/",
                "fields": ("invitation_code",),
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
    readonly_fields = ("invitation_code", "submitted_at")
# 
# This method tells Django Admin which fieldsets to use for new objects

    @override
    def get_fieldsets(self, request:HttpRequest, obj:Group | None = None):  # pyright: ignore[reportIncompatibleMethodOverride]
        if obj is None:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    @admin.display(description='RSVP Code')
    def get_formatted_code(self, obj):
        return obj.get_formatted_code()
    # A helper function for the 'guest_count' in list_display
    @admin.display(description="Guest Count")
    def guest_count(self, obj: Group) -> int:
        return obj.guests.count()

    @admin.display(description='Contact Email')
    def get_group_email(self, obj:Group):
        """Displays the email of the first guest in the group who has one."""
        first_guest_with_email = obj.guests.filter(email__isnull=False).filter(email__gt='').first()
        return first_guest_with_email.email if first_guest_with_email else "⚠️ NO EMAIL SET"

# We don't need a separate admin for Guest, as it's handled in-line.
# But you could register it if you wanted a separate list.
# admin.site.register(Guest)
