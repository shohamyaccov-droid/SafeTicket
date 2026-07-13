from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase

from users.models import Artist, Event

TZ_IL = ZoneInfo('Asia/Jerusalem')


class SeedOdiyaOsherHopeEventTests(TestCase):
    def test_seed_creates_menora_high_demand_event(self):
        call_command('seed_odiya_osher_hope_event')
        artist = Artist.objects.get(name='אודיה ואושר כהן')
        ev = Event.objects.get(artist=artist, date=datetime(2026, 7, 30, 19, 0, tzinfo=TZ_IL))
        self.assertEqual(ev.name, 'עוצמה של תקווה - אודיה ואושר כהן')
        self.assertEqual(ev.venue, 'היכל מנורה מבטחים')
        self.assertEqual(ev.venue_place.name, 'היכל מנורה מבטחים')
        self.assertEqual(ev.city, 'תל אביב')
        self.assertTrue(ev.high_demand)
        self.assertEqual(ev.status, 'פעיל')

    def test_seed_is_idempotent(self):
        call_command('seed_odiya_osher_hope_event')
        call_command('seed_odiya_osher_hope_event')
        self.assertEqual(Event.objects.filter(name='עוצמה של תקווה - אודיה ואושר כהן').count(), 1)
