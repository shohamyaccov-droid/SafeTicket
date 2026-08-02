"""
Seed איתי לוי concerts at Caesarea Amphitheater (Aug/Sep 2026).

Does NOT touch the existing Menora show (15.08.2026). Venue FK uses the
canonical place name "אמפי קיסריה" so CaesareaMap / sell sections match.

Usage:
  cd backend
  python manage.py seed_itay_levi_caesarea

  python manage.py seed_itay_levi_caesarea --dry-run
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')

ARTIST_NAME = 'איתי לוי'
# CharField choice — display name comes from venue_place (same as other Caesarea seeds)
VENUE_CHOICE = 'ישראל'
VENUE_PLACE_NAME = 'אמפי קיסריה'
VENUE_CITY = 'קיסריה'
EVENT_NAME_BASE = 'איתי לוי - אמפי קיסריה'

# (year, month, day, hour, minute) — Israel local time
SHOWS_2026 = (
    (2026, 8, 29, 21, 0),
    (2026, 9, 1, 20, 45),
)


def _dt(y: int, m: int, d: int, h: int, minute: int) -> datetime:
    return datetime(y, m, d, h, minute, 0, tzinfo=TZ_IL)


def _event_title(when: datetime) -> str:
    return f'{EVENT_NAME_BASE} — {when.strftime("%d.%m.%Y")}'


class Command(BaseCommand):
    help = 'Create or update Itay Levi Caesarea Amphitheater concerts (29.08 & 01.09.2026).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned rows without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        planned = []
        for y, m, d, h, minute in SHOWS_2026:
            when = _dt(y, m, d, h, minute)
            planned.append({'name': _event_title(when), 'date': when})

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no database changes.'))
            self.stdout.write(f'Artist: {ARTIST_NAME}')
            self.stdout.write(f'venue={VENUE_CHOICE!r} place={VENUE_PLACE_NAME}, {VENUE_CITY}')
            for row in planned:
                self.stdout.write(f"  - {row['name']} @ {row['date'].isoformat()}")
            return

        venue_place, _ = Venue.objects.get_or_create(name=VENUE_PLACE_NAME, city=VENUE_CITY)
        artist, artist_created = Artist.objects.update_or_create(
            name=ARTIST_NAME,
            defaults={
                'genre': 'Mizrahi',
                'description': 'Itay Levi — Israeli singer',
                'category': 'music',
                'is_international': False,
            },
        )

        created = 0
        updated = 0
        event_ids: list[int] = []

        with transaction.atomic():
            for row in planned:
                ev, was_created = Event.objects.update_or_create(
                    artist=artist,
                    date=row['date'],
                    defaults={
                        'name': row['name'],
                        'venue': VENUE_CHOICE,
                        'venue_place': venue_place,
                        'city': VENUE_CITY,
                        'category': 'concert',
                        'status': 'פעיל',
                        'country': 'IL',
                        'high_demand': True,
                    },
                )
                event_ids.append(ev.pk)
                if was_created:
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created event id={ev.pk} date={row["date"].isoformat()}')
                    )
                else:
                    updated += 1
                    self.stdout.write(
                        self.style.NOTICE(f'Updated event id={ev.pk} date={row["date"].isoformat()}')
                    )

        if artist_created:
            self.stdout.write(self.style.SUCCESS(f'Created artist id={artist.pk}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. artist_id={artist.pk}, venue_place_id={venue_place.pk}, '
                f'created={created}, updated={updated}, event_ids={event_ids}'
            )
        )
