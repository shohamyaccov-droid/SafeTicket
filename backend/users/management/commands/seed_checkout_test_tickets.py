"""
Create visible marketplace tickets for manual checkout testing.

Usage:
  python manage.py seed_checkout_test_tickets
  python manage.py seed_checkout_test_tickets --dry-run
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.models import Artist, Event, Ticket, Venue

User = get_user_model()

SELLER_EMAIL = 'checkout-test-seller@safeticket.com'
SELLER_USERNAME = 'checkout_test_seller'
PDF_BYTES = b'%PDF-1.4\n1 0 obj<< /Type /Catalog >>endobj\ntrailer<< /Root 1 0 R >>\n%%EOF\n'

EVENT_SPECS = (
    {
        'artist': 'אמן בדיקת Checkout א',
        'genre': 'Pop',
        'event_name': 'בדיקת Checkout — אמן א',
        'venue': 'ישראל',
        'venue_place': 'אצטדיון רמת גן',
        'city': 'רמת גן',
        'days_from_now': 21,
    },
    {
        'artist': 'אמן בדיקת Checkout ב',
        'genre': 'Mizrahi',
        'event_name': 'בדיקת Checkout — אמן ב',
        'venue': 'אצטדיון בלומפילד (הופעות)',
        'venue_place': 'אצטדיון בלומפילד',
        'city': 'תל אביב',
        'days_from_now': 28,
    },
)

TICKET_SPECS = (
    (0, 'בדיקה A', '1', '101', Decimal('169')),
    (0, 'בדיקה B', '2', '102', Decimal('189')),
    (0, 'בדיקה C', '3', '103', Decimal('219')),
    (1, 'בדיקה D', '4', '104', Decimal('249')),
    (1, 'בדיקה E', '5', '105', Decimal('299')),
)


class Command(BaseCommand):
    help = 'Create 5 active verified tickets for manual PayMe checkout testing.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print planned rows without writing to the DB.')
        parser.add_argument('--count', type=int, default=5, help='Number of tickets to create/update, max 5.')

    def handle(self, *args, **options):
        dry_run = bool(options['dry_run'])
        count = max(1, min(5, int(options['count'] or 5)))
        now = timezone.now()

        self.stdout.write(f'Checkout test tickets seed: count={count} dry_run={dry_run}')
        if dry_run:
            for idx, spec in enumerate(TICKET_SPECS[:count], start=1):
                event_spec = EVENT_SPECS[spec[0]]
                when = now + timedelta(days=event_spec['days_from_now'])
                self.stdout.write(
                    f'  #{idx}: event_index={spec[0]} row={spec[2]} '
                    f'seat={spec[3]} price={spec[4]} date={when.isoformat()}'
                )
            return

        with transaction.atomic():
            seller, _ = User.objects.update_or_create(
                email=SELLER_EMAIL,
                defaults={
                    'username': SELLER_USERNAME,
                    'role': 'seller',
                    'is_active': True,
                    'is_email_verified': True,
                    'is_verified_seller': True,
                    'accepted_escrow_terms': True,
                    'escrow_terms_accepted_at': now,
                    'account_holder_name': 'Checkout Test Seller',
                    'bank_name': '12',
                    'branch_number': '345',
                    'account_number': '123456789',
                },
            )
            if not seller.has_usable_password():
                seller.set_unusable_password()
                seller.save(update_fields=['password'])

            events: list[Event] = []
            for event_spec in EVENT_SPECS:
                artist, _ = Artist.objects.get_or_create(
                    name=event_spec['artist'],
                    defaults={'genre': event_spec['genre'], 'description': 'Checkout test artist'},
                )
                venue_place, _ = Venue.objects.get_or_create(
                    name=event_spec['venue_place'],
                    city=event_spec['city'],
                )
                event_date = now + timedelta(days=event_spec['days_from_now'])
                event, _ = Event.objects.update_or_create(
                    name=event_spec['event_name'],
                    defaults={
                        'artist': artist,
                        'date': event_date,
                        'venue': event_spec['venue'],
                        'venue_place': venue_place,
                        'city': event_spec['city'],
                        'country': 'IL',
                        'category': 'concert',
                        'status': 'פעיל',
                        'high_demand': True,
                    },
                )
                events.append(event)

            created = 0
            updated = 0
            for idx, (event_idx, section, row, seat, price) in enumerate(TICKET_SPECS[:count], start=1):
                event = events[event_idx]
                ticket, was_created = Ticket.objects.update_or_create(
                    seller=seller,
                    event=event,
                    seat_number=f'checkout-test-{idx}',
                    defaults={
                        'event_name': event.name,
                        'event_date': event.date,
                        'venue': event.venue_display_name(),
                        'custom_section_text': section,
                        'section_legacy': section,
                        'row': row,
                        'row_number': row,
                        'seat_numbers': seat,
                        'original_price': price,
                        'asking_price': price,
                        'available_quantity': 1,
                        'delivery_method': 'instant',
                        'ticket_type': 'כרטיס אלקטרוני / PDF',
                        'verification_status': 'מאומת',
                        'status': 'active',
                        'split_type': 'כל כמות',
                        'is_together': True,
                        'is_obstructed_view': False,
                        'listing_group_id': f'checkout-test-{event.pk}-{idx}',
                    },
                )
                if not ticket.pdf_file:
                    ticket.pdf_file.save(f'checkout-test-ticket-{idx}.pdf', ContentFile(PDF_BYTES), save=True)
                if was_created:
                    created += 1
                else:
                    updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{"Created" if was_created else "Updated"} ticket id={ticket.pk} '
                        f'event_id={event.pk} price={price} row={row} seat={seat}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. seller_id={seller.pk} created={created} updated={updated} active_checkout_test_tickets={count}'
            )
        )
