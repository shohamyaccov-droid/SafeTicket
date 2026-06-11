"""
Tests for TicketAlert subscribe API (event + artist scopes).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket, TicketAlert, Venue

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
            venue='אחר',
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
        from decimal import Decimal

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
