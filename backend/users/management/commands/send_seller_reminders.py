"""
Management command: send_seller_reminders

Sends email reminders to sellers if:
1. Their ticket has been live (active) for 3 days OR
2. The event is 1 day away (strictly < 24 hours from now)

Logic:
- Query all tickets with status='active' (not sold, deleted, etc.)
- Check if created_at is >= 3 days ago OR event.date is within 24 hours
- Send personalized Hebrew email with direct link to event page
- Track sent reminders to avoid duplicate emails within 24 hours
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db import models
from users.models import Ticket, SellerReminder
from users.utils.emails import send_seller_reminder_email
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send seller reminders for tickets live 3+ days or events 1 day away'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print reminders without sending emails',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        now = timezone.now()
        three_days_ago = now - timedelta(days=3)
        one_day_later = now + timedelta(days=1)

        self.stdout.write(self.style.HTTP_INFO('🔍 Checking for sellers to remind...'))

        # Find active tickets that match criteria
        eligible_tickets = Ticket.objects.filter(
            status='active'
        ).select_related('seller', 'event').filter(
            # Criteria 1: Ticket created 3+ days ago
            models.Q(created_at__lte=three_days_ago) |
            # Criteria 2: Event is within 24 hours (but not in the past)
            models.Q(event__date__lte=one_day_later, event__date__gte=now)
        ).distinct('seller_id')

        count = 0
        for ticket in eligible_tickets:
            if not ticket.seller or not ticket.seller.email:
                continue

            # Check if we already sent a reminder in the last 24 hours
            recent_reminder = SellerReminder.objects.filter(
                seller=ticket.seller,
                ticket=ticket,
                created_at__gte=now - timedelta(hours=24)
            ).exists()

            if recent_reminder:
                self.stdout.write(
                    self.style.WARNING(
                        f'⏭️  Skipping {ticket.seller.email} — reminder already sent in last 24h'
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    f'📧 [DRY-RUN] Would send reminder to {ticket.seller.email} '
                    f'for ticket #{ticket.id} (event: {ticket.event.name if ticket.event else "unknown"})'
                )
            else:
                try:
                    send_seller_reminder_email(
                        seller_email=ticket.seller.email,
                        seller_name=ticket.seller.get_full_name() or ticket.seller.username,
                        event_name=ticket.event.name if ticket.event else 'Unknown Event',
                        event_slug=ticket.event.slug if ticket.event else '',
                        ticket_id=ticket.id,
                    )
                    # Create SellerReminder record to track sent emails
                    SellerReminder.objects.create(
                        seller=ticket.seller,
                        ticket=ticket,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Sent reminder to {ticket.seller.email} (ticket #{ticket.id})'
                        )
                    )
                    count += 1
                except Exception as exc:
                    self.stderr.write(
                        self.style.ERROR(
                            f'❌ Failed to send reminder to {ticket.seller.email}: {exc}'
                        )
                    )
                    logger.exception(f'Seller reminder email failed for seller {ticket.seller.id}')

        if dry_run:
            self.stdout.write(
                self.style.HTTP_INFO(f'\n[DRY-RUN] Would have sent {count} reminders')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✨ Successfully sent {count} seller reminders!')
            )
