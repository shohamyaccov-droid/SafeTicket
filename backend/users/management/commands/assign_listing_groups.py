"""
Management command to assign listing_group_id to existing tickets that don't have one.
This ensures all tickets can be displayed in the grouped UI.

Usage: python manage.py assign_listing_groups
"""
from django.core.management.base import BaseCommand
from users.models import Ticket
import uuid
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Assign listing_group_id to existing tickets that don\'t have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all tickets without listing_group_id
        tickets_without_group = Ticket.objects.filter(listing_group_id__isnull=True)
        total_count = tickets_without_group.count()
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Listing Group Assignment Report ==='))
        self.stdout.write(f'Total tickets without listing_group_id: {total_count}')
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('All tickets already have listing_group_id assigned.'))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes will be made.'))
            self.stdout.write(f'Would assign unique listing_group_id to {total_count} tickets')
            
            # Show sample of tickets that would be updated
            sample_tickets = tickets_without_group[:10]
            for ticket in sample_tickets:
                self.stdout.write(
                    f'  Ticket {ticket.id}: Event={ticket.event_id if ticket.event else "N/A"}, '
                    f'Price={ticket.original_price}, Seller={ticket.seller.username if ticket.seller else "N/A"}'
                )
            if total_count > 10:
                self.stdout.write(f'  ... and {total_count - 10} more tickets')
            return
        
        # Group tickets by seller, event, and price to assign same listing_group_id
        # This way tickets that were likely listed together get the same group ID
        updated_count = 0
        group_assignments = {}
        
        for ticket in tickets_without_group:
            # Create a key based on seller, event, price, and created_at (within same minute)
            # This groups tickets that were likely created together
            if ticket.seller and ticket.event:
                # Use seller + event + price + created_at (rounded to minute) as grouping key
                created_minute = ticket.created_at.replace(second=0, microsecond=0) if ticket.created_at else None
                group_key = (
                    ticket.seller.id,
                    ticket.event.id,
                    str(ticket.original_price),
                    str(created_minute) if created_minute else 'no_date'
                )
                
                if group_key not in group_assignments:
                    # Assign new UUID for this group
                    group_assignments[group_key] = str(uuid.uuid4())
                
                ticket.listing_group_id = group_assignments[group_key]
            else:
                # For tickets without seller or event, assign unique ID to each
                ticket.listing_group_id = str(uuid.uuid4())
            
            ticket.save(update_fields=['listing_group_id'])
            updated_count += 1
            
            if updated_count % 100 == 0:
                self.stdout.write(f'Processed {updated_count}/{total_count} tickets...')
        
        logger.info(f'Assigned listing_group_id to {updated_count} tickets')
        
        self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Assigned listing_group_id to {updated_count} tickets'))
        self.stdout.write(self.style.SUCCESS(f'Created {len(group_assignments)} unique listing groups'))
        self.stdout.write(self.style.SUCCESS('\nAll tickets now have listing_group_id assigned!'))




