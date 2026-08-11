import json
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from users.models import Order
from users.payments import (
    extract_payme_raw_sign_fields,
    normalize_payme_webhook_status,
    verify_payme_webhook_request,
)
from users.tests.payme_ipn_test_helpers import (
    PAYME_IPN_TEST_SETTINGS,
    payme_ipn_form_request,
    payme_ipn_json_request,
    sign_payme_ipn_payload,
)
from users.views import confirm_order_payment


def _signed_request(payload):
    request, signed_payload, _body = payme_ipn_json_request(payload)
    return request


def _body_signed_request(payload):
    request, signed_payload, _body = payme_ipn_json_request(payload)
    return request, signed_payload


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
    def test_webhook_bypasses_signature_when_credentials_empty_in_sandbox(self):
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

    @override_settings(PAYME_IS_SANDBOX=True, DEBUG=False)
    def test_webhook_rejects_when_api_credentials_missing_in_production(self):
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
        self.assertEqual(reason, 'missing_api_credentials')

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
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

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_webhook_accepts_payme_signature_in_body(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'payme_transaction_id': 'txn_123',
            'payme_sale_id': 'txn_123',
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

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_bit_payload_ipn_signature_with_empty_cc_and_social_id(self):
        """
        Bit IPN: payme_signature = MD5(key + password + payme_transaction_id + payme_sale_id).
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
        request, signed = _body_signed_request(payload)

        ok, reason = verify_payme_webhook_request(
            request,
            payload=signed,
            order=_order(pk=124, payme_transaction_id='txn_123'),
            signature_payload=payload,
        )

        self.assertTrue(ok, reason)
        self.assertEqual(reason, 'ok')

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_apple_pay_form_urlencoded_ipn_signature(self):
        """
        Apple Pay IPN: signature uses payme_transaction_id + payme_sale_id from raw POST.
        """
        raw_fields = {
            'buyer_card_exp': '',
            'buyer_card_mask': '',
            'currency': 'ILS',
            'is_token_sale': 'true',
            'notify_type': 'sale-complete',
            'payme_sale_id': 'txn_apple_raw_1',
            'payme_transaction_id': 'txn_apple_raw_1',
            'payme_transaction_card_brand': '',
            'sale_payment_method': 'apple-pay',
            'sale_price': '110.50',
            'status': '0',
        }
        request, signed, _form = payme_ipn_form_request(raw_fields)

        casted_payload = {
            **signed,
            'buyer_card_exp': None,
            'buyer_card_mask': None,
            'is_token_sale': True,
            'sale_price': 110.5,
            'status': 0,
            'merchant_order_id': '126',
        }

        raw_extracted = extract_payme_raw_sign_fields(request)
        self.assertEqual(raw_extracted.get('payme_transaction_id'), 'txn_apple_raw_1')
        self.assertEqual(raw_extracted.get('payme_sale_id'), 'txn_apple_raw_1')

        ok, reason = verify_payme_webhook_request(
            request,
            payload=casted_payload,
            order=_order(pk=126, payme_transaction_id='txn_apple_raw_1', total_amount=Decimal('110.50')),
            signature_payload=casted_payload,
        )
        self.assertTrue(ok, reason)
        self.assertEqual(reason, 'ok')

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_injected_merchant_order_id_does_not_affect_ipn_signature(self):
        """merchant_order_id is not part of the IPN signature material."""
        original = {
            'currency': 'ILS',
            'notify_type': 'sale-complete',
            'payme_sale_id': 'txn_123',
            'payme_transaction_id': 'txn_123',
            'sale_price': 11000,
            'status': 'completed',
        }
        request, signed = _body_signed_request(original)
        canonical = {**signed, 'merchant_order_id': '123'}

        ok, reason = verify_payme_webhook_request(
            request,
            payload=canonical,
            order=_order(),
            signature_payload=original,
        )

        self.assertTrue(ok, reason)
        self.assertEqual(reason, 'ok')

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_injected_merchant_order_id_ignored_even_without_signature_payload(self):
        """Raw POST txn/sale ids drive IPN verification even if payload was mutated."""
        original = {
            'currency': 'ILS',
            'notify_type': 'sale-complete',
            'payme_sale_id': 'txn_apple_126',
            'payme_transaction_id': 'txn_apple_126',
            'sale_price': 11000,
            'status': 'completed',
        }
        request, signed = _body_signed_request(original)
        mutated = {**signed, 'merchant_order_id': '126'}

        ok, reason = verify_payme_webhook_request(
            request,
            payload=mutated,
            order=_order(pk=126, payme_transaction_id='txn_apple_126'),
        )

        self.assertTrue(ok, reason)
        self.assertEqual(reason, 'ok')

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
    def test_webhook_rejects_bad_body_signature(self):
        payload = {
            'merchant_order_id': '123',
            'transaction_id': 'txn_123',
            'payme_transaction_id': 'txn_123',
            'payme_sale_id': 'txn_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
            'payme_signature': 'not-a-valid-signature',
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

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
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

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
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

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
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

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
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

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
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

    @override_settings(**PAYME_IPN_TEST_SETTINGS)
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
