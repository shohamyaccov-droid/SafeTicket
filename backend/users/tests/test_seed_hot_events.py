"""Tests for seed_hot_events — verified Q3/Q4 2026 high-demand concerts."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from users.models import Artist, Event

TZ_IL = ZoneInfo('Asia/Jerusalem')


class SeedHotEventsTests(TestCase):
    def test_seed_creates_verified_high_demand_shows(self):
        call_command('seed_hot_events', skip_images=True)

        ribo = Event.objects.get(artist__name='ישי ריבו', date=datetime(2026, 9, 16, 21, 0, tzinfo=TZ_IL))
        self.assertEqual(ribo.name, 'ישי ריבו - מופע סימפוני')
        self.assertEqual(ribo.venue_place.name, 'אמפי MAX')
        self.assertEqual(ribo.city, 'ראשון לציון')
        self.assertTrue(ribo.high_demand)
        self.assertEqual(ribo.status, 'פעיל')

        tuna = Event.objects.get(artist__name='טונה', date=datetime(2026, 10, 17, 21, 0, tzinfo=TZ_IL))
        self.assertEqual(tuna.venue_place.name, 'זאפה אמפי שוני')
        self.assertEqual(tuna.city, 'בנימינה')

        agam = Event.objects.filter(artist__name='אגם בוחבוט', status='פעיל')
        self.assertEqual(agam.count(), 1)
        self.assertEqual(agam.get().date, datetime(2026, 10, 1, 21, 0, tzinfo=TZ_IL))

        hadag = Event.objects.filter(artist__name='הדג נחש', status='פעיל').order_by('date')
        self.assertEqual(hadag.count(), 2)
        self.assertEqual(hadag[0].venue_place.name, 'אמפי קיסריה')
        self.assertEqual(hadag[1].venue_place.name, 'זאפה אמפי שוני')
        self.assertFalse(
            Event.objects.filter(
                artist__name='הדג נחש',
                date=datetime(2026, 9, 30, 20, 30, tzinfo=TZ_IL),
            ).exists()
        )

        sarit = Event.objects.filter(artist__name='שרית חדד', status='פעיל').order_by('date')
        self.assertEqual(sarit.count(), 3)
        self.assertEqual(sarit[0].name, 'שרית חדד - 30 שנות מוזיקה')
        self.assertEqual(sarit[0].venue_place.name, 'פארק הירקון')

        festigal = Event.objects.get(artist__name='פסטיגל')
        self.assertEqual(festigal.category, 'festival')
        self.assertEqual(festigal.venue_place.name, 'אקספו תל אביב, ביתן 2')

        next_shows = Event.objects.filter(artist__name='NEXT', status='פעיל').order_by('date')
        self.assertEqual(next_shows.count(), 2)
        self.assertEqual(next_shows[0].venue_place.name, 'האצטדיון הלאומי רמת גן')
        self.assertEqual(next_shows[1].venue, 'פיס ארנה ירושלים')

        noam = Event.objects.get(artist__name='נועם בתן')
        self.assertEqual(noam.venue, 'היכל מנורה מבטחים')
        self.assertEqual(noam.name, 'נועם בתן - מופע בכורה')
        seeded_artists = (
            'חנן בן ארי',
            'ישי ריבו',
            'טונה',
            'פסטיגל',
            'הדג נחש',
            'נועם בתן',
            'אגם בוחבוט',
            'שרית חדד',
            'NEXT',
        )
        self.assertEqual(
            Event.objects.filter(artist__name__in=seeded_artists, high_demand=True).count(),
            14,
        )

    def test_seed_is_idempotent(self):
        call_command('seed_hot_events', skip_images=True)
        call_command('seed_hot_events', skip_images=True)
        self.assertEqual(Event.objects.filter(high_demand=True, artist__name='שרית חדד').count(), 3)
        self.assertEqual(Artist.objects.filter(name='ישי ריבו').count(), 1)

    def test_every_seeded_artist_has_a_wikimedia_image_url(self):
        from users.management.commands.seed_hot_events import ARTIST_IMAGE_URLS, SHOWS

        seeded = {spec.artist_name for spec in SHOWS}
        self.assertEqual(set(ARTIST_IMAGE_URLS), seeded)
        for name, url in ARTIST_IMAGE_URLS.items():
            self.assertTrue(url.startswith('https://'), name)
            self.assertNotIn('unsplash', url.lower(), name)
            self.assertTrue('wikimedia.org' in url or 'wikipedia.org' in url, name)


class HighDemandEventsApiTests(APITestCase):
    def setUp(self):
        self.api = APIClient()
        self.artist = Artist.objects.create(name='Hot API Artist')

    def test_high_demand_param_returns_only_flagged_upcoming_events(self):
        now = timezone.now()
        hot = Event.objects.create(
            name='Hot Show',
            artist=self.artist,
            date=now + timedelta(days=20),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
            high_demand=True,
        )
        Event.objects.create(
            name='Regular Show',
            artist=self.artist,
            date=now + timedelta(days=21),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
            high_demand=False,
        )
        res = self.api.get('/api/users/events/', {'high_demand': '1'})
        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names = [item['name'] for item in payload]
        self.assertIn(hot.name, names)
        self.assertNotIn('Regular Show', names)
        self.assertTrue(all(item.get('high_demand') for item in payload))
