import hashlib
import hmac
import json
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from users.models import Order
from users.payments import (
    build_payme_sorted_values_sign_string,
    normalize_payme_webhook_status,
    verify_payme_webhook_request,
)
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


def _body_signed_request(payload, secret='whsec_test'):
    """PayMe production-style: sorted-values HMAC, signature inside JSON body (no header)."""
    unsigned = {k: v for k, v in payload.items() if k not in ('payme_signature', 'paymeSignature', 'signature')}
    sign_string = build_payme_sorted_values_sign_string(unsigned)
    signature = hmac.new(secret.encode('utf-8'), sign_string.encode('utf-8'), hashlib.sha256).hexdigest()
    signed_payload = {**unsigned, 'payme_signature': signature}
    body = json.dumps(signed_payload, separators=(',', ':')).encode('utf-8')
    return (
        APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=body,
            content_type='application/json',
        ),
        signed_payload,
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

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False, DEBUG=False)
    def test_webhook_accepts_payme_signature_in_body(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
        }
        request, signed_payload = _body_signed_request(payload)

        ok, reason = verify_payme_webhook_request(
            request,
            payload=signed_payload,
            order=_order(),
        )

        self.assertTrue(ok, reason)
        self.assertEqual(reason, 'ok')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False, DEBUG=False)
    def test_bit_payload_sorted_values_signature_with_empty_cc_and_social_id(self):
        """
        Bit IPN keys from production logs: empty CC fields + buyer_social_id.
        Signature = HMAC-SHA256(secret, sorted_keys → concatenated values).
        """
        payload = {
            'buyer_card_exp': '',
            'buyer_card_mask': '',
            'buyer_social_id': '123456789',
            'currency': 'ILS',
            'merchant_order_id': '124',
            'notify_type': 'sale-complete',
            'payme_sale_id': 'txn_123',
            'payme_status': 'completed',
            'payme_transaction_card_brand': '',
            'payme_transaction_id': 'txn_123',
            'sale_price': 11000,
            'status': '0',
        }
        sign_string = build_payme_sorted_values_sign_string(payload)
        # Alphabetical key order: buyer_card_exp, buyer_card_mask, buyer_social_id, ...
        self.assertTrue(sign_string.startswith('123456789') or '123456789' in sign_string)
        signature = hmac.new(
            b'whsec_test',
            sign_string.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        signed = {**payload, 'payme_signature': signature}
        body = json.dumps(signed, separators=(',', ':')).encode('utf-8')
        request = APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=body,
            content_type='application/json',
        )

        ok, reason = verify_payme_webhook_request(
            request,
            payload=signed,
            order=_order(pk=124, payme_transaction_id='txn_123'),
            signature_payload=payload,
        )

        self.assertTrue(ok, reason)
        self.assertEqual(reason, 'ok')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False, DEBUG=False)
    def test_injected_merchant_order_id_does_not_break_sorted_signature(self):
        """Canonicalize may append merchant_order_id; HMAC must use original POST fields."""
        original = {
            'currency': 'ILS',
            'notify_type': 'sale-complete',
            'payme_sale_id': 'txn_123',
            'sale_price': 11000,
            'status': 'completed',
        }
        sign_string = build_payme_sorted_values_sign_string(original)
        signature = hmac.new(b'whsec_test', sign_string.encode('utf-8'), hashlib.sha256).hexdigest()
        # Business payload after canonicalize injects merchant_order_id
        canonical = {**original, 'merchant_order_id': '123', 'payme_signature': signature}
        body = json.dumps({**original, 'payme_signature': signature}, separators=(',', ':')).encode('utf-8')
        request = APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=body,
            content_type='application/json',
        )

        ok, reason = verify_payme_webhook_request(
            request,
            payload=canonical,
            order=_order(),
            signature_payload=original,
        )

        self.assertTrue(ok, reason)
        self.assertEqual(reason, 'ok')

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False, DEBUG=False)
    def test_injected_merchant_order_id_ignored_even_without_signature_payload(self):
        """
        If the view accidentally passes a mutated payload as the only HMAC source,
        verification must still succeed by ignoring the injected merchant_order_id.
        """
        original = {
            'currency': 'ILS',
            'notify_type': 'sale-complete',
            'payme_sale_id': 'txn_apple_126',
            'sale_price': 11000,
            'status': 'completed',
        }
        sign_string = build_payme_sorted_values_sign_string(original)
        signature = hmac.new(b'whsec_test', sign_string.encode('utf-8'), hashlib.sha256).hexdigest()
        # Simulate production bug: merchant_order_id filled after order lookup, then hashed.
        mutated = {
            **original,
            'merchant_order_id': '126',
            'payme_signature': signature,
        }
        body = json.dumps(mutated, separators=(',', ':')).encode('utf-8')
        request = APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=body,
            content_type='application/json',
        )

        ok, reason = verify_payme_webhook_request(
            request,
            payload=mutated,
            order=_order(pk=126, payme_transaction_id='txn_apple_126'),
            # Intentionally omit signature_payload — strip path must still pass.
        )

        self.assertTrue(ok, reason)
        self.assertEqual(reason, 'ok')

        # Sanity: hashing the mutated payload (including merchant_order_id) must NOT
        # equal the PayMe signature we generated from the pristine fields.
        mutated_sign = build_payme_sorted_values_sign_string(
            {k: v for k, v in mutated.items() if k != 'payme_signature'}
        )
        self.assertNotEqual(mutated_sign, sign_string)

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test', PAYME_IS_SANDBOX=False, DEBUG=False)
    def test_webhook_rejects_bad_body_signature(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
            'payme_signature': 'not-a-valid-hmac',
        }
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        request = APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=body,
            content_type='application/json',
        )

        ok, reason = verify_payme_webhook_request(
            request,
            payload=payload,
            order=_order(),
        )

        self.assertFalse(ok)
        self.assertEqual(reason, 'bad_signature')

    def test_normalize_prefers_notify_type_over_numeric_status(self):
        tid, norm = normalize_payme_webhook_status(
            {
                'status': '1',
                'notify_type': 'sale-complete',
                'payme_sale_id': 'txn_123',
            }
        )
        self.assertEqual(tid, 'txn_123')
        self.assertEqual(norm, 'success')

    def test_normalize_hebrew_bit_auth_and_sale_labels(self):
        _, auth_norm = normalize_payme_webhook_status(
            {
                'payme_sale_status': 'תפיסת מסגרת',
                'payme_sale_id': 'txn_bit',
                'buyer_card_mask': '',
            }
        )
        self.assertEqual(auth_norm, 'authorized')
        _, sale_norm = normalize_payme_webhook_status(
            {
                'payme_sale_status': 'מכירה',
                'status': '1',
                'payme_sale_id': 'txn_bit',
            }
        )
        self.assertEqual(sale_norm, 'success')

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
