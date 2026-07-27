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
        '/api/payments/webhook/payme/',
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
    @override_settings(PAYME_WEBHOOK_SECRET='', PAYME_IS_SANDBOX=True, DEBUG=True)
    def test_webhook_bypasses_hmac_when_secret_empty_in_sandbox(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
        }

        ok, reason = verify_payme_webhook_request(
            APIRequestFactory().post(
                '/api/payments/webhook/payme/',
                data=json.dumps(payload).encode('utf-8'),
                content_type='application/json',
            ),
            payload=payload,
            order=_order(),
        )

        self.assertTrue(ok)
        self.assertEqual(reason, 'ok')

    @override_settings(PAYME_WEBHOOK_SECRET='', PAYME_IS_SANDBOX=True, DEBUG=False)
    def test_webhook_rejects_when_secret_missing_in_production(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
        }

        ok, reason = verify_payme_webhook_request(
            APIRequestFactory().post(
                '/api/payments/webhook/payme/',
                data=json.dumps(payload).encode('utf-8'),
                content_type='application/json',
            ),
            payload=payload,
            order=_order(),
        )

        self.assertFalse(ok)
        self.assertEqual(reason, 'missing_signature_header')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False)
    def test_webhook_rejects_missing_signature_in_production(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
        }

        ok, reason = verify_payme_webhook_request(
            APIRequestFactory().post(
                '/api/payments/webhook/payme/',
                data=json.dumps(payload).encode('utf-8'),
                content_type='application/json',
            ),
            payload=payload,
            order=_order(),
        )

        self.assertFalse(ok)
        self.assertEqual(reason, 'missing_signature_header')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False)
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

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False)
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

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False)
    def test_webhook_accepts_sale_id_when_transaction_id_differs(self):
        """Apple Pay often sends TRAN + original payme_sale_id; either must verify."""
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'TRAN_APPLE_NEW',
            'payme_sale_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'completed',
        }

        ok, reason = verify_payme_webhook_request(
            _signed_request(payload),
            payload=payload,
            order=_order(),
        )

        self.assertTrue(ok)
        self.assertEqual(reason, 'ok')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False)
    def test_webhook_ignores_mismatched_generic_order_id_when_sale_matches(self):
        """PayMe-internal order_id must not reject a valid sale-id callback."""
        payload = {
            'order_id': '999001',
            'transaction_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'completed',
        }

        ok, reason = verify_payme_webhook_request(
            _signed_request(payload),
            payload=payload,
            order=_order(),
        )

        self.assertTrue(ok)
        self.assertEqual(reason, 'ok')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False)
    def test_webhook_skips_amount_when_omitted(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'currency': 'ILS',
            'status': 'completed',
        }

        ok, reason = verify_payme_webhook_request(
            _signed_request(payload),
            payload=payload,
            order=_order(),
        )

        self.assertTrue(ok)
        self.assertEqual(reason, 'ok')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False)
    def test_webhook_rejects_explicit_merchant_order_mismatch(self):
        payload = {
            'merchant_order_id': '999999',
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
        self.assertEqual(reason, 'merchant_order_id_mismatch')

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
