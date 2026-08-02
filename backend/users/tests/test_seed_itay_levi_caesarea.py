"""Tests for seed_itay_levi_caesarea — two Caesarea shows only (not Menora)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')


class SeedItayLeviCaesareaTests(TestCase):
    def test_seed_creates_two_caesarea_events(self):
        call_command('seed_itay_levi_caesarea')

        artist = Artist.objects.get(name='איתי לוי')
        venue = Venue.objects.get(name='אמפי קיסריה', city='קיסריה')
        events = list(
            Event.objects.filter(artist=artist, venue_place=venue, status='פעיל').order_by('date')
        )
        self.assertEqual(len(events), 2)

        expected = (
            datetime(2026, 8, 29, 21, 0, tzinfo=TZ_IL),
            datetime(2026, 9, 1, 20, 45, tzinfo=TZ_IL),
        )
        for ev, when in zip(events, expected, strict=True):
            self.assertEqual(ev.date, when)
            self.assertEqual(ev.venue, 'ישראל')
            self.assertEqual(ev.city, 'קיסריה')
            self.assertEqual(ev.category, 'concert')
            self.assertEqual(ev.country, 'IL')
            self.assertTrue(ev.high_demand)
            self.assertIn('אמפי קיסריה', ev.name)

    def test_seed_is_idempotent(self):
        call_command('seed_itay_levi_caesarea')
        call_command('seed_itay_levi_caesarea')
        artist = Artist.objects.get(name='איתי לוי')
        self.assertEqual(
            Event.objects.filter(artist=artist, city='קיסריה', status='פעיל').count(),
            2,
        )

    def test_does_not_create_or_cancel_menora_show(self):
        menora_venue, _ = Venue.objects.get_or_create(
            name='היכל מנורה מבטחים',
            city='תל אביב',
        )
        artist, _ = Artist.objects.get_or_create(
            name='איתי לוי',
            defaults={'genre': 'Mizrahi', 'category': 'music'},
        )
        menora = Event.objects.create(
            artist=artist,
            name='איתי לוי - היכל מנורה מבטחים — 15.08.2026',
            date=datetime(2026, 8, 15, 21, 30, tzinfo=TZ_IL),
            venue='היכל מנורה מבטחים',
            venue_place=menora_venue,
            city='תל אביב',
            category='concert',
            status='פעיל',
            country='IL',
        )

        call_command('seed_itay_levi_caesarea')

        menora.refresh_from_db()
        self.assertEqual(menora.status, 'פעיל')
        self.assertEqual(menora.venue, 'היכל מנורה מבטחים')
        self.assertEqual(
            Event.objects.filter(artist=artist, city='קיסריה', status='פעיל').count(),
            2,
        )
