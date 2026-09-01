"""POST /api/users/orders/<id>/cancel-payment/ releases inventory immediately."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket

User = get_user_model()

CANCEL_URL = '/api/users/orders/{}/cancel-payment/'


class CancelPendingPaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='cancel-seller',
            email='cancel-seller@example.test',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='cancel-buyer',
            email='cancel-buyer@example.test',
            password='pass',
            role='buyer',
        )
        artist = Artist.objects.create(name='Cancel Artist')
        event = Event.objects.create(
            artist=artist,
            name='Cancel Show',
            date=timezone.now() + timedelta(days=10),
            venue='ישראל',
            city='תל אביב',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            status='reserved',
            available_quantity=0,
            reserved_by=self.buyer,
            reserved_at=timezone.now(),
            verification_status='מאומת',
            pdf_file='tickets/pdfs/cancel.pdf',
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            quantity=1,
            total_amount=Decimal('107.00'),
            status='pending_payment',
            payme_status='initialized',
            ticket_ids=[self.ticket.pk],
            event_name=event.name,
            payment_confirm_token='cancel-token-aaaaaaaaaaaaaaaaaaaaaaaa',
        )
        self.guest_ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('80'),
            asking_price=Decimal('80'),
            status='reserved',
            available_quantity=1,
            reservation_email='guest-cancel@example.test',
            reserved_at=timezone.now(),
            verification_status='מאומת',
            pdf_file='tickets/pdfs/cancel-guest.pdf',
        )
        self.guest_order = Order.objects.create(
            user=None,
            guest_email='guest-cancel@example.test',
            ticket=self.guest_ticket,
            quantity=1,
            total_amount=Decimal('85.60'),
            status='pending_payment',
            payme_status='initialized',
            ticket_ids=[self.guest_ticket.pk],
            event_name=event.name,
            payment_confirm_token='guest-token-bbbbbbbbbbbbbbbbbbbbbbbb',
        )

    def test_owner_cancel_releases_reserved_ticket(self):
        self.client.force_authenticate(self.buyer)
        res = self.client.post(CANCEL_URL.format(self.order.pk), {}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data.get('released'))
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.ticket.status, 'active')
        self.assertIsNone(self.ticket.reserved_by_id)
        self.assertIsNone(self.ticket.reserved_at)

    def test_guest_email_cancel_releases_hold(self):
        res = self.client.post(
            CANCEL_URL.format(self.guest_order.pk),
            {'guest_email': 'guest-cancel@example.test'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.guest_order.refresh_from_db()
        self.guest_ticket.refresh_from_db()
        self.assertEqual(self.guest_order.status, 'cancelled')
        self.assertEqual(self.guest_ticket.status, 'active')

    def test_payment_confirm_token_cancel_without_auth(self):
        res = self.client.post(
            CANCEL_URL.format(self.order.pk),
            {'payment_confirm_token': 'cancel-token-aaaaaaaaaaaaaaaaaaaaaaaa'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.ticket.status, 'active')

    def test_stranger_cannot_cancel(self):
        other = User.objects.create_user(
            username='cancel-other',
            email='cancel-other@example.test',
            password='pass',
            role='buyer',
        )
        self.client.force_authenticate(other)
        res = self.client.post(CANCEL_URL.format(self.order.pk), {}, format='json')
        self.assertEqual(res.status_code, 404)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')

    def test_anonymous_without_proof_is_404_not_401(self):
        res = self.client.post(CANCEL_URL.format(self.guest_order.pk), {}, format='json')
        self.assertEqual(res.status_code, 404)
        self.assertNotEqual(res.status_code, 401)

    def test_paid_order_returns_409(self):
        self.order.status = 'paid'
        self.order.save(update_fields=['status'])
        self.client.force_authenticate(self.buyer)
        res = self.client.post(CANCEL_URL.format(self.order.pk), {}, format='json')
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data.get('status'), 'paid')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'reserved')

    def test_cancel_is_idempotent(self):
        self.client.force_authenticate(self.buyer)
        first = self.client.post(CANCEL_URL.format(self.order.pk), {}, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        second = self.client.post(CANCEL_URL.format(self.order.pk), {}, format='json')
        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.data.get('already_cancelled'))
