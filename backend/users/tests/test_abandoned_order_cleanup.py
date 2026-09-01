from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.models import Artist, Event, Order, Ticket
from users.order_cleanup import cancel_abandoned_pending_payment_orders
from users.views import release_abandoned_carts


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

    def _pending_order(self, *, age_minutes=70, **overrides):
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

    def test_cancels_abandoned_group_order_without_payme_sale_id(self):
        ticket = self._ticket()
        order = self._pending_order(ticket=ticket, ticket_ids=[ticket.id], payme_status='initialized')

        result = cancel_abandoned_pending_payment_orders(older_than_minutes=60)

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

        result = cancel_abandoned_pending_payment_orders(older_than_minutes=60)

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
        order = self._pending_order(
            ticket=ticket,
            ticket_ids=[ticket.id],
            payme_status='authorized',
            payme_transaction_id='SALE-AUTH',
        )

        result = cancel_abandoned_pending_payment_orders(older_than_minutes=60)

        self.assertEqual(result.cancelled, 0)
        self.assertEqual(result.skipped_payme_completed, 1)
        order.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')
        self.assertEqual(ticket.status, 'reserved')

    def test_skips_orders_with_payme_sale_id_until_explicit_failure(self):
        """Apple Pay: sale id stored at init, webhook delayed — must not cancel."""
        ticket = self._ticket()
        order = self._pending_order(
            age_minutes=90,
            ticket=ticket,
            ticket_ids=[ticket.id],
            payme_status='initialized',
            payme_transaction_id='SALE-APPLE-PENDING',
        )

        result = cancel_abandoned_pending_payment_orders(older_than_minutes=60)

        self.assertEqual(result.cancelled, 0)
        self.assertEqual(result.skipped_payme_sale_pending, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')

    def test_cancels_payme_sale_when_status_explicitly_failed(self):
        ticket = self._ticket()
        order = self._pending_order(
            age_minutes=90,
            ticket=ticket,
            ticket_ids=[ticket.id],
            payme_status='failed',
            payme_transaction_id='SALE-FAILED',
        )

        result = cancel_abandoned_pending_payment_orders(older_than_minutes=60)

        self.assertEqual(result.cancelled, 1)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

    def test_keeps_pending_payment_order_inside_sixty_minute_grace(self):
        ticket = self._ticket()
        order = self._pending_order(
            age_minutes=45,
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


class ReleaseAbandonedCartsLockingTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='seller-release',
            email='seller-release@example.com',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='buyer-release',
            email='buyer-release@example.com',
            password='pass',
        )
        self.artist = Artist.objects.create(name='Release Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Release Show',
            date=timezone.now() + timedelta(days=30),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
        )

    def test_release_abandoned_carts_unlocks_expired_reservation_row_locked(self):
        ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            pdf_file='tickets/pdfs/test.pdf',
            status='reserved',
            verification_status='מאומת',
            available_quantity=1,
            reserved_by=self.buyer,
            reserved_at=timezone.now() - timedelta(minutes=20),
        )

        released = release_abandoned_carts()

        self.assertGreaterEqual(released, 1)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_at)
        self.assertIsNone(ticket.reserved_by_id)
        self.assertIsNone(ticket.locked_until)

    def test_sweeper_keeps_live_payment_hold_after_cart_window(self):
        until = timezone.now() + timedelta(minutes=10)
        ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            pdf_file='tickets/pdfs/test.pdf',
            status='reserved',
            verification_status='מאומת',
            available_quantity=1,
            reserved_by=self.buyer,
            reserved_at=timezone.now() - timedelta(minutes=3),
            locked_until=until,
        )

        release_abandoned_carts()

        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertIsNotNone(ticket.locked_until)
