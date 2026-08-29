"""
PayMe webhook idempotency + concurrent success notifies.

Run: python manage.py test users.tests.test_payme_webhook_idempotency -v 2
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import (
    Artist,
    Event,
    Order,
    PayMeWebhookIdempotency,
    SellerPayout,
    Ticket,
)
from users.payme_views import payme_webhook
from users.payments import build_payme_webhook_idempotency_key
from users.pricing import expected_buy_now_total
from users.tests.payme_ipn_test_helpers import (
    MOCK_PAYME_SALE_SUCCESS,
    PAYME_IPN_TEST_SETTINGS,
    payme_ipn_json_request,
)
from wallets.models import UserWallet, WalletTransaction

User = get_user_model()


@override_settings(**{**PAYME_IPN_TEST_SETTINGS, 'DEBUG': True, 'PAYME_IS_SANDBOX': True})
class PayMeWebhookConcurrentIdempotencyTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self._confirm_patcher = patch(
            'users.payme_views.confirm_payme_sale_status',
            return_value=dict(MOCK_PAYME_SALE_SUCCESS),
        )
        self.mock_confirm = self._confirm_patcher.start()
        self.addCleanup(self._confirm_patcher.stop)
        self.seller = User.objects.create_user(
            username='idemp_seller',
            email='idemp-seller@example.test',
            password='pass-12345',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='idemp_buyer',
            email='idemp-buyer@example.test',
            password='pass-12345',
        )
        self.artist = Artist.objects.create(name='Idempotency Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Idempotency Show',
            date=timezone.now() + timedelta(days=21),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
            status='פעיל',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file='tickets/pdfs/idemp.pdf',
            status='reserved',
            verification_status='מאומת',
            available_quantity=1,
            reserved_by=self.buyer,
            reserved_at=timezone.now(),
        )
        self.total = expected_buy_now_total(self.ticket.asking_price, 1)
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            ticket_ids=[self.ticket.id],
            status='pending_payment',
            total_amount=self.total,
            total_paid_by_buyer=self.total,
            currency='ILS',
            quantity=1,
            payme_transaction_id='SALE-IDEMP-CONCURRENT-1',
            payme_status='initialized',
            payment_confirm_token='tok-idemp',
        )
        self.payload = {
            'merchant_order_id': str(self.order.id),
            'payme_sale_id': 'SALE-IDEMP-CONCURRENT-1',
            'transaction_id': 'SALE-IDEMP-CONCURRENT-1',
            'sale_price': int(self.total * 100),
            'currency': 'ILS',
            'status': 'completed',
        }

    def _fire_success_webhook(self):
        connections.close_all()
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute('PRAGMA busy_timeout=8000;')
        request, _signed, _body = payme_ipn_json_request(self.payload)
        try:
            response = payme_webhook(request)
            return int(response.status_code), dict(getattr(response, 'data', {}) or {})
        finally:
            connections.close_all()

    def _assert_single_fulfillment(self):
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.ticket.status, 'sold')
        self.assertEqual(self.ticket.available_quantity, 0)
        self.assertEqual(Order.objects.filter(ticket=self.ticket, status='paid').count(), 1)
        self.assertEqual(SellerPayout.objects.filter(order=self.order).count(), 1)
        payout = SellerPayout.objects.get(order=self.order)
        sale_credits = WalletTransaction.objects.filter(
            seller_payout=payout,
            transaction_type=WalletTransaction.TransactionType.SALE_CREDIT,
        )
        self.assertEqual(sale_credits.count(), 1)
        wallet = UserWallet.objects.get(user=self.seller)
        credited = (wallet.available_balance or 0) + (wallet.locked_balance or 0)
        self.assertEqual(credited, payout.net_payout + (payout.seller_bonus_amount or 0))
        keys = PayMeWebhookIdempotency.objects.filter(order=self.order)
        self.assertEqual(keys.count(), 1)
        self.assertEqual(keys.get().status, PayMeWebhookIdempotency.STATUS_COMPLETED)
        expected_key = build_payme_webhook_idempotency_key(self.order, self.payload)
        self.assertEqual(keys.get().idempotency_key, expected_key)

    def test_same_success_payload_five_times_concurrent(self):
        statuses = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(self._fire_success_webhook) for _ in range(5)]
            for fut in as_completed(futures, timeout=45):
                status_code, body = fut.result()
                statuses.append(status_code)
                self.assertIn(status_code, (200, 409), body)

        self.assertTrue(any(code == 200 for code in statuses), statuses)
        self.assertTrue(all(code in (200, 409) for code in statuses), statuses)
        self._assert_single_fulfillment()

    def test_same_success_payload_five_times_sequential(self):
        client = APIClient()
        request, _signed, body = payme_ipn_json_request(self.payload)
        content_type = request.content_type
        for _ in range(5):
            res = client.generic(
                'POST',
                '/api/payments/webhook/payme/',
                body,
                content_type=content_type,
            )
            self.assertEqual(res.status_code, 200, res.content)
            self.assertTrue(res.data.get('finalized'))

        self._assert_single_fulfillment()
        self.assertEqual(PayMeWebhookIdempotency.objects.filter(order=self.order).count(), 1)
