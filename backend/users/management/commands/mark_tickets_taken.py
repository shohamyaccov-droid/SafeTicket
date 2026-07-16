"""
Mark previously seeded / test tickets as permanently Taken (נתפס).

Targets (OR-combined when no --ticket-ids):
  - Tickets with seed_test_tickets section labels (אזור בדיקה)
  - Tickets owned by the dummy seller system_seed_user
  - Active tickets on explicit event IDs (default includes production Eden Ben Zaken id=83)
  - Active tickets on Eden Ben Zaken events (artist-name fallback when IDs differ)

Usage:
  python manage.py mark_tickets_taken
  python manage.py mark_tickets_taken --dry-run
  python manage.py mark_tickets_taken --ticket-ids 1,2,3
  python manage.py mark_tickets_taken --event-ids 83,84
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q

from users.models import Event, Ticket
from users.ticket_status import TICKET_STATUS_TAKEN

User = get_user_model()

# Production Eden Ben Zaken event that still showed blue "קנה עכשיו" after taken-lock shipped.
DEFAULT_EVENT_IDS = (83,)
SEED_SELLER_EMAIL = 'system_seed_user@example.com'
SEED_SELLER_USERNAME = 'system_seed_user'
EDEN_ARTIST_NAME = 'עדן בן זקן'

TERMINAL_STATUSES = ('sold', 'paid_out', 'rejected', 'pending_payout', TICKET_STATUS_TAKEN)


class Command(BaseCommand):
    help = 'Mark seeded/test marketplace tickets as status=taken (נתפס).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List matching tickets without updating.',
        )
        parser.add_argument(
            '--ticket-ids',
            type=str,
            default='',
            help='Comma-separated ticket IDs to mark (skips auto-detection).',
        )
        parser.add_argument(
            '--event-ids',
            type=str,
            default=','.join(str(i) for i in DEFAULT_EVENT_IDS),
            help='Comma-separated event IDs whose active tickets should be marked taken '
            f'(default: {",".join(str(i) for i in DEFAULT_EVENT_IDS)}).',
        )
        parser.add_argument(
            '--skip-eden-artist-fallback',
            action='store_true',
            help='Do not also match Eden Ben Zaken events by artist name.',
        )
        parser.add_argument(
            '--skip-seed-seller',
            action='store_true',
            help='Do not mark tickets owned by system_seed_user.',
        )

    def handle(self, *args, **options):
        dry_run = bool(options['dry_run'])
        ids_raw = (options.get('ticket_ids') or '').strip()

        if ids_raw:
            ids = [int(part) for part in ids_raw.split(',') if part.strip().isdigit()]
            qs = Ticket.objects.filter(id__in=ids).exclude(status__in=TERMINAL_STATUSES)
        else:
            qs = self._auto_detect_queryset(options)

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('No matching tickets found to mark as taken.'))
            return

        for t in qs.select_related('event', 'seller').order_by('id')[:80]:
            section = t.custom_section_text or t.section_legacy or t.seat_row or ''
            safe_section = section.encode('ascii', 'backslashreplace').decode('ascii')
            seller = getattr(t.seller, 'username', None) or getattr(t.seller, 'email', '') or ''
            self.stdout.write(
                f'  id={t.id} status={t.status} event={getattr(t.event, "id", None)} '
                f'seller={seller} section={safe_section}'
            )
        if count > 80:
            self.stdout.write(f'  ... and {count - 80} more')

        if dry_run:
            self.stdout.write(self.style.WARNING(f'Dry run — would mark {count} ticket(s) as taken.'))
            return

        updated = qs.update(status=TICKET_STATUS_TAKEN, available_quantity=0)
        self.stdout.write(self.style.SUCCESS(f'Marked {updated} ticket(s) as taken.'))

    def _parse_event_ids(self, raw: str) -> list[int]:
        ids: list[int] = []
        for part in (raw or '').split(','):
            part = part.strip()
            if part.isdigit():
                ids.append(int(part))
        return ids

    def _auto_detect_queryset(self, options):
        q = Q(custom_section_text__icontains='אזור בדיקה')
        q |= Q(section_legacy__icontains='אזור בדיקה')
        q |= Q(seat_row__icontains='אזור בדיקה')

        if not options.get('skip_seed_seller'):
            seed_sellers = User.objects.filter(
                Q(email__iexact=SEED_SELLER_EMAIL) | Q(username=SEED_SELLER_USERNAME)
            )
            if seed_sellers.exists():
                q |= Q(seller_id__in=list(seed_sellers.values_list('id', flat=True)))

        event_ids = set(self._parse_event_ids(options.get('event_ids') or ''))
        if not options.get('skip_eden_artist_fallback'):
            eden_ids = Event.objects.filter(artist__name=EDEN_ARTIST_NAME).values_list('id', flat=True)
            event_ids.update(int(pk) for pk in eden_ids)

        if event_ids:
            q |= Q(event_id__in=list(event_ids))

        return (
            Ticket.objects.filter(q)
            .exclude(status__in=TERMINAL_STATUSES)
            .distinct()
        )
