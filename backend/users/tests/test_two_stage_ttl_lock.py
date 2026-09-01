from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket
from users.pricing import expected_buy_now_total
from users.ticket_status import CART_HOLD_MINUTES, PAYMENT_HOLD_MINUTES
from users.views import release_abandoned_carts

User = get_user_model()


def _aware(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


class TwoStageTtlLockTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='ttl_seller',
            email='ttl_seller@test.com',
            password='Pass12345!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='ttl_buyer',
            email='ttl_buyer@test.com',
            password='Pass12345!',
            role='buyer',
            first_name='Buyer',
            last_name='Test',
            phone_number='0501234567',
        )
        artist = Artist.objects.create(name='TTL Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='TTL Event',
            date=timezone.now() + timedelta(days=14),
            venue='Hall',
            city='Tel Aviv',
            country='IL',
        )

    def _ticket(self, **kwargs):
        defaults = dict(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('120.00'),
            asking_price=Decimal('120.00'),
            pdf_file='tickets/pdfs/ttl.pdf',
            status='active',
            verification_status='מאומת',
            available_quantity=1,
        )
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def _seconds_until(self, iso_or_dt):
        if iso_or_dt is None:
            return None
        dt = iso_or_dt if hasattr(iso_or_dt, 'year') else parse_datetime(str(iso_or_dt))
        dt = _aware(dt)
        return (dt - timezone.now()).total_seconds()

    def test_buy_now_reserve_locks_for_two_minutes(self):
        ticket = self._ticket()
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'quantity': 1},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertAlmostEqual(self._seconds_until(res.data.get('expires_at')), CART_HOLD_MINUTES * 60, delta=8)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertIsNotNone(ticket.locked_until)
        self.assertAlmostEqual(self._seconds_until(ticket.locked_until), CART_HOLD_MINUTES * 60, delta=8)

    def test_unlock_clears_locked_until(self):
        ticket = self._ticket()
        self.client.force_authenticate(self.buyer)
        lock = self.client.post(f'/api/users/tickets/{ticket.id}/reserve/', {'quantity': 1}, format='json')
        self.assertEqual(lock.status_code, 200, lock.data)
        unlock = self.client.post(f'/api/users/tickets/{ticket.id}/unlock/', {}, format='json')
        self.assertEqual(unlock.status_code, 200, unlock.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.locked_until)
        self.assertIsNone(ticket.reserved_at)

    def test_abandoned_cart_without_locked_until_releases_after_two_minutes(self):
        ticket = self._ticket(
            status='reserved',
            reserved_by=self.buyer,
            reserved_at=timezone.now() - timedelta(minutes=3),
            locked_until=None,
        )
        released = release_abandoned_carts()
        self.assertGreaterEqual(released, 1)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_at)
        self.assertIsNone(ticket.locked_until)

    def test_payment_hold_survives_three_minute_sweeper(self):
        until = timezone.now() + timedelta(minutes=PAYMENT_HOLD_MINUTES)
        ticket = self._ticket(
            status='reserved',
            reserved_by=self.buyer,
            reserved_at=timezone.now() - timedelta(minutes=3),
            locked_until=until,
        )
        release_abandoned_carts()
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertIsNotNone(ticket.locked_until)

    def test_create_order_extends_lock_to_ten_minutes(self):
        ticket = self._ticket()
        self.client.force_authenticate(self.buyer)
        lock = self.client.post(f'/api/users/tickets/{ticket.id}/reserve/', {'quantity': 1}, format='json')
        self.assertEqual(lock.status_code, 200, lock.data)
        total = expected_buy_now_total(ticket.asking_price, 1)
        res = self.client.post(
            '/api/users/orders/',
            {
                'ticket': ticket.id,
                'quantity': 1,
                'total_amount': str(total),
                'accepted_terms': True,
                'event_name': self.event.name,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data.get('lock_expires_at'))
        self.assertAlmostEqual(
            self._seconds_until(res.data.get('lock_expires_at')),
            PAYMENT_HOLD_MINUTES * 60,
            delta=8,
        )
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertAlmostEqual(self._seconds_until(ticket.locked_until), PAYMENT_HOLD_MINUTES * 60, delta=8)

    def test_guest_checkout_extends_lock_to_ten_minutes(self):
        ticket = self._ticket()
        guest_email = 'ttl-guest@example.test'
        lock = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'email': guest_email, 'quantity': 1},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        total = expected_buy_now_total(ticket.asking_price, 1)
        res = self.client.post(
            '/api/users/orders/guest/',
            {
                'guest_first_name': 'Guest',
                'guest_last_name': 'Buyer',
                'guest_email': guest_email,
                'guest_phone': '0501234567',
                'ticket_id': ticket.id,
                'total_amount': str(total),
                'quantity': 1,
                'event_name': self.event.name,
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data.get('lock_expires_at'))
        self.assertAlmostEqual(
            self._seconds_until(res.data.get('lock_expires_at')),
            PAYMENT_HOLD_MINUTES * 60,
            delta=8,
        )
        ticket.refresh_from_db()
        self.assertAlmostEqual(self._seconds_until(ticket.locked_until), PAYMENT_HOLD_MINUTES * 60, delta=8)
