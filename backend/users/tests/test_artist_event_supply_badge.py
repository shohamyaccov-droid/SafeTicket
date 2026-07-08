"""Tests for artist event supply badge tie-break (earliest date wins)."""
from django.test import SimpleTestCase

from users.tests._artist_event_supply import pick_most_supply_event_id


class ArtistEventSupplyBadgeTests(SimpleTestCase):
    def test_single_max_gets_badge(self):
        events = [
            {'id': 1, 'tickets_count': 5, 'date': '2026-08-20T18:00:00Z'},
            {'id': 2, 'tickets_count': 10, 'date': '2026-08-15T18:00:00Z'},
        ]
        self.assertEqual(pick_most_supply_event_id(events), 2)

    def test_tie_picks_earliest_date(self):
        events = [
            {'id': 1, 'tickets_count': 10, 'date': '2026-08-20T18:00:00Z'},
            {'id': 2, 'tickets_count': 10, 'date': '2026-08-13T18:00:00Z'},
            {'id': 3, 'tickets_count': 3, 'date': '2026-08-10T18:00:00Z'},
        ]
        self.assertEqual(pick_most_supply_event_id(events), 2)

    def test_zero_supply_returns_none(self):
        events = [
            {'id': 1, 'tickets_count': 0, 'date': '2026-08-20T18:00:00Z'},
        ]
        self.assertIsNone(pick_most_supply_event_id(events))
