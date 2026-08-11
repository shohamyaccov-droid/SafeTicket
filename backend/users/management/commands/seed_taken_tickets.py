"""
Seed dummy Taken (נתפס) tickets for empty active events.

Purpose:
  - QA the taken map UI across venue SVGs
  - Marketing FOMO / social proof on events that otherwise show an empty map

Safety:
  - Only targets Events with status=פעיל that currently have ZERO tickets
  - Never creates or modifies tickets on events that already have inventory
    (available, taken, sold, etc.)

Usage:
  python manage.py seed_taken_tickets
  python manage.py seed_taken_tickets --dry-run
  python manage.py seed_taken_tickets --random-seed 42
  python manage.py seed_taken_tickets --limit 20
"""
from __future__ import annotations

import random
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from users.models import Event, Ticket
from users.secure_ticket_storage import random_ticket_storage_name
from users.ticket_status import TICKET_STATUS_TAKEN

User = get_user_model()

SEED_SELLER_EMAIL = 'taken_fomo_seed_user@example.com'
SEED_SELLER_USERNAME = 'taken_fomo_seed_user'

# Interactive Menora SVG IDs (InteractiveMenoraMap)
MENORA_SECTIONS = [
    'VIP',
    *[f'{n} Lower' for n in range(1, 13)],
    *[f'{n} Upper' for n in range(1, 13)],
]

# Caesarea Amphitheater SVG IDs (CaesareaMap)
CAESAREA_SECTIONS = [
    'אורקסטרה',
    *[f'{n} תחתון' for n in range(1, 7)],
    *[f'{n} אמצע' for n in range(1, 7)],
    *[f'{n} עליון' for n in range(1, 7)],
]

# Bloomfield stadium sport map block IDs
BLOOMFIELD_SECTIONS = [
    *[str(n) for n in range(201, 210)],
    *[str(n) for n in range(214, 217)],
    *[str(n) for n in range(221, 230)],
    *[str(n) for n in range(234, 237)],
    *[str(n) for n in range(301, 339)],
    *[str(n) for n in range(404, 407)],
    *[str(n) for n in range(419, 432)],
]

# Bloomfield concert map block IDs (BloomfieldConcertMap)
BLOOMFIELD_CONCERT_SECTIONS = [
    *[f'A{n}' for n in range(1, 7)],
    *[f'B{n}' for n in range(1, 6)],
    *[f'C{n}' for n in range(1, 6)],
    '106', '105', '104', '103', '102', '101',
    '42', '43', '44', '45', '46', '47',
    *[f'{n}A' for n in range(70, 81)],
    *[f'{n}B' for n in range(71, 81)],
]

# Ramat Gan InteractiveStadiumMap dbIds
RAMAT_GAN_SECTIONS = [
    '6A', '6C', 'B5', '13A', '13B', '13C', '6B', 'ACCESSIBLE',
    '16A', '16B', '16C', '11B', 'D12', 'A3', 'A2', 'A1', 'B4', '11A',
    'B6', 'C7', 'C8', 'C9', '9A', 'D14', 'D13', 'D11', 'D10', '9B',
    '4', '3', '2-3', '2', '1',
]

# Pais Arena Jerusalem wedge IDs
JERUSALEM_SECTIONS = [
    *[str(n) for n in range(101, 123)],
    *[str(n) for n in range(301, 331)],
]

GENERIC_SECTIONS = ['אזור A', 'אזור B', 'אזור C', 'יציע 1', 'יציע 2', 'יציע 3']

PRICES_ILS = [180, 220, 250, 280, 320, 350, 380, 420]

MINIMAL_PDF_BYTES = (
    b'%PDF-1.4\n'
    b'1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n'
    b'2 0 obj<< /Type /Pages /Kids [] /Count 0 >>endobj\n'
    b'trailer<< /Root 1 0 R >>\n'
    b'%%EOF\n'
)


def _venue_haystack(event: Event) -> str:
    parts: list[str] = []
    try:
        parts.append(event.venue_display_name() or '')
    except Exception:
        parts.append(str(getattr(event, 'venue', '') or ''))
    vp = getattr(event, 'venue_place', None)
    if vp is not None:
        parts.append(getattr(vp, 'name', '') or '')
    parts.append(str(getattr(event, 'venue', '') or ''))
    return ' '.join(parts).strip()


def _safe_log_text(value: str) -> str:
    """Avoid UnicodeEncodeError on Windows cp1252 consoles during manage.py output."""
    try:
        value.encode('ascii')
        return value
    except UnicodeEncodeError:
        return value.encode('ascii', errors='backslashreplace').decode('ascii')

def section_pool_for_event(event: Event) -> list[str]:
    """Pick SVG/map section IDs that match the event venue's interactive map."""
    hay = _venue_haystack(event)
    category = (getattr(event, 'category', None) or '').strip().lower()

    if 'בלומפילד' in hay and ('הופעות' in hay or category in ('concert', 'music', 'הופעה')):
        return list(BLOOMFIELD_CONCERT_SECTIONS)
    if 'בלומפילד' in hay:
        return list(BLOOMFIELD_SECTIONS)
    if 'מנורה' in hay or 'מבטחים' in hay:
        return list(MENORA_SECTIONS)
    if 'קיסריה' in hay:
        return list(CAESAREA_SECTIONS)
    if 'רמת גן' in hay:
        return list(RAMAT_GAN_SECTIONS)
    if 'ירושלים' in hay or 'פיס ארנה' in hay:
        return list(JERUSALEM_SECTIONS)
    return list(GENERIC_SECTIONS)


