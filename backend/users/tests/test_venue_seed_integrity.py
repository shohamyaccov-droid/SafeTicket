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
        events = Event.objects.filter(artist=artist, venue='היכל מנורה מבטחים', status='פעיל').order_by('date')
        self.assertEqual(events.count(), 3)
        days = sorted(e.date.day for e in events)
        self.assertEqual(days, [17, 18, 20])
        self.assertTrue(all(e.city == 'תל אביב' for e in events))

    def test_seed_august_2026_creates_ben_tzur_caesarea_shows(self):
        call_command('seed_august_2026_concerts')
        artist = Artist.objects.filter(name='בן צור').first()
        self.assertIsNotNone(artist)
        self.assertEqual(artist.category, 'music')
        caesarea = Venue.objects.filter(name='אמפי קיסריה', city='קיסריה').first()
        self.assertIsNotNone(caesarea)
        events = Event.objects.filter(artist=artist, venue_place=caesarea, status='פעיל').order_by('date')
        self.assertEqual(events.count(), 2)
        days = sorted(e.date.day for e in events)
        self.assertEqual(days, [26, 27])
        self.assertTrue(all(e.high_demand for e in events))

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
