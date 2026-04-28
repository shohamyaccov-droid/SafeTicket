import hashlib
import hmac
import json
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from users.models import Order
from users.payments import verify_payme_webhook_request
from users.views import confirm_order_payment


def _signed_request(payload, secret='whsec_test'):
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return APIRequestFactory().post(
        '/api/payments/webhook/',
        data=body,
        content_type='application/json',
        HTTP_X_PAYME_SIGNATURE=signature,
    )


def _order(**overrides):
    base = {
        'pk': 123,
        'payme_transaction_id': 'txn_123',
        'currency': 'ILS',
        'total_amount': Decimal('110.00'),
        'total_paid_by_buyer': None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class PaymeWebhookVerificationTests(TestCase):
    @override_settings(PAYME_WEBHOOK_SECRET='')
    def test_webhook_requires_secret(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
        }

        ok, reason = verify_payme_webhook_request(
            _signed_request(payload),
            payload=payload,
            order=_order(),
        )

        self.assertFalse(ok)
        self.assertEqual(reason, 'missing_webhook_secret')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test')
    def test_webhook_rejects_transaction_mismatch(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_other',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
        }

        ok, reason = verify_payme_webhook_request(
            _signed_request(payload),
            payload=payload,
            order=_order(),
        )

        self.assertFalse(ok)
        self.assertEqual(reason, 'transaction_id_mismatch')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test')
    def test_webhook_rejects_amount_mismatch(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'sale_price': 10999,
            'currency': 'ILS',
            'status': 'authorized',
        }

        ok, reason = verify_payme_webhook_request(
            _signed_request(payload),
            payload=payload,
            order=_order(),
        )

        self.assertFalse(ok)
        self.assertEqual(reason, 'amount_mismatch')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test')
    def test_webhook_accepts_exact_signed_order_payment(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
        }

        ok, reason = verify_payme_webhook_request(
            _signed_request(payload),
            payload=payload,
            order=_order(),
        )

        self.assertTrue(ok)
        self.assertEqual(reason, 'ok')


class ClientConfirmPaymentSecurityTests(TestCase):
    @override_settings(PAYME_REQUIRE_WEBHOOK_CONFIRMATION=True)
    def test_client_confirm_token_rejected_when_payme_webhook_required(self):
        order = Order.objects.create(
            status='pending_payment',
            total_amount=Decimal('110.00'),
            currency='ILS',
            guest_email='buyer@example.com',
            guest_phone='0501234567',
            payment_confirm_token='client-visible-token',
        )
        request = APIRequestFactory().post(
            f'/api/users/orders/{order.id}/confirm-payment/',
            {
                'payment_confirm_token': 'client-visible-token',
                'guest_email': 'buyer@example.com',
            },
            format='json',
        )

        response = confirm_order_payment(request, order.id)

        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')
