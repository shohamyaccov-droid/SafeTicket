from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.models import Event, Order, SellerPayout, Ticket
from users.payout_ledger import ensure_seller_payout_for_order, payout_amounts_from_order

User = get_user_model()


class PayoutLedgerTest(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='seller_ledger',
            email='seller_ledger@test.com',
            password='test-pass-123',
            role='seller',
            account_holder_name='Test Seller',
            bank_name='10',
            branch_number='123',
            account_number='987654',
        )
        self.buyer = User.objects.create_user(
            username='buyer_ledger',
            email='buyer_ledger@test.com',
            password='test-pass-123',
        )
        self.event = Event.objects.create(
            name='Ledger Event',
            date=timezone.now() + timedelta(days=30),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='sold',
            available_quantity=0,
        )

    def _paid_order(self, **kwargs):
        defaults = {
            'user': self.buyer,
            'ticket': self.ticket,
            'status': 'paid',
            'total_amount': Decimal('115.00'),
            'total_paid_by_buyer': Decimal('115.00'),
            'final_negotiated_price': Decimal('100.00'),
            'buyer_service_fee': Decimal('15.00'),
            'seller_service_fee': Decimal('0.00'),
            'net_seller_revenue': Decimal('100.00'),
            'quantity': 1,
            'event_name': self.event.name,
        }
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    def test_payout_save_preserves_explicit_order_fee_and_net(self):
        order = self._paid_order()
        payout = SellerPayout.objects.get(order=order)
        payout.total_paid = Decimal('200.00')
        payout.save()
        self.assertEqual(payout.platform_fee, Decimal('15.00'))
        self.assertEqual(payout.net_payout, Decimal('100.00'))

    def test_payout_amounts_from_order(self):
        order = self._paid_order()
        amounts = payout_amounts_from_order(order)
        self.assertEqual(amounts, (Decimal('115.00'), Decimal('15.00'), Decimal('100.00')))

    def test_ensure_seller_payout_for_order_idempotent(self):
        order = self._paid_order()
        first = ensure_seller_payout_for_order(order)
        second = ensure_seller_payout_for_order(order)
        self.assertIsNotNone(first)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SellerPayout.objects.filter(order=order).count(), 1)
        self.assertEqual(first.platform_fee, Decimal('15.00'))
        self.assertEqual(first.net_payout, Decimal('100.00'))
        self.assertEqual(first.payout_status, SellerPayout.PayoutStatus.PENDING)

    def test_signal_creates_payout_when_order_marked_paid(self):
        order = self._paid_order(status='pending_payment')
        order.status = 'paid'
        order.save()
        payout = SellerPayout.objects.get(order=order)
        self.assertEqual(payout.seller_id, self.seller.id)
        self.assertEqual(payout.platform_fee, Decimal('15.00'))
        self.assertEqual(payout.net_payout, Decimal('100.00'))

    def test_transferred_status_sets_transferred_at(self):
        order = self._paid_order()
        payout = SellerPayout.objects.get(order=order)
        payout.payout_status = SellerPayout.PayoutStatus.TRANSFERRED
        payout.transferred_at = None
        payout.save()
        self.assertIsNotNone(payout.transferred_at)

    def test_total_pending_for_seller(self):
        order = self._paid_order()
        ensure_seller_payout_for_order(order)
        total = SellerPayout.total_pending_for_seller(self.seller)
        self.assertEqual(total, Decimal('100.00'))
