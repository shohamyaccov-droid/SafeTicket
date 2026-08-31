"""Tests for seed_sports — Q3/Q4 2026 high-demand football and basketball."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from users.management.commands.seed_sports import (
    MATCHES,
    TEAM_BEITAR,
    TEAM_HAPOEL_BS,
    TEAM_HAPOEL_JLM,
    TEAM_HAPOEL_TA,
    TEAM_MACCABI_HAIFA,
    TEAM_MACCABI_TA,
)
from users.models import Artist, Event

TZ_IL = ZoneInfo('Asia/Jerusalem')

SEEDED_TEAMS = (
    TEAM_MACCABI_HAIFA,
    TEAM_MACCABI_TA,
    TEAM_BEITAR,
    TEAM_HAPOEL_BS,
    TEAM_HAPOEL_TA,
    TEAM_HAPOEL_JLM,
)


class SeedSportsTests(TestCase):
    def test_seed_creates_high_demand_football_and_basketball(self):
        call_command('seed_sports', skip_images=True)

        derby = Event.objects.get(
            artist__name=TEAM_MACCABI_TA,
            date=datetime(2026, 9, 14, 20, 30, tzinfo=TZ_IL),
        )
        self.assertEqual(derby.name, f'{TEAM_MACCABI_TA} נגד {TEAM_HAPOEL_TA}')
        self.assertEqual(derby.category, 'football')
        self.assertEqual(derby.home_team, TEAM_MACCABI_TA)
        self.assertEqual(derby.away_team, TEAM_HAPOEL_TA)
        self.assertEqual(derby.venue, 'אצטדיון בלומפילד')
        self.assertTrue(derby.high_demand)
        self.assertEqual(derby.status, 'פעיל')

        turner = Event.objects.get(
            artist__name=TEAM_HAPOEL_BS,
            date=datetime(2026, 9, 7, 20, 30, tzinfo=TZ_IL),
        )
        self.assertEqual(turner.venue_place.name, 'אצטדיון טוטו טרנר')
        self.assertEqual(turner.city, 'באר שבע')
        self.assertEqual(turner.away_team, TEAM_MACCABI_TA)

        euro_derby = Event.objects.get(
            artist__name=TEAM_MACCABI_TA,
            date=datetime(2026, 11, 12, 21, 5, tzinfo=TZ_IL),
        )
        self.assertEqual(euro_derby.category, 'basketball')
        self.assertEqual(euro_derby.tournament, 'יורוליג')
        self.assertEqual(euro_derby.away_team, TEAM_HAPOEL_TA)
        self.assertEqual(euro_derby.venue, 'היכל מנורה מבטחים')

        self.assertEqual(Event.objects.filter(category='football').count(), 12)
        self.assertEqual(Event.objects.filter(category='basketball').count(), 12)
        self.assertEqual(
            Event.objects.filter(category__in=('football', 'basketball'), high_demand=True).count(),
            len(MATCHES),
        )

        for name in SEEDED_TEAMS:
            artist = Artist.objects.get(name=name)
            self.assertEqual(artist.category, 'sports')
            self.assertFalse(artist.is_international)

        self.assertEqual(Artist.objects.filter(name=TEAM_BEITAR).count(), 1)
        self.assertTrue(
            Event.objects.filter(home_team=TEAM_BEITAR, away_team=TEAM_MACCABI_TA).exists()
        )
        self.assertTrue(
            Event.objects.filter(
                category='basketball',
                home_team=TEAM_HAPOEL_TA,
                away_team=TEAM_HAPOEL_JLM,
            ).exists()
        )
        # Away Euroleague games must not be seeded (no Israeli stadium).
        self.assertFalse(Event.objects.filter(away_team='בשיקטאש', city='איסטנבול').exists())
        self.assertFalse(
            Event.objects.filter(home_team='וילרבאן').exists()
        )

    def test_seed_is_idempotent(self):
        call_command('seed_sports', skip_images=True)
        call_command('seed_sports', skip_images=True)
        self.assertEqual(Event.objects.filter(high_demand=True, category='football').count(), 12)
        self.assertEqual(Event.objects.filter(high_demand=True, category='basketball').count(), 12)
        self.assertEqual(Artist.objects.filter(name=TEAM_MACCABI_TA).count(), 1)
        self.assertEqual(Artist.objects.filter(name=TEAM_BEITAR).count(), 1)
        self.assertEqual(Artist.objects.filter(name=TEAM_HAPOEL_JLM).count(), 1)

    def test_every_seeded_team_has_a_wikimedia_crest_url(self):
        from users.management.commands.seed_sports import TEAM_IMAGE_URLS, TEAM_NAMES

        self.assertEqual(set(TEAM_IMAGE_URLS), set(TEAM_NAMES))
        for name, url in TEAM_IMAGE_URLS.items():
            self.assertTrue(url.startswith('https://'), name)
            self.assertNotIn('unsplash', url.lower(), name)
            self.assertTrue('wikimedia.org' in url or 'wikipedia.org' in url, name)


class SportsEventsApiTests(APITestCase):
    def setUp(self):
        self.api = APIClient()
        self.home = Artist.objects.create(name=TEAM_MACCABI_TA, category='sports')
        self.other = Artist.objects.create(name='Regular Concert Artist', category='music')

    def test_category_and_high_demand_filters(self):
        now = timezone.now()
        football = Event.objects.create(
            name=f'{TEAM_MACCABI_TA} נגד {TEAM_HAPOEL_TA}',
            artist=self.home,
            date=now + timedelta(days=20),
            venue='אצטדיון בלומפילד',
            city='תל אביב',
            country='IL',
            category='football',
            status='פעיל',
            high_demand=True,
            home_team=TEAM_MACCABI_TA,
            away_team=TEAM_HAPOEL_TA,
        )
        basketball = Event.objects.create(
            name=f'{TEAM_MACCABI_TA} נגד {TEAM_HAPOEL_TA}',
            artist=self.home,
            date=now + timedelta(days=40),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='basketball',
            status='פעיל',
            high_demand=True,
            home_team=TEAM_MACCABI_TA,
            away_team=TEAM_HAPOEL_TA,
        )
        Event.objects.create(
            name='Cold Concert',
            artist=self.other,
            date=now + timedelta(days=21),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
            high_demand=True,
        )
        Event.objects.create(
            name='Regular Football',
            artist=self.home,
            date=now + timedelta(days=25),
            venue='אצטדיון בלומפילד',
            city='תל אביב',
            country='IL',
            category='football',
            status='פעיל',
            high_demand=False,
        )

        res = self.api.get(
            '/api/users/events/',
            {'high_demand': '1', 'category': 'football,basketball'},
        )
        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names_cats = {(item['name'], item['category']) for item in payload}
        self.assertIn((football.name, 'football'), names_cats)
        self.assertIn((basketball.name, 'basketball'), names_cats)
        self.assertTrue(all(item.get('high_demand') and item.get('is_hot') for item in payload))
        self.assertTrue(all(item['category'] in ('football', 'basketball') for item in payload))
        self.assertFalse(any(item['category'] == 'concert' for item in payload))

        football_only = self.api.get('/api/users/events/', {'category': 'football'})
        self.assertEqual(football_only.status_code, 200, football_only.content)
        football_payload = (
            football_only.data
            if isinstance(football_only.data, list)
            else football_only.data.get('results', [])
        )
        self.assertTrue(all(item['category'] == 'football' for item in football_payload))
        self.assertGreaterEqual(len(football_payload), 2)
