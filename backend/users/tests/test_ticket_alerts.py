"""
Tests for TicketAlert subscribe API (event + artist scopes) and quantity matching.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket, TicketAlert, Venue
from users.ticket_alert_matching import (
    alert_matches_desired_quantity,
    listing_available_quantity,
    prioritize_alerts,
)

User = get_user_model()


@override_settings(DEBUG=True, SECRET_KEY='test-secret-key-for-local')
class TicketAlertSubscribeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.artist = Artist.objects.create(name='Test Artist')
        self.venue = Venue.objects.create(name='Test Venue', city='Tel Aviv')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Test Show',
            date=timezone.now() + timedelta(days=30),
            venue='ישראל',
            venue_place=self.venue,
            city='Tel Aviv',
            category='concert',
            status='פעיל',
        )
        self.user = User.objects.create_user(
            username='alertuser',
            email='user@example.com',
            password='testpass123',
        )

    def _subscribe(self, payload, user=None):
        if user is not None:
            self.client.force_authenticate(user=user)
        else:
            self.client.force_authenticate(user=None)
        return self.client.post('/api/alerts/subscribe/', payload, format='json')

    def test_subscribe_event_alert_success(self):
        resp = self._subscribe({'event': self.event.id, 'email': 'fan@example.com'})
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp.content))
        alert = TicketAlert.objects.get(event=self.event, email='fan@example.com')
        self.assertIsNone(alert.artist_id)
        self.assertFalse(alert.notified)
        self.assertIsNone(alert.desired_quantity)

    def test_subscribe_with_desired_quantity(self):
        resp = self._subscribe(
            {'event': self.event.id, 'email': 'qty@example.com', 'desired_quantity': 2}
        )
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp.content))
        alert = TicketAlert.objects.get(event=self.event, email='qty@example.com')
        self.assertEqual(alert.desired_quantity, 2)
        self.assertEqual(resp.data['alert']['desired_quantity'], 2)

    def test_subscribe_zero_quantity_means_any(self):
        resp = self._subscribe(
            {'event': self.event.id, 'email': 'any@example.com', 'desired_quantity': 0}
        )
        self.assertEqual(resp.status_code, 201)
        alert = TicketAlert.objects.get(event=self.event, email='any@example.com')
        self.assertIsNone(alert.desired_quantity)

    def test_resubscribe_updates_desired_quantity(self):
        self._subscribe({'event': self.event.id, 'email': 'upd@example.com', 'desired_quantity': 1})
        resp = self._subscribe(
            {'event': self.event.id, 'email': 'upd@example.com', 'desired_quantity': 4}
        )
        self.assertEqual(resp.status_code, 200)
        alert = TicketAlert.objects.get(event=self.event, email='upd@example.com')
        self.assertEqual(alert.desired_quantity, 4)

    def test_subscribe_artist_alert_success(self):
        resp = self._subscribe({'artist': self.artist.id, 'email': 'fan@example.com'})
        self.assertEqual(resp.status_code, 201)
        alert = TicketAlert.objects.get(artist=self.artist, email='fan@example.com', event__isnull=True)
        self.assertIsNone(alert.event_id)

    def test_subscribe_requires_event_or_artist(self):
        resp = self._subscribe({'email': 'fan@example.com'})
        self.assertEqual(resp.status_code, 400)

    def test_subscribe_rejects_both_event_and_artist(self):
        resp = self._subscribe(
            {'event': self.event.id, 'artist': self.artist.id, 'email': 'fan@example.com'}
        )
        self.assertEqual(resp.status_code, 400)

    def test_subscribe_idempotent_for_same_event_email(self):
        self._subscribe({'event': self.event.id, 'email': 'fan@example.com'})
        resp = self._subscribe({'event': self.event.id, 'email': 'fan@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(TicketAlert.objects.filter(event=self.event, email='fan@example.com').count(), 1)

    def test_subscribe_rejects_when_event_has_active_tickets(self):
        Ticket.objects.create(
            seller=self.user,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=2,
            status='active',
        )
        resp = self._subscribe({'event': self.event.id, 'email': 'fan@example.com'})
        self.assertEqual(resp.status_code, 400)

    def test_authenticated_user_email_default(self):
        resp = self._subscribe({'event': self.event.id}, user=self.user)
        self.assertEqual(resp.status_code, 201, getattr(resp, 'data', resp.content))
        alert = TicketAlert.objects.get(event=self.event, email='user@example.com')
        self.assertEqual(alert.user_id, self.user.pk)

    def test_legacy_users_alerts_route(self):
        resp = self.client.post(
            '/api/users/alerts/',
            {'event': self.event.id, 'email': 'legacy@example.com'},
            format='json',
        )
        self.assertIn(resp.status_code, (200, 201))


@override_settings(DEBUG=True, SECRET_KEY='test-secret-key-for-local')
class TicketAlertQuantityMatchingTests(TestCase):
    def setUp(self):
        self.artist = Artist.objects.create(name='Match Artist')
        self.venue = Venue.objects.create(name='Match Venue', city='Tel Aviv')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Match Show',
            date=timezone.now() + timedelta(days=20),
            venue='ישראל',
            venue_place=self.venue,
            city='Tel Aviv',
            category='concert',
            status='פעיל',
        )
        self.seller = User.objects.create_user(
            username='seller_alert',
            email='seller@example.com',
            password='testpass123',
        )

    def test_unit_match_helpers(self):
        self.assertTrue(alert_matches_desired_quantity(None, 1))
        self.assertTrue(alert_matches_desired_quantity(0, 1))
        self.assertTrue(alert_matches_desired_quantity(2, 2))
        self.assertTrue(alert_matches_desired_quantity(2, 5))
        self.assertFalse(alert_matches_desired_quantity(2, 1))
        self.assertFalse(alert_matches_desired_quantity(5, 4))

    def test_wanting_two_not_notified_for_single_ticket(self):
        any_alert = TicketAlert.objects.create(
            event=self.event,
            email='any@example.com',
            desired_quantity=None,
        )
        want_two = TicketAlert.objects.create(
            event=self.event,
            email='two@example.com',
            desired_quantity=2,
        )
        Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=1,
            status='active',
        )
        any_alert.refresh_from_db()
        want_two.refresh_from_db()
        self.assertTrue(any_alert.notified)
        self.assertFalse(want_two.notified)

    def test_wanting_two_notified_when_listing_has_two(self):
        want_two = TicketAlert.objects.create(
            event=self.event,
            email='two@example.com',
            desired_quantity=2,
        )
        Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=2,
            status='active',
        )
        want_two.refresh_from_db()
        self.assertTrue(want_two.notified)

    def test_prioritize_specific_over_any(self):
        any_alert = TicketAlert.objects.create(
            event=self.event,
            email='any@example.com',
            desired_quantity=None,
        )
        want_two = TicketAlert.objects.create(
            event=self.event,
            email='two@example.com',
            desired_quantity=2,
        )
        ordered = prioritize_alerts([any_alert, want_two])
        self.assertEqual(ordered[0].email, 'two@example.com')
        self.assertEqual(ordered[1].email, 'any@example.com')

    def test_listing_group_quantity_sums(self):
        group = 'group-alert-qty-1'
        t1 = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=1,
            status='active',
            listing_group_id=group,
        )
        Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=1,
            status='active',
            listing_group_id=group,
        )
        self.assertEqual(listing_available_quantity(t1), 2)


@override_settings(DEBUG=True, SECRET_KEY='test-secret-key-for-local')
class BloomfieldMapLegendLayoutTests(TestCase):
    """Ensure map legend CSS does not overlay seating (absolute positioning removed)."""

    def test_bloomfield_legend_not_absolute_overlay(self):
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        css_path = repo_root / 'frontend' / 'src' / 'components' / 'BloomfieldStadiumMap.css'
        css = css_path.read_text(encoding='utf-8')
        legend_block = css.split('.bloomfield-map-legend {', 1)[1].split('}', 1)[0]
        self.assertNotIn('position: absolute', legend_block)
        self.assertIn('position: static', legend_block)

        jsx_path = repo_root / 'frontend' / 'src' / 'components' / 'BloomfieldStadiumMap.jsx'
        jsx = jsx_path.read_text(encoding='utf-8')
        self.assertIn('bloomfield-map-shell', jsx)
        legend_idx = jsx.index('bloomfield-map-legend')
        root_close = jsx.rindex('bloomfield-map-root')
        self.assertGreater(legend_idx, root_close, 'Legend must render after map root closes')
