"""
Seed active test tickets with minimal PDFs (authenticated Cloudinary / UUID storage).

Usage:
  python manage.py seed_test_tickets
  python manage.py seed_test_tickets --seller-email seller@example.com --event-id 3
"""
from __future__ import annotations

import re
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from users.models import Artist, Event, Ticket, Venue
from users.secure_ticket_storage import random_ticket_storage_name

User = get_user_model()

MINIMAL_PDF_BYTES = (
    b'%PDF-1.4\n'
    b'1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n'
    b'2 0 obj<< /Type /Pages /Kids [] /Count 0 >>endobj\n'
    b'trailer<< /Root 1 0 R >>\n'
    b'%%EOF\n'
)

TICKET_SPECS = (
    {'section': 'אזור בדיקה A', 'row': '1', 'seat': '101', 'price': Decimal('149'), 'qty': 1},
    {'section': 'אזור בדיקה B', 'row': '2', 'seat': '102', 'price': Decimal('179'), 'qty': 2},
    {'section': 'אזור בדיקה C', 'row': '3', 'seat': '103', 'price': Decimal('199'), 'qty': 1},
)


class Command(BaseCommand):
    help = 'Create 3 active test tickets with minimal PDFs for checkout/download verification.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seller-email',
            type=str,
            default='',
            help='Use this seller email if the user exists (otherwise first seller or dummy seller).',
        )
        parser.add_argument(
            '--event-id',
            type=int,
            default=None,
            help='Use this event id (must be active/upcoming). Otherwise first active upcoming event.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned actions without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = bool(options['dry_run'])
        seller_email = (options.get('seller_email') or '').strip().lower()
        event_id = options.get('event_id')
        now = timezone.now()

        if dry_run:
            seller = self._resolve_seller(seller_email, dry_run=True)
            event = self._resolve_event(event_id, now, dry_run=True)
            self.stdout.write(f'Would create 3 tickets for seller={seller} event={event}')
            for idx, spec in enumerate(TICKET_SPECS, start=1):
                self.stdout.write(
                    f'  #{idx}: section={spec["section"]} row={spec["row"]} '
                    f'seat={spec["seat"]} price={spec["price"]} qty={spec["qty"]}'
                )
            return

        with transaction.atomic():
            seller = self._resolve_seller(seller_email, dry_run=False)
            event = self._resolve_event(event_id, now, dry_run=False)
            listing_group_id = str(uuid.uuid4())
            created_rows: list[tuple[Ticket, bool]] = []

            for idx, spec in enumerate(TICKET_SPECS, start=1):
                seat_marker = f'seed-test-{idx}'
                ticket, was_created = Ticket.objects.update_or_create(
                    seller=seller,
                    event=event,
                    seat_number=seat_marker,
                    defaults={
                        'event_name': event.name,
                        'event_date': event.date,
                        'venue': event.venue_display_name()
                        if hasattr(event, 'venue_display_name')
                        else event.venue,
                        'custom_section_text': spec['section'],
                        'section_legacy': spec['section'],
                        'row': spec['row'],
                        'row_number': spec['row'],
                        'seat_numbers': spec['seat'],
                        'original_price': spec['price'],
                        'asking_price': spec['price'],
                        'available_quantity': spec['qty'],
                        'delivery_method': 'instant',
                        'ticket_type': 'כרטיס אלקטרוני / PDF',
                        'verification_status': 'מאומת',
                        'status': 'active',
                        'split_type': 'כל כמות',
                        'is_together': True,
                        'is_obstructed_view': False,
                        'listing_group_id': listing_group_id,
                    },
                )
                ticket.pdf_file.save(
                    random_ticket_storage_name('.pdf'),
                    ContentFile(MINIMAL_PDF_BYTES),
                    save=True,
                )
                ticket.refresh_from_db()
                created_rows.append((ticket, was_created))

                stored_name = ticket.pdf_file.name or ''
                if getattr(settings, 'USE_CLOUDINARY', False):
                    if not re.search(r'tickets/pdfs/[0-9a-f]{32}\.pdf$', stored_name.replace('\\', '/')):
                        raise CommandError(
                            f'Ticket {ticket.pk} pdf_file path does not look UUID-based: {stored_name!r}'
                        )

        self.stdout.write(self.style.SUCCESS('seed_test_tickets: ready (3 active tickets with PDFs)'))
        self.stdout.write(f'  seller_id={seller.pk} seller_email={seller.email}')
        event_label = (event.name or '').encode('ascii', 'replace').decode('ascii')
        self.stdout.write(f'  event_id={event.pk} event_name={event_label!r}')
        self.stdout.write(f'  listing_group_id={listing_group_id}')
        self.stdout.write(f'  cloudinary={"yes" if getattr(settings, "USE_CLOUDINARY", False) else "no (local media)"}')
        self.stdout.write('')
        self.stdout.write('Tickets (use these IDs on the frontend):')
        for ticket, was_created in created_rows:
            action = 'created' if was_created else 'updated'
            section = (ticket.custom_section_text or '').encode('ascii', 'replace').decode('ascii')
            event_label = (event.name or '').encode('ascii', 'replace').decode('ascii')
            self.stdout.write(
                f'  - [{action}] ticket_id={ticket.pk} | event_id={event.pk} | event_name={event_label!r} | '
                f'section={section!r} | row={ticket.row} | seat={ticket.seat_numbers} | '
                f'price={ticket.asking_price} | qty={ticket.available_quantity} | '
                f'pdf_storage_path={ticket.pdf_file.name}'
            )

    def _resolve_seller(self, seller_email: str, *, dry_run: bool):
        if seller_email:
            seller = User.objects.filter(email__iexact=seller_email).first()
            if seller:
                if seller.role != 'seller':
                    seller.role = 'seller'
                    if not dry_run:
                        seller.save(update_fields=['role'])
                return seller

        seller = (
            User.objects.filter(role='seller', is_active=True)
            .order_by('id')
            .first()
        )
        if seller:
            return seller

        if dry_run:
            return f'<new dummy seller {seller_email or "seed-test-seller@safeticket.com"}>'

        email = seller_email or 'seed-test-seller@safeticket.com'
        seller, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': 'seed_test_seller',
                'role': 'seller',
                'is_active': True,
                'is_email_verified': True,
                'is_verified_seller': True,
                'accepted_escrow_terms': True,
                'escrow_terms_accepted_at': timezone.now(),
                'account_holder_name': 'Seed Test Seller',
                'bank_name': '12',
                'branch_number': '345',
                'account_number': '987654321',
            },
        )
        if created:
            seller.set_unusable_password()
            seller.save(update_fields=['password'])
        elif seller.role != 'seller':
            seller.role = 'seller'
            seller.save(update_fields=['role'])
        return seller

    def _resolve_event(self, event_id: int | None, now, *, dry_run: bool):
        if event_id:
            event = Event.objects.filter(pk=event_id).first()
            if not event:
                raise CommandError(f'Event id={event_id} not found.')
            return event

        event = (
            Event.objects.filter(status='פעיל', date__gte=now)
            .select_related('artist')
            .order_by('date')
            .first()
        )
        if event:
            return event

        if dry_run:
            return '<new dummy event Seed Test Concert>'

        artist, _ = Artist.objects.get_or_create(
            name='Seed Test Artist',
            defaults={'genre': 'Pop', 'description': 'Auto-created for seed_test_tickets'},
        )
        venue_place, _ = Venue.objects.get_or_create(
            name='היכל מנורה מבטחים',
            defaults={'city': 'Tel Aviv'},
        )
        event = Event.objects.create(
            name='Seed Test Concert — Checkout',
            artist=artist,
            date=now + timedelta(days=30),
            venue='היכל מנורה מבטחים',
            venue_place=venue_place,
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        return event
