from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.models import Artist, Event, Order, Ticket
from users.order_cleanup import cancel_abandoned_pending_payment_orders


User = get_user_model()


class AbandonedOrderCleanupTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='seller-cleanup',
            email='seller-cleanup@example.com',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='buyer-cleanup',
            email='buyer-cleanup@example.com',
            password='pass',
        )
        self.artist = Artist.objects.create(name='Cleanup Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Cleanup Show',
            date=timezone.now() + timedelta(days=30),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
        )

    def _ticket(self, **overrides):
        base = {
            'seller': self.seller,
            'event': self.event,
            'original_price': Decimal('100'),
            'asking_price': Decimal('100'),
            'pdf_file': 'tickets/pdfs/test.pdf',
            'status': 'reserved',
            'verification_status': 'מאומת',
            'available_quantity': 1,
            'reserved_by': self.buyer,
            'reserved_at': timezone.now() - timedelta(minutes=20),
        }
        base.update(overrides)
        return Ticket.objects.create(**base)

    def _pending_order(self, *, age_minutes=20, **overrides):
        base = {
            'user': self.buyer,
            'total_amount': Decimal('110.00'),
            'currency': 'ILS',
            'quantity': 1,
            'status': 'pending_payment',
            'payment_confirm_token': 'pending-token',
        }
        base.update(overrides)
        order = Order.objects.create(**base)
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(minutes=age_minutes))
        order.refresh_from_db()
        return order

    def test_cancels_ten_minute_abandoned_group_order_and_releases_reserved_tickets(self):
        ticket = self._ticket()
        order = self._pending_order(ticket=ticket, ticket_ids=[ticket.id], payme_status='initialized')

        result = cancel_abandoned_pending_payment_orders()

        self.assertEqual(result.cancelled, 1)
        self.assertEqual(result.released_tickets, 1)
        order.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertIsNone(order.payment_confirm_token)
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_at)
        self.assertIsNone(ticket.reserved_by_id)

    def test_restores_partial_quantity_hold(self):
        ticket = self._ticket(status='reserved', available_quantity=0)
        order = self._pending_order(
            ticket=ticket,
            held_ticket=ticket,
            held_quantity=2,
            ticket_ids=[ticket.id],
            quantity=2,
            payme_status='pending',
        )

        result = cancel_abandoned_pending_payment_orders()

        self.assertEqual(result.cancelled, 1)
        self.assertEqual(result.restored_quantity, 2)
        order.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertIsNone(order.held_ticket_id)
        self.assertEqual(order.held_quantity, 0)
        self.assertEqual(ticket.available_quantity, 2)
        self.assertEqual(ticket.status, 'active')

    def test_skips_orders_with_successful_payme_status(self):
        ticket = self._ticket()
        order = self._pending_order(ticket=ticket, ticket_ids=[ticket.id], payme_status='authorized')

        result = cancel_abandoned_pending_payment_orders()

        self.assertEqual(result.cancelled, 0)
        self.assertEqual(result.skipped_payme_completed, 1)
        order.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')
        self.assertEqual(ticket.status, 'reserved')

    def test_keeps_pending_payment_order_inside_ten_minute_window(self):
        ticket = self._ticket()
        order = self._pending_order(
            age_minutes=9,
            ticket=ticket,
            ticket_ids=[ticket.id],
            payme_status='initialized',
        )

        result = cancel_abandoned_pending_payment_orders()

        self.assertEqual(result.cancelled, 0)
        order.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')
        self.assertEqual(ticket.status, 'reserved')
