"""DEBUG-only mock payment bypass — order paid + SellerPayout ledger."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Order, SellerPayout, Ticket
from users.pricing import buyer_charge_from_base_amount, expected_buy_now_total

User = get_user_model()

MOCK_URL = '/api/payments/mock-success/'
ORDERS_URL = '/api/users/orders/'

MINOR_PDF = SimpleUploadedFile(
    'ticket.pdf',
    b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
    content_type='application/pdf',
)

@override_settings(DEBUG=True)
class MockPaymentSuccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False

        self.seller = User.objects.create_user(
            username='mock_seller',
            email='mock_seller@test.invalid',
            password='test-pass-123',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='mock_buyer',
            email='mock_buyer@test.invalid',
            password='test-pass-123',
            role='buyer',
        )
        self.asking = Decimal('100.00')
        self.checkout_total = expected_buy_now_total(self.asking, 1)

        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event_name='Mock Event',
            event_date=timezone.now() + timedelta(days=30),
            venue='Bloomfield',
            original_price=self.asking,
            asking_price=self.asking,
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file=MINOR_PDF,
        )

    def _create_pending_order(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(
            ORDERS_URL,
            {
                'ticket': self.ticket.id,
                'total_amount': float(self.checkout_total),
                'quantity': 1,
                'event_name': self.ticket.event_name,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        return res.data['id']

    def test_mock_payment_finalizes_order_and_ledger(self):
        order_id = self._create_pending_order()
        res = self.client.post(MOCK_URL, {'order_id': order_id}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'))
        self.assertEqual(res.data.get('order_status'), 'paid')

        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, 'paid')

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'sold')

        payout = SellerPayout.objects.get(order=order)
        total = Decimal(str(self.checkout_total)).quantize(Decimal('0.01'))
        expected_net, expected_fee, _expected_total = buyer_charge_from_base_amount(self.ticket.asking_price)
        self.assertEqual(payout.total_paid, total)
        self.assertEqual(payout.platform_fee, expected_fee)
        self.assertEqual(payout.net_payout, expected_net)
        self.assertEqual(payout.payout_status, 'pending')

    def test_mock_payment_forbidden_when_debug_false(self):
        order_id = self._create_pending_order()
        with override_settings(DEBUG=False):
            res = self.client.post(MOCK_URL, {'order_id': order_id}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_mock_payment_requires_order_owner(self):
        order_id = self._create_pending_order()
        other = User.objects.create_user(
            username='other_buyer',
            email='other@test.invalid',
            password='test-pass-123',
        )
        self.client.force_authenticate(user=other)
        res = self.client.post(MOCK_URL, {'order_id': order_id}, format='json')
        self.assertEqual(res.status_code, 403)
