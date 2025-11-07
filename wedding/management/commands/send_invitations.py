from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from wedding.models import Group
from wedding.utils import generate_qr_code_data

class Command(BaseCommand):
    help = 'Sends email invitations with embedded QR codes to groups that have a primary email set.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-email',
            action='store_true',
            help='Sends emails only to the specified TEST_EMAIL in settings.',
        )

    def handle(self, *args, **options):
        # Filter for groups that have at least one guest with an email
        groups = Group.objects.filter(guests__email__isnull=False).distinct()
        
        self.stdout.write(f'Preparing to send invitations to {groups.count()} groups...')

        for group in groups:
            # Get the primary contact email (the first one found)
            contact_guest = group.guests.filter(email__isnull=False).filter(email__gt='').first()
            if not contact_guest:
                self.stdout.write(self.style.WARNING(f'Skipping {group.group_name}: No contact email found.'))
                continue

            recipient_email = contact_guest.email
            
            if options['test_email']:
                # Override recipient for testing
                recipient_email = getattr(settings, 'TEST_EMAIL', 'test@example.com')
                if recipient_email == 'test@example.com':
                    self.stdout.write(self.style.ERROR('TEST_EMAIL not configured in settings. Skipping test send.'))
                    continue
            
            # 1. Generate QR Code Data (In Memory)
            qr_buffer = generate_qr_code_data(group.invitation_code)
            
            # Prepare the content ID for the inline image
            qr_cid = f'qr_code_{group.invitation_code}' 

            # 2. Render Email Content
            context = {
                'group': group,
                'contact_name': contact_guest.first_name,
                'qr_cid': qr_cid, # Pass the CID to the template for the <img> tag
            }
            html_content = render_to_string('wedding/email/invitation_email.html', context)
            text_content = render_to_string('wedding/email/invitation_email.txt', context)

            # 3. Create Email Object
            msg = EmailMultiAlternatives(
                subject=f"You're Invited! Wedding RSVP for the {group.group_name}",
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
            )
            msg.attach_alternative(html_content, "text/html")

            # 4. Attach QR Code Inline
            # The name is used for the filename when viewed as an attachment, but the content is embedded.
            msg.attach(
                filename=f'qrcode_{group.invitation_code}.png',
                content=qr_buffer.read(),
                mimetype='image/png',
            )

            try:
                msg.send()
                self.stdout.write(self.style.SUCCESS(f'Successfully sent invite to {group.group_name} at {recipient_email}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to send email to {group.group_name}: {e}'))
