"""
Management command to fix existing tickets' asking_price to be properly rounded.
This ensures all prices are saved with exactly 2 decimal places (e.g., 444.00).

Usage: python manage.py fix_ticket_prices
"""
from django.core.management.base import BaseCommand
from users.models import Ticket
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix existing tickets asking_price to be properly rounded to 2 decimal places'

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
        
        # Find tickets that need fixing
        tickets_to_fix = []
        for ticket in all_tickets:
            if ticket.original_price is not None:
                # Check if price needs rounding
                original_decimal = Decimal(str(ticket.original_price))
                rounded_original = original_decimal.quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
                rounded_asking = rounded_original  # asking_price should equal original_price
                
                # Check if rounding is needed
                if (ticket.original_price != rounded_original or 
                    ticket.asking_price != rounded_asking):
                    tickets_to_fix.append({
                        'ticket': ticket,
                        'old_original': ticket.original_price,
                        'old_asking': ticket.asking_price,
                        'new_original': rounded_original,
                        'new_asking': rounded_asking,
                    })
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Ticket Price Fix Report ==='))
        self.stdout.write(f'Total tickets in database: {total_count}')
        self.stdout.write(f'Tickets that need price fixing: {len(tickets_to_fix)}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes will be made.'))
            for fix_info in tickets_to_fix[:10]:  # Show first 10
                ticket = fix_info['ticket']
                self.stdout.write(
                    f'Ticket {ticket.id}: '
                    f'original_price {fix_info["old_original"]} -> {fix_info["new_original"]}, '
                    f'asking_price {fix_info["old_asking"]} -> {fix_info["new_asking"]}'
                )
            if len(tickets_to_fix) > 10:
                self.stdout.write(f'... and {len(tickets_to_fix) - 10} more tickets')
            return
        
        # Fix tickets
        fixed_count = 0
        for fix_info in tickets_to_fix:
            ticket = fix_info['ticket']
            ticket.original_price = fix_info['new_original']
            ticket.asking_price = fix_info['new_asking']
            ticket.save()
            fixed_count += 1
            
            logger.info(
                f'Fixed ticket {ticket.id}: '
                f'original_price {fix_info["old_original"]} -> {fix_info["new_original"]}, '
                f'asking_price {fix_info["old_asking"]} -> {fix_info["new_asking"]}'
            )
        
        self.stdout.write(self.style.SUCCESS(f'\n[SUCCESS] Fixed {fixed_count} tickets'))
        self.stdout.write(self.style.SUCCESS('All prices are now properly rounded to 2 decimal places'))
        self.stdout.write(self.style.SUCCESS('\nPrice fix complete!'))




