"""
Management command to reset all tickets to active status and clear reservations.
This is a one-time fix to resolve stuck reservations and synchronization issues.

Usage: python manage.py reset_all_tickets
"""
from django.core.management.base import BaseCommand
from users.models import Ticket
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reset all tickets to active status and clear all reservations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all tickets
        all_tickets = Ticket.objects.all()
        total_count = all_tickets.count()
        
        # Count tickets that need resetting
        reserved_tickets = Ticket.objects.filter(status='reserved')
        reserved_count = reserved_count = reserved_tickets.count()
        
        tickets_with_reservations = Ticket.objects.exclude(reserved_at__isnull=True)
        reservation_count = tickets_with_reservations.count()
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Ticket Reset Report ==='))
        self.stdout.write(f'Total tickets in database: {total_count}')
        self.stdout.write(f'Tickets with status="reserved": {reserved_count}')
        self.stdout.write(f'Tickets with reserved_at set: {reservation_count}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes will be made.'))
            self.stdout.write(f'Would reset {reserved_count} reserved tickets to active')
            self.stdout.write(f'Would clear reservations from {reservation_count} tickets')
            return
        
        # Reset all tickets to active and clear reservations
        updated = Ticket.objects.all().update(
            status='active',
            reserved_at=None,
            reserved_by=None,
            reservation_email=None
        )
        
        logger.info(f'Reset {updated} tickets to active status and cleared all reservations')
        
        self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Successfully reset {updated} tickets'))
        self.stdout.write(self.style.SUCCESS('[SUCCESS] All tickets set to status="active"'))
        self.stdout.write(self.style.SUCCESS('[SUCCESS] All reservations cleared (reserved_at, reserved_by, reservation_email)'))
        self.stdout.write(self.style.SUCCESS('\nDatabase reset complete!'))


