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

    def test_webhook_unknown_status_does_not_silently_return_200(self):
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
        self.assertEqual(res.status_code, 409, res.content)
        self.assertFalse(res.data.get('finalized'))
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

    @override_settings(PAYME_IS_SANDBOX=False)
    def test_webhook_rejects_bad_signature(self):
        payload = {
            'merchant_order_id': str(self.order.id),
            'status': 'success',
            'transaction_id': 'webhook_txn_1',
            'sale_price': 11500,
            'currency': 'ILS',
        }
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        res = self.client.post(
            '/api/payments/webhook/payme/',
            body,
            content_type='application/json',
            HTTP_X_PAYME_SIGNATURE='bad-signature',
        )
        self.assertEqual(res.status_code, 403)
