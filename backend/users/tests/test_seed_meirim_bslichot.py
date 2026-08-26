"""Tests for מאירים בסליחות hub + ASCII event slugs."""
from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from users.meirim_bslichot import (
    ARTIST_NAME,
    ARTIST_SLUG,
    SHOW_DATES,
    VENUE_CITY,
    VENUE_PLACE_NAME,
    expected_event_slug,
    seed_meirim_bslichot,
)
from users.models import Artist, Event, Venue
from users.seo import build_artist_slug_base


class SeedMeirimBslichotTests(TestCase):
    def test_seed_creates_hub_and_four_ascii_event_slugs(self):
        result = seed_meirim_bslichot(attach_poster=False)
        artist = result['artist']
        self.assertEqual(artist.name, ARTIST_NAME)
        self.assertEqual(artist.slug, ARTIST_SLUG)
        self.assertEqual(build_artist_slug_base(artist), ARTIST_SLUG)

        venue = Venue.objects.get(name=VENUE_PLACE_NAME, city=VENUE_CITY)
        events = list(Event.objects.filter(artist=artist).order_by('date'))
        self.assertEqual(len(events), 4)
        for ev, when in zip(events, SHOW_DATES, strict=True):
            self.assertEqual(ev.date, when)
            self.assertEqual(ev.name, ARTIST_NAME)
            self.assertEqual(ev.city, VENUE_CITY)
            self.assertEqual(ev.venue_place_id, venue.pk)
            self.assertEqual(ev.status, 'פעיל')
            self.assertTrue(ev.high_demand)
            self.assertEqual(ev.slug, expected_event_slug(when))
            self.assertTrue(all(ord(c) < 128 for c in ev.slug), ev.slug)

    def test_command_is_idempotent(self):
        call_command('seed_meirim_bslichot')
        call_command('seed_meirim_bslichot')
        artist = Artist.objects.get(slug=ARTIST_SLUG)
        self.assertEqual(Event.objects.filter(artist=artist).count(), 4)

    def test_api_hub_and_event_lookup(self):
        seed_meirim_bslichot(attach_poster=False)
        client = APIClient()
        hub = client.get(f'/api/users/artists/{ARTIST_SLUG}/')
        self.assertEqual(hub.status_code, 200, hub.content)
        self.assertEqual(hub.data['slug'], ARTIST_SLUG)

        slug = expected_event_slug(SHOW_DATES[0])
        ev = client.get(f'/api/users/events/{slug}/')
        self.assertEqual(ev.status_code, 200, ev.content)
        self.assertEqual(ev.data['slug'], slug)
        self.assertTrue(ev.data['canonical_url'].endswith(f'/event/{slug}'))
