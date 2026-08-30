import csv
from typing import override

from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Q
from django.forms import BaseInlineFormSet, ValidationError
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.safestring import mark_safe

from .invites import generate_invitations_pdf
from .models import Group, Guest, InvitationTier, StatusChoices
from .utils import generate_qr_code_data  # Import the utility function

EVENT_FIELDS = (
    ("is_attending_ceremony", "Cérémonie"),
    ("is_attending_mairie", "Mairie"),
    ("is_attending_cocktail", "Cocktail"),
    ("is_attending_dinner", "Dîner"),
    ("is_attending_brunch", "Brunch"),
)


class GuestInlineFormSet(BaseInlineFormSet):
    """
    Requires that at least one guest in the group has both a first and last
    name, even though last_name is optional on individual guests.
    """

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        has_full_name = False
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE"):
                if form.cleaned_data.get("first_name") and form.cleaned_data.get(
                    "last_name"
                ):
                    has_full_name = True
                    break

        if not has_full_name:
            raise ValidationError(
                "Au moins un invité du Groupe doit avoir un prénom et un nom renseignés."
            )


class SimpleWeddingAdminSite(admin.AdminSite):
    """
    Custom AdminSite to hide the default User and Group models.
    """

    site_header = "Wedding Site Administration"  # Customize the header text
    site_title = "Wedding Admin"  # Customize the browser title

    @override
    def has_permission(self, request: HttpRequest) -> bool:
        # We need the user to be a superuser or staff to access the admin
        return request.user.is_active and request.user.is_staff

    @override
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("dashboard/", self.admin_view(self.dashboard_view), name="dashboard"),
            path(
                "dashboard/export-catering.csv",
                self.admin_view(self.export_catering_csv),
                name="export_catering_csv",
            ),
        ]
        # Custom urls must come first so they aren't shadowed by the catch-all app_list url.
        return custom_urls + urls

    def dashboard_view(self, request: HttpRequest) -> HttpResponse:
        groups = Group.objects.all()
        total_groups = groups.count()
        submitted_groups = groups.filter(rsvp_submitted=True).count()

        tier_breakdown = list(
            groups.values("invitation_tier")
            .annotate(
                total=Count("id"),
                submitted=Count("id", filter=Q(rsvp_submitted=True)),
            )
            .order_by("invitation_tier")
        )
        tier_labels = dict(InvitationTier.choices)
        for row in tier_breakdown:
            row["label"] = tier_labels.get(
                row["invitation_tier"], row["invitation_tier"]
            )

        status_labels = dict(StatusChoices.choices)
        event_stats = []
        for field, label in EVENT_FIELDS:
            qs = Guest.objects.filter(**{field: True})
            by_status = {
                status_labels[code]: qs.filter(status=code).count()
                for code, _ in StatusChoices.choices
            }
            event_stats.append(
                {
                    "label": label,
                    "total": qs.count(),
                    "by_status": by_status,
                }
            )

        sleeping_friday = groups.filter(requests_sleeping_friday=True)
        sleeping_saturday = groups.filter(requests_sleeping_saturday=True)

        dietary_guests = (
            Guest.objects.exclude(dietary_restrictions="")
            .select_related("group")
            .order_by("group__group_name", "first_name")
        )
        babysitting_guests = (
            Guest.objects.filter(
                Q(status=StatusChoices.BABYSITTED) | ~Q(babysitting_notes="")
            )
            .select_related("group")
            .order_by("group__group_name", "first_name")
        )
        song_requests = (
            Guest.objects.exclude(song_request="")
            .select_related("group")
            .order_by("group__group_name", "first_name")
        )
        group_messages = groups.exclude(group_message="").order_by("group_name")

        no_contact_email_groups = [
            g
            for g in groups
            if not g.guests.filter(email__isnull=False).exclude(email="").exists()
        ]

        context = {
            **self.each_context(request),
            "title": "Tableau de bord RSVP",
            "total_groups": total_groups,
            "submitted_groups": submitted_groups,
            "pending_groups": total_groups - submitted_groups,
            "submission_rate": round(100 * submitted_groups / total_groups)
            if total_groups
            else 0,
            "total_guests": Guest.objects.count(),
            "tier_breakdown": tier_breakdown,
            "event_stats": event_stats,
            "sleeping_friday_count": sleeping_friday.count(),
            "sleeping_saturday_count": sleeping_saturday.count(),
            "sleeping_friday_groups": sleeping_friday,
            "sleeping_saturday_groups": sleeping_saturday,
            "dietary_guests": dietary_guests,
            "babysitting_guests": babysitting_guests,
            "song_requests": song_requests,
            "group_messages": group_messages,
            "no_contact_email_groups": no_contact_email_groups,
            "status_labels_items": StatusChoices.choices,
        }
        return TemplateResponse(request, "admin/dashboard.html", context)

    def export_catering_csv(self, request: HttpRequest) -> HttpResponse:
        """Exports one row per attending guest, for handing to the caterer."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="catering_list.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Groupe",
                "Prénom",
                "Nom",
                "Statut",
                "Cérémonie",
                "Mairie",
                "Cocktail",
                "Dîner",
                "Brunch",
                "Allergies / Régimes",
                "Besoins baby-sitting",
            ]
        )
        guests = Guest.objects.select_related("group").order_by(
            "group__group_name", "first_name"
        )
        for guest in guests:
            writer.writerow(
                [
                    guest.group.group_name,
                    guest.first_name,
                    guest.last_name,
                    guest.get_status_display(),
                    "Oui" if guest.is_attending_ceremony else "",
                    "Oui" if guest.is_attending_mairie else "",
                    "Oui" if guest.is_attending_cocktail else "",
                    "Oui" if guest.is_attending_dinner else "",
                    "Oui" if guest.is_attending_brunch else "",
                    guest.dietary_restrictions,
                    guest.babysitting_notes,
                ]
            )
        return response


# Instantiate your custom site
wedding_admin_site = SimpleWeddingAdminSite(name="wedding_admin")


class GuestInline(admin.StackedInline):
    """
    Allows editing Guest models directly inside the Group admin page.
    """

    model = Guest
    formset = GuestInlineFormSet
    extra = 1  # Show 1 blank slot for a new guest
    fields = (("first_name", "last_name", "status"), "dietary_restrictions", "email")
    verbose_name = "Guest"
    verbose_name_plural = "Guests in this Group"


@admin.register(
    Group, site=wedding_admin_site
)  # Register Group model with the custom site
class GroupAdmin(admin.ModelAdmin):
    """
    The admin configuration for the Group model.
    """

    actions = ["send_invitations_action", "generate_invitations_pdf_action"]

    # 1. NEW ADMIN ACTION METHOD
    @admin.action(description="Send Email Invitation")
    def send_invitations_action(self, request, queryset):
        total_sent = 0
        total_skipped = 0

        for group in queryset:
            # Get the primary contact email (the first one found)
            contact_guest = (
                group.guests.filter(email__isnull=False).filter(email__gt="").first()
            )

            if not contact_guest:
                messages.warning(
                    request,
                    f"Skipping {group.group_name}: No contact email found for any guest.",
                )
                total_skipped += 1
                continue

            recipient_email = contact_guest.email

            try:
                # 2. Generate QR Code Data (In Memory)
                qr_buffer = generate_qr_code_data(group.invitation_code)
                qr_cid = f"qr_code_{group.invitation_code}"

                # 3. Render Email Content
                context = {
                    "group": group,
                    "contact_name": contact_guest.first_name,
                    "qr_cid": qr_cid,
                }
                html_content = render_to_string(
                    "wedding/email/invitation_email.html", context
                )
                text_content = render_to_string(
                    "wedding/email/invitation_email.txt", context
                )

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
                    filename=f"qrcode_{group.invitation_code}.png",
                    content=qr_buffer.read(),
                    mimetype="image/png",
                )

                msg.send()
                total_sent += 1

            except Exception as e:
                messages.error(
                    request,
                    f"Failed to send email to {group.group_name} at {recipient_email}: {e}",
                )
                total_skipped += 1

        if total_sent > 0:
            messages.success(
                request, f"Successfully sent invitations to {total_sent} group(s)."
            )

        if total_skipped > 0:
            messages.info(
                request,
                f"{total_skipped} group(s) were skipped due to errors or missing email addresses.",
            )

        # Prevent the action from redirecting away from the changelist view

    @admin.action(description="Generate Invitations PDF")
    def generate_invitations_pdf_action(self, request, queryset):
        pdf_bytes = generate_invitations_pdf(queryset)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="invitations.pdf"'
        return response

    @admin.display(description="RSVP Link")
    def rsvp_link_display(self, obj: Group) -> str:
        if obj.invitation_code:
            url = reverse("rsvp", kwargs={"invitation_code": obj.invitation_code})
            # full_url = request.build_absolute_uri(url) # Requires access to 'request'
            # Return safe HTML for a clickable link
            return mark_safe(
                f'<a href="{url}" target="_blank">/rsvp/{obj.invitation_code}/</a>'
            )
        return "Code not yet generated"  # Should not happen with current model default

    # What to show in the main list
    list_display = (
        "group_name",
        "invitation_tier",
        "guest_count",
        "get_group_email",
        "rsvp_submitted",
        "requests_sleeping_friday",
        "requests_sleeping_saturday",
    )

    # Filters (with Django 5.0+ facet counts)
    list_filter = (
        "invitation_tier",
        "rsvp_submitted",
        "requests_sleeping_friday",
        "requests_sleeping_saturday",
    )

    # Search functionality
    search_fields = ("group_name", "guests__first_name", "guests__last_name")

    # Add the GuestInline to the Group's edit page
    inlines = [GuestInline]

    # Organize the edit page
    fieldsets = (
        ("Group Info", {"fields": ("group_name", "invitation_tier")}),
        (
            "Address",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "postal_code",
                    "city",
                    "country",
                ),
                "description": "Optionnel : à renseigner si connu, l'invité pourra le compléter/corriger via son formulaire RSVP.",
            },
        ),
        (
            "RSVP Response",
            {
                "fields": (
                    "rsvp_submitted",
                    "requests_sleeping_friday",
                    "requests_sleeping_saturday",
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
        (
            None,
            {
                "fields": ("group_name", "invitation_tier"),
                "description": "Enter the group name and select the invitation tier. RSVP data will appear after the guests reply.",
            },
        ),
        (
            "Address (optionnel)",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "postal_code",
                    "city",
                    "country",
                ),
                "classes": ("collapse",),
            },
        ),
        # RSVP RESPONSE FIELDS ARE OMITTED HERE
    )
    # Make these fields read-only in the admin
    readonly_fields = ("rsvp_link_display", "submitted_at")
    #
    # This method tells Django Admin which fieldsets to use for new objects

    @override
    def get_fieldsets(self, request: HttpRequest, obj: Group | None = None):  # pyright: ignore[reportIncompatibleMethodOverride]
        if obj is None:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    @admin.display(description="RSVP Code")
    def get_formatted_code(self, obj: Group) -> str:
        return obj.invitation_code

    # A helper function for the 'guest_count' in list_display
    @admin.display(description="Guest Count")
    def guest_count(self, obj: Group) -> int:
        return obj.guests.count()

    @admin.display(description="Contact Email")
    def get_group_email(self, obj: Group):
        """Displays the email of the first guest in the group who has one."""
        first_guest_with_email = (
            obj.guests.filter(email__isnull=False).filter(email__gt="").first()
        )
        return (
            first_guest_with_email.email if first_guest_with_email else "NO EMAIL SET"
        )
