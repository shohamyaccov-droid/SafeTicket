"""
Venue catalog / seed integrity for Caesarea + Menora map venues.
"""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from users.models import Artist, Event, Venue, VenueSection


class VenueSeedIntegrityTests(TestCase):
    def test_seed_caesarea_sections_creates_19_rows(self):
        call_command('seed_caesarea_sections')
        venue = Venue.objects.filter(name__icontains='קיסריה').first()
        self.assertIsNotNone(venue, 'Caesarea venue should exist after seed')
        count = VenueSection.objects.filter(venue=venue).count()
        self.assertGreaterEqual(count, 19, f'Expected >=19 Caesarea sections, got {count}')

    def test_seed_august_2026_places_eden_at_menora(self):
        call_command('seed_august_2026_concerts')
        artist = Artist.objects.filter(name='עדן בן זקן').first()
        self.assertIsNotNone(artist)
        events = Event.objects.filter(artist=artist).order_by('date')
        self.assertTrue(events.exists())
        target = events.filter(date__date=timezone.datetime(2026, 8, 17).date()).first()
        if target is None:
            # Some DBs store aware datetimes — match by month/day
            target = next(
                (e for e in events if e.date.month == 8 and e.date.day == 17),
                events.first(),
            )
        self.assertIsNotNone(target)
        self.assertEqual(target.venue, 'היכל מנורה מבטחים')
        self.assertEqual(target.city, 'תל אביב')

    def test_fix_eden_ben_zaken_event_command_is_idempotent(self):
        artist = Artist.objects.create(name='עדן בן זקן')
        venue_place, _ = Venue.objects.get_or_create(
            name='היכל מנורה מבטחים',
            city='תל אביב',
        )
        Event.objects.filter(pk=77).delete()
        ev = Event(
            id=77,
            artist=artist,
            name='wrong title',
            date=timezone.now() + timedelta(days=1),
            venue='אחר',
            city='תל אביב',
            category='concert',
            status='פעיל',
            country='IL',
        )
        ev.save()

        call_command('fix_eden_ben_zaken_event')
        ev.refresh_from_db()
        self.assertEqual(ev.name, 'עדן בן זקן')
        self.assertEqual(ev.venue, 'היכל מנורה מבטחים')
        self.assertEqual(ev.date.month, 8)
        self.assertEqual(ev.date.day, 17)
        self.assertEqual(ev.venue_place_id, venue_place.id)
