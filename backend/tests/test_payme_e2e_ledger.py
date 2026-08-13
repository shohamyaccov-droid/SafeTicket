"""
End-to-end PayMe checkout + SellerPayout ledger integration tests.

Simulates real marketplace flow:
  Seller lists ticket → Buyer reserves → Buyer creates order → PayMe init → Webhook → Ledger

Run:
  cd backend && python manage.py test tests.test_payme_e2e_ledger -v 2
"""
from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from users.models import Artist, Event, Order, SellerPayout, Ticket
from users.payme_views import payme_webhook
from users.pricing import expected_buy_now_total
from users.tests.payme_ipn_test_helpers import (
    MOCK_PAYME_SALE_FAILED,
    MOCK_PAYME_SALE_NOT_FOUND,
    TEST_PAYME_API_KEY,
    TEST_PAYME_API_PASSWORD,
    MockPayMeSaleConfirmMixin,
    sign_payme_ipn_payload,
)

User = get_user_model()

WEBHOOK_URL = '/api/payments/webhook/payme/'
INIT_URL = '/api/users/payments/payme/init/'
ORDERS_URL = '/api/users/orders/'
RESERVE_URL = '/api/users/tickets/{ticket_id}/reserve/'
PAYME_SANDBOX_BUYER_EMAIL = 'tradetix.support+1@gmail.com'

MINOR_PDF = SimpleUploadedFile(
    'ticket.pdf',
    b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
    content_type='application/pdf',
)


def sign_payme_payload(payload: dict) -> tuple[bytes, str]:
    signed = sign_payme_ipn_payload(payload)
    body = json.dumps(signed, separators=(',', ':')).encode('utf-8')
    return body, signed['payme_signature']


def assert_ledger_math(test_case, total_paid: Decimal, payout: SellerPayout) -> None:
    """Assert platform fee is the buyer Service and Operation Fee and seller receives listing price."""
    total = Decimal(total_paid).quantize(Decimal('0.01'))
    expected_net = payout.order.net_seller_revenue.quantize(Decimal('0.01'))
    expected_fee = (total - expected_net).quantize(Decimal('0.01'))

    test_case.assertEqual(payout.total_paid, total)
    test_case.assertEqual(payout.platform_fee, expected_fee)
    test_case.assertEqual(payout.net_payout, expected_net)
    test_case.assertEqual(
        payout.platform_fee + payout.net_payout,
        total,
        'platform_fee + net_payout must equal total_paid',
    )
    test_case.assertEqual(payout.net_payout, payout.order.final_negotiated_price)


