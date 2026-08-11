"""
Payme webhook → order finalization (mocked HTTP to Payme init is optional).
Run: cd backend && python manage.py test tests.test_payme_flow -v 2
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, SellerPayout, Ticket
from users.tests.payme_ipn_test_helpers import PAYME_IPN_TEST_SETTINGS, sign_payme_ipn_payload

User = get_user_model()


@override_settings(
    DEBUG=True,
    PAYME_SELLER_ID='MPL-TEST-SELLER',
    PAYME_IS_SANDBOX=True,
    PAYME_SANDBOX_ACCOUNT_EMAIL='tradetix.support+1@gmail.com',
    PAYME_API_URL='https://testpay.payme.io/api',
    PAYME_WEBHOOK_SECRET='whsec_test',
)
class PaymeWebhookFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        future = timezone.now() + timedelta(days=30)
        self.seller = User.objects.create_user(
            username='payme_seller',
            email='payme_seller@test.invalid',
            password='x',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='payme_buyer',
            email='payme_buyer@test.invalid',
            password='x',
            role='buyer',
            phone_number='0501234567',
        )
        artist = Artist.objects.create(name='Payme Artist')
        self.event = Event.objects.create(
            name='Payme Event',
            artist=artist,
            date=future,
            venue='מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        pdf = SimpleUploadedFile('t.pdf', b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n', content_type='application/pdf')
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=1,
            status='reserved',
            reserved_by=self.buyer,
            reserved_at=timezone.now(),
            pdf_file=pdf,
            verification_status='מאומת',
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='pending_payment',
            total_amount=Decimal('115.00'),
            total_paid_by_buyer=Decimal('115.00'),
            currency='ILS',
            quantity=1,
            event_name=self.event.name,
            ticket_ids=[self.ticket.id],
            guest_email=None,
            payme_transaction_id='webhook_txn_1',
        )

    @patch('users.payme_views.generate_payme_sale_for_order')
    def test_payme_init_returns_redirect(self, mock_generate):
        mock_generate.return_value = {
            'payme_sale_url': 'https://testpay.payme.io/hosted/test',
            'transaction_id': 'txn_123',
            'raw': {'status_code': 0},
        }
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            '/api/users/payments/payme/init/',
            {
                'order_id': self.order.id,
                'success_url': 'http://localhost:5173/checkout/success',
                'failure_url': 'http://localhost:5173/checkout/failure',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIn('redirect_url', res.data)
        self.assertIn('payme_sale_url', res.data)
        self.assertEqual(res.data['redirect_url'], 'https://testpay.payme.io/hosted/test')
        self.order.refresh_from_db()
        self.assertEqual(self.order.payme_transaction_id, 'txn_123')

    @override_settings(PAYME_SELLER_ID='')
    def test_payme_init_503_when_not_configured(self):
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            '/api/users/payments/payme/init/',
            {
                'order_id': self.order.id,
                'success_url': 'http://localhost/s',
                'failure_url': 'http://localhost/f',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 503)

    def test_webhook_marks_paid_via_finalize(self):
        """Webhook success + merchant_order_id runs finalize (inventory + paid)."""
        payload = {
            'merchant_order_id': str(self.order.id),
            'status': 'success',
            'transaction_id': 'webhook_txn_1',
            'sale_price': 11500,
            'currency': 'ILS',
        }
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        sig = hmac.new(b'whsec_test', body, hashlib.sha256).hexdigest()
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
            HTTP_X_PAYME_SIGNATURE=sig,
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payme_status, 'success')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'sold')
        self.assertTrue(SellerPayout.objects.filter(order=self.order).exists())

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_webhook_marks_paid_with_payme_signature_in_body(self):
        """Production PayMe sends payme_signature in the POST body (IPN MD5)."""
        unsigned = {
            'merchant_order_id': str(self.order.id),
            'status': 'success',
            'payme_sale_id': 'webhook_txn_1',
            'payme_transaction_id': 'webhook_txn_1',
            'payme_status': 'completed',
            'sale_price': 11500,
            'currency': 'ILS',
        }
        payload = sign_payme_ipn_payload(unsigned)
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'sold')

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_bit_auth_then_capture_finalizes_with_empty_card_fields(self):
        """
        Bit sends Authorisation (תפיסת מסגרת) then Capture (מכירה) with empty CC fields.
        Generic status=1 must not hide notify_type=sale-complete.
        """
        auth_payload = {
            'merchant_order_id': str(self.order.id),
            'status': '1',
            'notify_type': 'sale-authorized',
            'payme_sale_status': 'תפיסת מסגרת',
            'payme_sale_id': 'webhook_txn_1',
            'payme_transaction_id': 'webhook_txn_1',
            'sale_price': 11500,
            'currency': 'ILS',
            'payment_method': 'bit',
            'buyer_card_mask': '',
            'buyer_card_exp': None,
            'payme_transaction_card_brand': '',
        }
        auth_payload = sign_payme_ipn_payload(auth_payload)
        auth_body = json.dumps(auth_payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        auth_res = self.client.post(
            '/api/payments/webhook/payme/',
            auth_body,
            content_type='application/json',
        )
        self.assertEqual(auth_res.status_code, 200, auth_res.content)
        # Authorisation may finalize (escrow-style) or ACK without finalizing — must not 4xx/5xx.
        self.assertTrue(auth_res.data.get('received'), auth_res.data)

        capture_payload = {
            'merchant_order_id': str(self.order.id),
            'status': '1',
            'notify_type': 'sale-complete',
            'payme_sale_status': 'מכירה',
            'payme_sale_id': 'webhook_txn_1',
            'payme_transaction_id': 'TRAN_BIT_CAPTURE',
            'payme_transaction_total': 11500,
            'currency': 'ILS',
            'payment_method': 'bit',
            'buyer_card_mask': '',
            'buyer_card_exp': '',
            'payme_transaction_card_brand': None,
        }
        capture_payload = sign_payme_ipn_payload(capture_payload)
        capture_body = json.dumps(capture_payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        capture_res = self.client.post(
            '/api/payments/webhook/payme/',
            capture_body,
            content_type='application/json',
        )
        self.assertEqual(capture_res.status_code, 200, capture_res.content)
        self.assertTrue(capture_res.data.get('finalized'), capture_res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'sold')

    def test_webhook_marks_paid_form_urlencoded(self):
        """PayMe preprod/live sends application/x-www-form-urlencoded callbacks."""
        payload = {
            'merchant_order_id': str(self.order.id),
            'status': 'success',
            'transaction_id': 'webhook_txn_1',
            'sale_price': '11500',
            'currency': 'ILS',
        }
        body = urlencode(payload)
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/x-www-form-urlencoded',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_webhook_marks_paid_form_urlencoded_with_payme_sale_code_fallback(self):
        """Live PayMe callbacks include multiple IDs; match whichever was stored during init."""
        self.order.payme_transaction_id = 'SALE1781-test'
        self.order.save(update_fields=['payme_transaction_id'])
        payload = {
            'payme_sale_code': '15959553',
            'payme_sale_id': 'SALE1781-test',
            'payme_transaction_id': 'TRAN1781-test',
            'status': 'success',
            'price': '11500',
            'currency': 'ILS',
        }
        body = urlencode(payload)
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/x-www-form-urlencoded',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_webhook_marks_paid_with_payme_status_code_zero(self):
        """PayMe may send numeric status_code=0 instead of a textual success status."""
        payload = {
            'merchant_order_id': str(self.order.id),
            'status_code': '0',
            'transaction_id': 'webhook_txn_1',
            'sale_price': '11500',
            'currency': 'ILS',
        }
        body = urlencode(payload)
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/x-www-form-urlencoded',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'sold')

    def test_webhook_unknown_status_acks_without_finalizing(self):
        """
        Non-final statuses must ACK 200 (PayMe Bit: auth before capture) without marking paid.
        Returning 409 previously aborted the notify chain for wallet payments.
        """
        payload = {
            'merchant_order_id': str(self.order.id),
            'status': 'processing',
            'transaction_id': 'webhook_txn_1',
            'sale_price': 11500,
            'currency': 'ILS',
        }
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        sig = hmac.new(b'whsec_test', body, hashlib.sha256).hexdigest()
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
            HTTP_X_PAYME_SIGNATURE=sig,
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('received'))
        self.assertFalse(res.data.get('finalized'))
        self.assertEqual(res.data.get('reason'), 'webhook_status_not_finalizable')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')

    def test_webhook_rejects_invalid_json(self):
        res = self.client.post(
            '/api/payments/webhook/payme/',
            b'not-json',
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)

    def test_webhook_rejects_unknown_payme_transaction_id(self):
        payload = {'status': 'success', 'transaction_id': 'x'}
        body = json.dumps(payload).encode('utf-8')
        sig = hmac.new(b'whsec_test', body, hashlib.sha256).hexdigest()
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
            HTTP_X_PAYME_SIGNATURE=sig,
        )
        self.assertEqual(res.status_code, 404)

    def test_webhook_apple_pay_like_payload_marks_paid(self):
        """
        Apple Pay / wallet notifies often differ from card:
        - PayMe-internal order_id field (not merchant_order_id)
        - New TRAN id plus original payme_sale_id from init
        - Nested sale.status = completed
        - Sometimes no sale_price
        """
        self.order.payme_transaction_id = 'SALE-APPLE-INIT'
        self.order.save(update_fields=['payme_transaction_id'])
        payload = {
            'order_id': 'payme-internal-wallet-oid',
            'transaction_id': 'TRAN-APPLE-WALLET-99',
            'payme_sale_id': 'SALE-APPLE-INIT',
            'notify_type': 'sale-complete',
            'payment_method': 'apple_pay',
            'currency': 'ILS',
            'sale': {'status': 'completed'},
        }
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        sig = hmac.new(b'whsec_test', body, hashlib.sha256).hexdigest()
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
            HTTP_X_PAYME_SIGNATURE=sig,
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payme_status, 'success')
        self.assertEqual(self.order.payme_transaction_id, 'SALE-APPLE-INIT')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'sold')

    def test_webhook_nested_completed_status_with_matching_sale_id(self):
        payload = {
            'payme_sale_id': 'webhook_txn_1',
            'order_id': 'payme-internal-not-our-pk',
            'notify_type': 'sale-complete',
            'sale_price': 11500,
            'currency': 'ILS',
            'payment': {'status': 'completed'},
        }
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        sig = hmac.new(b'whsec_test', body, hashlib.sha256).hexdigest()
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
            HTTP_X_PAYME_SIGNATURE=sig,
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_webhook_idempotent_when_already_paid(self):
        self.order.status = 'paid'
        self.order.save(update_fields=['status'])
        payload = {
            'merchant_order_id': str(self.order.id),
            'status': 'success',
            'transaction_id': 'webhook_txn_1',
            'sale_price': 11500,
            'currency': 'ILS',
        }
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        sig = hmac.new(b'whsec_test', body, hashlib.sha256).hexdigest()
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
            HTTP_X_PAYME_SIGNATURE=sig,
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('finalized'))

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_webhook_rejects_bad_signature(self):
        payload = {
            'merchant_order_id': str(self.order.id),
            'status': 'success',
            'transaction_id': 'webhook_txn_1',
            'payme_transaction_id': 'webhook_txn_1',
            'payme_sale_id': 'webhook_txn_1',
            'sale_price': 11500,
            'currency': 'ILS',
            'payme_signature': 'deadbeefdeadbeefdeadbeefdeadbeef',
        }
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 403)
