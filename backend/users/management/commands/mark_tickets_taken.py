"""
Mark previously seeded / test tickets as permanently Taken (נתפס).

Usage:
  python manage.py mark_tickets_taken
  python manage.py mark_tickets_taken --dry-run
  python manage.py mark_tickets_taken --ticket-ids 1,2,3
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Q

from users.models import Ticket
from users.ticket_status import TICKET_STATUS_TAKEN


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
            '--all-active-test-sections',
            action='store_true',
            default=True,
            help='Mark tickets whose section looks like seed_test_tickets (אזור בדיקה).',
        )

    def handle(self, *args, **options):
        dry_run = bool(options['dry_run'])
        ids_raw = (options.get('ticket_ids') or '').strip()

        if ids_raw:
            ids = []
            for part in ids_raw.split(','):
                part = part.strip()
                if part.isdigit():
                    ids.append(int(part))
            qs = Ticket.objects.filter(id__in=ids).exclude(
                status__in=('sold', 'paid_out', 'rejected', 'pending_payout')
            )
        else:
            qs = Ticket.objects.filter(
                Q(custom_section_text__icontains='אזור בדיקה')
                | Q(section_legacy__icontains='אזור בדיקה')
                | Q(seat_row__icontains='אזור בדיקה')
            ).exclude(status__in=('sold', 'paid_out', 'rejected', 'pending_payout', TICKET_STATUS_TAKEN))

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('No matching tickets found to mark as taken.'))
            return

        for t in qs.order_by('id')[:50]:
            section = t.custom_section_text or t.section_legacy or t.seat_row or ''
            # Avoid Windows console UnicodeEncodeError on Hebrew section labels
            safe_section = section.encode('ascii', 'backslashreplace').decode('ascii')
            self.stdout.write(
                f'  id={t.id} status={t.status} event={getattr(t.event, "id", None)} '
                f'section={safe_section}'
            )
        if count > 50:
            self.stdout.write(f'  ... and {count - 50} more')

        if dry_run:
            self.stdout.write(self.style.WARNING(f'Dry run — would mark {count} ticket(s) as taken.'))
            return

        updated = qs.update(status=TICKET_STATUS_TAKEN)
        self.stdout.write(self.style.SUCCESS(f'Marked {updated} ticket(s) as taken.'))