@override_settings(
    DEBUG=True,
    PAYME_SELLER_ID='MPL-E2E-TEST-SELLER',
    PAYME_API_URL='https://testpay.payme.io/api',
    PAYME_IS_SANDBOX=True,
    PAYME_SANDBOX_ACCOUNT_EMAIL=PAYME_SANDBOX_BUYER_EMAIL,
    PAYME_API_KEY=TEST_PAYME_API_KEY,
    PAYME_API_PASSWORD=TEST_PAYME_API_PASSWORD,
)
class PayMeMarketplaceE2EBase(MockPayMeSaleConfirmMixin, TestCase):
    """Shared marketplace fixture: seller event + verified active listing."""

    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        self.factory = APIRequestFactory()
        self.event_date = timezone.now() + timedelta(days=45)

        self.seller = User.objects.create_user(
            username='e2e_seller',
            email='e2e_seller@test.invalid',
            password='test-pass-123',
            role='seller',
            account_holder_name='E2E Seller',
            bank_name='12',
            branch_number='456',
            account_number='123456789',
        )
        self.buyer = User.objects.create_user(
            username='e2e_buyer',
            email=PAYME_SANDBOX_BUYER_EMAIL,
            password='test-pass-123',
            role='buyer',
            phone_number='0501234567',
            first_name='E2E',
            last_name='Buyer',
        )
        self.artist = Artist.objects.create(name='E2E Headliner')
        self.event = Event.objects.create(
            name='E2E Concert Night',
            artist=self.artist,
            date=self.event_date,
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        self.asking_price = Decimal('100.00')
        self.checkout_total = expected_buy_now_total(self.asking_price, 1)

        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=self.asking_price,
            asking_price=self.asking_price,
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file=MINOR_PDF,
        )

    def _buyer_reserves_ticket(self) -> None:
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            RESERVE_URL.format(ticket_id=self.ticket.id),
            {},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'reserved')
        self.assertEqual(self.ticket.reserved_by_id, self.buyer.id)

    def _buyer_creates_pending_order(self) -> Order:
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            ORDERS_URL,
            {
                'ticket': self.ticket.id,
                'total_amount': str(self.checkout_total),
                'accepted_terms': True,
                'quantity': 1,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        order = Order.objects.get(pk=res.data['id'])
        self.assertEqual(order.status, 'pending_payment')
        self.assertEqual(order.user_id, self.buyer.id)
        self.assertEqual(order.ticket_ids, [self.ticket.id])
        return order

    def _init_payme_checkout(self, order: Order, mock_generate, *, transaction_id: str = 'txn_e2e_001'):
        mock_generate.return_value = {
            'payme_sale_url': 'https://testpay.payme.io/hosted/e2e-checkout',
            'transaction_id': transaction_id,
            'payme_sale_id': 'sale_e2e_001',
            'raw': {'status_code': 0},
        }
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            INIT_URL,
            {
                'order_id': order.id,
                'success_url': 'http://localhost:5173/checkout/success',
                'failure_url': 'http://localhost:5173/checkout/failure',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['payme_sale_url'], 'https://testpay.payme.io/hosted/e2e-checkout')
        order.refresh_from_db()
        self.assertEqual(order.payme_transaction_id, transaction_id)
        self.assertEqual(order.payme_status, 'initialized')
        return res

    def _post_signed_webhook(self, payload: dict, *, signature: str | None = None):
        signed = sign_payme_ipn_payload(payload)
        if signature is not None:
            signed['payme_signature'] = signature
        body = json.dumps(signed, separators=(',', ':')).encode('utf-8')
        return self.client.post(
            WEBHOOK_URL,
            body,
            content_type='application/json',
        )

    def _success_webhook_payload(self, order: Order, *, transaction_id: str | None = None) -> dict:
        tid = transaction_id or order.payme_transaction_id
        sale_price_minor = int(Decimal(order.total_paid_by_buyer or order.total_amount) * 100)
        return {
            'merchant_order_id': str(order.id),
            'status': 'success',
            'transaction_id': tid,
            'payme_transaction_id': tid,
            'payme_sale_id': tid,
            'sale_price': sale_price_minor,
            'currency': order.currency or 'ILS',
        }


class PayMeHappyPathE2ETests(PayMeMarketplaceE2EBase):
    """Full buyer journey: reserve → order → PayMe init → webhook → paid + ledger."""

    @patch('users.payme_views.generate_payme_sale_for_order')
    def test_full_flow_creates_seller_payout_with_correct_current_fee_math(self, mock_generate):
        self._buyer_reserves_ticket()
        order = self._buyer_creates_pending_order()
        self.assertEqual(SellerPayout.objects.filter(order=order).count(), 0)

        self._init_payme_checkout(order, mock_generate, transaction_id='txn_happy_path')

        webhook_res = self._post_signed_webhook(self._success_webhook_payload(order))
        self.assertEqual(webhook_res.status_code, 200, webhook_res.content)
        self.assertTrue(webhook_res.data.get('finalized'), webhook_res.data)

        order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.payme_status, 'success')
        self.assertEqual(self.ticket.status, 'sold')
        self.assertEqual(self.ticket.available_quantity, 0)

        payout = SellerPayout.objects.get(order=order)
        self.assertEqual(payout.seller_id, self.seller.id)
        self.assertEqual(payout.payout_status, SellerPayout.PayoutStatus.PENDING)
        assert_ledger_math(self, order.total_paid_by_buyer or order.total_amount, payout)

        total_paid = Decimal(order.total_paid_by_buyer or order.total_amount)
        self.assertEqual(total_paid, self.checkout_total)
        self.assertEqual(payout.platform_fee, total_paid - Decimal('100.00'))
        self.assertEqual(payout.net_payout, Decimal('100.00'))
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.locked_balance, Decimal('100.00'))
        self.assertEqual(self.seller.wallet.available_balance, Decimal('0.00'))

    @patch('users.payme_views.generate_payme_sale_for_order')
    def test_duplicate_success_webhook_does_not_duplicate_ledger(self, mock_generate):
        self._buyer_reserves_ticket()
        order = self._buyer_creates_pending_order()
        self._init_payme_checkout(order, mock_generate, transaction_id='txn_dup_ledger')

        payload = self._success_webhook_payload(order)
        first = self._post_signed_webhook(payload)
        second = self._post_signed_webhook(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(SellerPayout.objects.filter(order=order).count(), 1)


class PayMeFraudFailureE2ETests(PayMeMarketplaceE2EBase):
    """Webhook attacks / failures must never finalize orders or create ledger rows."""

    def setUp(self):
        super().setUp()
        self._buyer_reserves_ticket()
        self.order = self._buyer_creates_pending_order()
        self.order.payme_transaction_id = 'txn_fraud_guard'
        self.order.payme_status = 'initialized'
        self.order.save(update_fields=['payme_transaction_id', 'payme_status', 'updated_at'])

    def _assert_checkout_still_pending(self):
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')
        self.assertFalse(SellerPayout.objects.filter(order=self.order).exists())

    def test_webhook_invalid_json_does_not_finalize(self):
        res = self.client.post(
            WEBHOOK_URL,
            b'{not-valid-json',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        self._assert_checkout_still_pending()

    def test_webhook_missing_merchant_order_id_with_valid_transaction_finalizes(self):
        payload = {
            'status': 'success',
            'transaction_id': 'txn_fraud_guard',
            'sale_price': int(self.checkout_total * 100),
            'currency': 'ILS',
        }
        res = self._post_signed_webhook(payload)
        self.assertEqual(res.status_code, 200)
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.ticket.status, 'sold')

    def test_webhook_unknown_order_does_not_finalize(self):
        payload = {
            'merchant_order_id': '999999',
            'status': 'success',
            'transaction_id': 'txn_fraud_guard',
            'sale_price': int(self.checkout_total * 100),
            'currency': 'ILS',
        }
        res = self._post_signed_webhook(payload)
        self.assertEqual(res.status_code, 403)
        self._assert_checkout_still_pending()

    def test_webhook_unpaid_payme_api_does_not_finalize(self):
        payload = self._success_webhook_payload(self.order)
        self.mock_confirm_payme_sale_status.return_value = dict(MOCK_PAYME_SALE_NOT_FOUND)
        res = self._post_signed_webhook(payload, signature='deadbeefdeadbeefdeadbeefdeadbeef')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data.get('finalized'))
        self._assert_checkout_still_pending()

    def test_webhook_transaction_id_mismatch_does_not_finalize(self):
        # Wrong TRAN and no matching sale id — must not resolve via merchant_order_id alone.
        payload = self._success_webhook_payload(self.order, transaction_id='txn_attacker')
        res = self._post_signed_webhook(payload)
        self.assertIn(res.status_code, (403, 404))
        self._assert_checkout_still_pending()

    def test_webhook_amount_mismatch_does_not_finalize(self):
        payload = self._success_webhook_payload(self.order)
        payload['sale_price'] = 100  # 1.00 ILS instead of 115.00
        res = self._post_signed_webhook(payload)
        self.assertEqual(res.status_code, 403)
        self._assert_checkout_still_pending()

    def test_webhook_failed_status_does_not_finalize_or_create_ledger(self):
        payload = {
            'merchant_order_id': str(self.order.id),
            'status': 'failed',
            'transaction_id': 'txn_fraud_guard',
            'sale_price': int(self.checkout_total * 100),
            'currency': 'ILS',
        }
        self.mock_confirm_payme_sale_status.return_value = dict(MOCK_PAYME_SALE_FAILED)
        res = self._post_signed_webhook(payload)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data.get('finalized'))
        self._assert_checkout_still_pending()

    def test_webhook_without_payme_api_confirm_does_not_finalize(self):
        payload = self._success_webhook_payload(self.order)
        body, _ = sign_payme_payload(payload)
        self.mock_confirm_payme_sale_status.return_value = {
            'ok': False,
            'found': False,
            'status': None,
            'raw': None,
            'error': 'seller_not_configured',
        }
        res = self.client.post(
            WEBHOOK_URL,
            body,
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 503, res.content)
        self.assertFalse(res.data.get('finalized'))
        self._assert_checkout_still_pending()

    def test_webhook_missing_signature_header_finalizes_in_sandbox(self):
        payload = self._success_webhook_payload(self.order)
        body, _ = sign_payme_payload(payload)
        res = self.client.post(
            WEBHOOK_URL,
            body,
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)


class PayMeDirectViewFailureTests(TestCase):
    """Direct view-level checks using APIRequestFactory (no DB marketplace setup)."""

    @override_settings(PAYME_IS_SANDBOX=True, DEBUG=True)
    def test_webhook_non_object_payload_rejected(self):
        factory = APIRequestFactory()
        body = json.dumps(['not', 'an', 'object']).encode('utf-8')
        request = factory.post(
            WEBHOOK_URL,
            data=body,
            content_type='application/json',
        )
        response = payme_webhook(request)
        self.assertEqual(response.status_code, 400)
