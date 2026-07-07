"""
Fix Event id=77 — Eden Ben Zaken at Menora Mivtachim, August 17 2026.

Usage:
  cd backend
  python manage.py fix_eden_ben_zaken_event
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')
EVENT_ID = 77
VENUE_MENORA = 'היכל מנורה מבטחים'


class Command(BaseCommand):
    help = 'Update Event 77 to Eden Ben Zaken at Menora on 2026-08-17.'

    def handle(self, *args, **options):
        ev = Event.objects.filter(pk=EVENT_ID).first()
        if not ev:
            self.stderr.write(self.style.ERROR(f'Event id={EVENT_ID} not found.'))
            return

        artist, _ = Artist.objects.get_or_create(
            name='עדן בן זקן',
            defaults={
                'genre': 'Pop',
                'description': 'Eden Ben Zaken — Israeli singer',
                'category': 'music',
                'is_international': False,
            },
        )
        venue_place, _ = Venue.objects.get_or_create(
            name=VENUE_MENORA,
            city='תל אביב',
        )
        when = datetime(2026, 8, 17, 21, 0, tzinfo=TZ_IL)

        ev.artist = artist
        ev.name = 'עדן בן זקן'
        ev.date = when
        ev.venue = VENUE_MENORA
        ev.venue_place = venue_place
        ev.city = 'תל אביב'
        ev.category = 'concert'
        ev.status = 'פעיל'
        ev.country = 'IL'
        ev.high_demand = True
        ev.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Updated event id={ev.pk}: {ev.name!r} @ {ev.venue} — {ev.date.isoformat()}'
            )
        )
