"""
Seed אייל גולן concerts at Bloomfield Stadium (June 2026).

Usage:
  cd backend
  python manage.py seed_eyal_golan

  python manage.py seed_eyal_golan --dry-run
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')

ARTIST_NAME = 'אייל גולן'
VENUE_LABEL = 'אצטדיון בלומפילד (הופעות)'
VENUE_PLACE_NAME = 'אצטדיון בלומפילד'
VENUE_CITY = 'תל אביב'
EVENT_NAME_BASE = 'אייל גולן - אצטדיון בלומפילד'

# (year, month, day, hour, minute)
SHOWS_2026 = (
    (2026, 6, 11, 20, 0),
    (2026, 6, 13, 21, 0),
    (2026, 6, 14, 20, 0),
    (2026, 6, 18, 20, 0),
)


def _dt(y: int, m: int, d: int, h: int, minute: int) -> datetime:
    return datetime(y, m, d, h, minute, 0, tzinfo=TZ_IL)


def _event_title(when: datetime) -> str:
    return f'{EVENT_NAME_BASE} — {when.strftime("%d.%m.%Y")}'


class Command(BaseCommand):
    help = 'Create or update Eyal Golan Bloomfield Stadium concert events (June 2026).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned rows without writing to the database.',
        )
        parser.add_argument(
            '--no-high-demand',
            action='store_true',
            help='Do not set high_demand on events (default: high_demand=True).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        high_demand = not options['no_high_demand']

        planned = []
        for y, m, d, h, minute in SHOWS_2026:
            when = _dt(y, m, d, h, minute)
            planned.append(
                {
                    'name': _event_title(when),
                    'date': when,
                    'status': 'פעיל',
                }
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no database changes.'))
            self.stdout.write(f'Artist: {ARTIST_NAME}')
            self.stdout.write(f'Venue place: {VENUE_PLACE_NAME}, {VENUE_CITY}')
            self.stdout.write(f'venue field: {VENUE_LABEL} | high_demand: {high_demand}')
            for row in planned:
                self.stdout.write(
                    f"  - {row['name']} @ {row['date'].isoformat()} status={row['status']}"
                )
            return

        venue_place, _ = Venue.objects.get_or_create(
            name=VENUE_PLACE_NAME,
            city=VENUE_CITY,
        )

        artist, _ = Artist.objects.get_or_create(
            name=ARTIST_NAME,
            defaults={'genre': 'Mizrahi', 'description': 'Israeli Mizrahi pop artist'},
        )

        created = 0
        updated = 0

        with transaction.atomic():
            for row in planned:
                ev, was_created = Event.objects.update_or_create(
                    artist=artist,
                    date=row['date'],
                    defaults={
                        'name': row['name'],
                        'venue': VENUE_LABEL,
                        'venue_place': venue_place,
                        'city': VENUE_CITY,
                        'category': 'concert',
                        'status': row['status'],
                        'country': 'IL',
                        'high_demand': high_demand,
                    },
                )
                if was_created:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f'Created: {ev.name} (id={ev.pk})'))
                else:
                    updated += 1
                    self.stdout.write(self.style.NOTICE(f'Updated: {ev.name} (id={ev.pk})'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. artist_id={artist.pk}, venue_place_id={venue_place.pk}, '
                f'created={created}, updated={updated}, total_shows={len(planned)}'
            )
        )
