from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase

from users.models import Artist, Event

TZ_IL = ZoneInfo('Asia/Jerusalem')

SHOWS = (
    datetime(2026, 9, 6, 20, 45, tzinfo=TZ_IL),
    datetime(2026, 9, 7, 20, 45, tzinfo=TZ_IL),
    datetime(2026, 9, 8, 20, 45, tzinfo=TZ_IL),
    datetime(2026, 9, 10, 20, 45, tzinfo=TZ_IL),
)


class SeedEyalGolanMenoraTests(TestCase):
    def test_seed_creates_four_menora_shows(self):
        call_command('seed_eyal_golan_menora')
        artist = Artist.objects.get(name='אייל גולן')
        events = Event.objects.filter(artist=artist, venue='היכל מנורה מבטחים', status='פעיל').order_by('date')
        self.assertEqual(events.count(), 4)
        for ev, when in zip(events, SHOWS, strict=True):
            self.assertEqual(ev.date, when)
            self.assertIn('אייל גולן במנורה', ev.name)
            self.assertEqual(ev.venue_place.name, 'היכל מנורה מבטחים')
            self.assertTrue(ev.high_demand)

    def test_seed_is_idempotent(self):
        call_command('seed_eyal_golan_menora')
        call_command('seed_eyal_golan_menora')
        self.assertEqual(
            Event.objects.filter(artist__name='אייל גולן', venue='היכל מנורה מבטחים').count(),
            4,
        )
