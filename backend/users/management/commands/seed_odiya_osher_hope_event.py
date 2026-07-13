"""
Seed high-demand Menora event: עוצמה של תקווה - אודיה ואושר כהן (30.07.2026 19:00).

Venue field MUST be 'היכל מנורה מבטחים' so EventDetailsPage loads InteractiveMenoraMap.

Usage:
  cd backend
  python manage.py seed_odiya_osher_hope_event
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')

ARTIST_NAME = 'אודיה ואושר כהן'
EVENT_NAME = 'עוצמה של תקווה - אודיה ואושר כהן'
VENUE_CHOICE = 'היכל מנורה מבטחים'
VENUE_PLACE_NAME = 'היכל מנורה מבטחים'
VENUE_CITY = 'תל אביב'
EVENT_WHEN = datetime(2026, 7, 30, 19, 0, 0, tzinfo=TZ_IL)


class Command(BaseCommand):
    help = 'Create or update the Odiya & Osher Cohen Hope Power Menora event (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned row without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: would create {EVENT_NAME!r} @ {EVENT_WHEN.isoformat()} '
                    f'venue={VENUE_CHOICE!r} place={VENUE_PLACE_NAME}, {VENUE_CITY}'
                )
            )
            return

        with transaction.atomic():
            venue_place, venue_created = Venue.objects.get_or_create(
                name=VENUE_PLACE_NAME,
                city=VENUE_CITY,
            )
            artist, artist_created = Artist.objects.update_or_create(
                name=ARTIST_NAME,
                defaults={
                    'genre': 'Pop',
                    'description': 'אודיה ואושר כהן — הופעה משותפת',
                    'category': 'music',
                    'is_international': False,
                },
            )
            ev, event_created = Event.objects.update_or_create(
                artist=artist,
                date=EVENT_WHEN,
                defaults={
                    'name': EVENT_NAME,
                    'venue': VENUE_CHOICE,
                    'venue_place': venue_place,
                    'city': VENUE_CITY,
                    'category': 'concert',
                    'status': 'פעיל',
                    'country': 'IL',
                    'high_demand': True,
                },
            )

        if venue_created:
            self.stdout.write(self.style.SUCCESS(f'Created venue place: {venue_place.name} (id={venue_place.pk})'))
        if artist_created:
            self.stdout.write(self.style.SUCCESS(f'Created artist: {artist.name} (id={artist.pk})'))
        if event_created:
            self.stdout.write(self.style.SUCCESS(f'Created event: {ev.name} (id={ev.pk})'))
        else:
            self.stdout.write(self.style.NOTICE(f'Updated event: {ev.name} (id={ev.pk})'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. event_id={ev.pk} venue={ev.venue!r} '
                f'venue_place={ev.venue_place.name if ev.venue_place else None!r} '
                f'date={ev.date.astimezone(TZ_IL).isoformat()}'
            )
        )