class Command(BaseCommand):
    help = (
        'Seed 4–6 status=taken dummy tickets on active events that currently have '
        'zero tickets (FOMO / map QA). Never touches events that already have tickets.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List empty events that would be seeded without writing.',
        )
        parser.add_argument(
            '--random-seed',
            type=int,
            default=None,
            help='Deterministic RNG seed (useful for tests).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Max number of empty events to seed (default: all).',
        )
        parser.add_argument(
            '--event-ids',
            type=str,
            default='',
            help='Optional comma-separated event IDs to consider (still must be empty).',
        )

    def handle(self, *args, **options):
        dry_run = bool(options['dry_run'])
        rng = (
            random.Random(options['random_seed'])
            if options.get('random_seed') is not None
            else random.Random()
        )
        limit = options.get('limit')
        ids_raw = (options.get('event_ids') or '').strip()

        empty_events = self._queryset_empty_active_events(ids_raw)
        if limit is not None and limit > 0:
            empty_events = empty_events[:limit]

        events = list(empty_events)
        if not events:
            self.stdout.write(self.style.WARNING('No empty active events found — nothing to seed.'))
            return

        self.stdout.write(f'Found {len(events)} empty active event(s).')
        if dry_run:
            for ev in events:
                pool = section_pool_for_event(ev)
                self.stdout.write(
                    f'  [dry-run] event_id={ev.pk} venue={_safe_log_text(_venue_haystack(ev))!r} '
                    f'would_create=4-6 taken tickets from pool_size={len(pool)}'
                )
            self.stdout.write(self.style.WARNING('Dry run complete — no tickets created.'))
            return

        seller = self._resolve_seed_seller()
        created_total = 0
        seeded_events = 0

        for ev in events:
            with transaction.atomic():
                # PostgreSQL forbids SELECT FOR UPDATE with GROUP BY (Count annotate).
                # Lock the event row first, then count tickets in a separate query.
                locked = (
                    Event.objects.select_for_update()
                    .select_related('venue_place', 'artist')
                    .filter(pk=ev.pk)
                    .first()
                )
                if locked is None:
                    continue
                ticket_count = Ticket.objects.filter(event_id=locked.pk).count()
                if ticket_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  skip event_id={ev.pk} — tickets appeared before seed (count={ticket_count})'
                        )
                    )
                    continue

                n = self._seed_taken_tickets_for_event(event=locked, seller=seller, rng=rng)
                created_total += n
                seeded_events += 1
                self.stdout.write(
                    f'  seeded event_id={ev.pk} taken_tickets={n} '
                    f'venue={_safe_log_text(_venue_haystack(ev))!r}'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'seed_taken_tickets: done — events={seeded_events} tickets={created_total}'
            )
        )

    def _queryset_empty_active_events(self, ids_raw: str):
        qs = (
            Event.objects.filter(status='פעיל')
            .annotate(ticket_count=Count('tickets'))
            .filter(ticket_count=0)
            .select_related('venue_place', 'artist')
            .order_by('id')
        )
        if ids_raw:
            ids = [int(p) for p in ids_raw.split(',') if p.strip().isdigit()]
            qs = qs.filter(id__in=ids)
        return qs

    def _resolve_seed_seller(self) -> User:
        seller, created = User.objects.get_or_create(
            email=SEED_SELLER_EMAIL,
            defaults={
                'username': SEED_SELLER_USERNAME,
                'role': 'seller',
                'is_active': True,
                'is_email_verified': True,
                'is_verified_seller': True,
                'accepted_escrow_terms': True,
                'escrow_terms_accepted_at': timezone.now(),
                'account_holder_name': 'Taken FOMO Seed',
                'bank_name': '12',
                'branch_number': '100',
                'account_number': '111222333',
            },
        )
        if created:
            seller.set_unusable_password()
            seller.save(update_fields=['password'])
        else:
            changed = False
            if seller.username != SEED_SELLER_USERNAME:
                seller.username = SEED_SELLER_USERNAME
                changed = True
            if seller.role != 'seller':
                seller.role = 'seller'
                changed = True
            if not seller.is_active:
                seller.is_active = True
                changed = True
            if changed:
                seller.save()
        return seller

    def _seed_taken_tickets_for_event(
        self,
        *,
        event: Event,
        seller: User,
        rng: random.Random,
    ) -> int:
        pool = section_pool_for_event(event)
        ticket_count = rng.randint(4, 6)
        k = min(ticket_count, len(pool))
        sections = rng.sample(pool, k=k)

        venue_label = ''
        try:
            venue_label = event.venue_display_name()
        except Exception:
            venue_label = str(getattr(event, 'venue', '') or '')

        created = 0
        for idx, section_id in enumerate(sections):
            price = Decimal(str(rng.choice(PRICES_ILS)))
            row = str(1 + (idx % 12))
            listing_group_id = str(uuid.uuid4())

            ticket = Ticket(
                seller=seller,
                event=event,
                event_name=event.name,
                event_date=event.date,
                venue=venue_label,
                custom_section_text=section_id,
                section_legacy=section_id,
                row=row,
                row_number=row,
                seat_numbers=str(idx + 1),
                seat_number=str(idx + 1),
                original_price=price,
                asking_price=price,
                available_quantity=0,
                delivery_method='instant',
                ticket_type='כרטיס אלקטרוני / PDF',
                verification_status='מאומת',
                status=TICKET_STATUS_TAKEN,
                is_together=True,
                split_type='כל כמות',
                listing_group_id=listing_group_id,
            )
            ticket.pdf_file.save(
                random_ticket_storage_name('.pdf'),
                ContentFile(MINIMAL_PDF_BYTES),
                save=False,
            )
            ticket.save()
            created += 1

        return created
