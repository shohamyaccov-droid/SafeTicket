"""
Golden tests: production Apple Pay PayMe IPN payme_signature (official MD5 rule).

Requires PAYME_API_KEY and PAYME_API_PASSWORD in the environment for golden tests.
"""
from __future__ import annotations

import os
import unittest
from decimal import Decimal
from types import SimpleNamespace

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from users.payments import (
    compute_payme_ipn_md5_signature,
    parse_payme_raw_body_fields,
    verify_payme_webhook_request,
)

# Order ~129 / Log #1 Apple Pay capture
PRODUCTION_APPLE_PAY_RAW_ORDER_129 = (
    'payme_status=success&status_error_code=0&status_code=0'
    '&payme_sale_id=SALE1786-378288U7-ZKNHJCKI-1NH0A43E&payme_sale_code=106406565'
    '&sale_created=2026-08-10+19%3A11%3A28&payme_sale_status=completed&sale_status=completed'
    '&currency=ILS&sale_payment_method=apple-pay&is_token_sale=0&price=535'
    '&payme_signature=d061550eeb2184b59d51ceb8c2c62f34'
    '&sale_description=TradeTix+%E2%80%94+%D7%9E%D7%95%D7%A8+%D7%A8%D7%91%D7%99%D7%A2%D7%99+-+%D7%94%D7%99%D7%9B%D7%9C+%D7%9E%D7%A0%D7%95%D7%A8%D7%94+%D7%9E%D7%91%D7%98%D7%97%D7%99%D7%9D+%E2%80%94+13.08.2026'
    '&sale_type=Sale&payme_transaction_id=TRAN1786-3782963H-UBNU5P1E-MVXPW6YO'
    '&payme_transaction_total=535&payme_transaction_card_brand=Mastercard'
    '&payme_transaction_auth_number=5444668&payme_transaction_voucher=77005468'
    '&payme_transaction_emv_uid=26081019113719921984027&payme_transaction_acquirer=PayMe'
    '&payme_transaction_auth_source=Issuer&payme_transaction_card_issuer=Isracard'
    '&payme_transaction_credit_type=RegularCredit&buyer_name=Shoham+Yakov'
    '&buyer_email=shohamyaccov%40gmail.com&buyer_phone=0509003638'
    '&buyer_card_mask=532619%2A%2A%2A%2A%2A%2A1322&buyer_card_exp=0429'
    '&buyer_card_is_foreign=0&installments=1&transaction_first_payment=535'
    '&transaction_periodical_payment=0&transaction_arn=26081019113719921984027'
    '&sale_paid_date=2026-08-10+19%3A11%3A36&sale_3ds=0&notify_type=sale-complete'
)
PRODUCTION_TARGET_SIG_ORDER_129 = 'd061550eeb2184b59d51ceb8c2c62f34'

# PayMeWebhookLog #6 / Order 131
PRODUCTION_APPLE_PAY_RAW_LOG6 = (
    'payme_status=success&status_error_code=0&status_code=0'
    '&payme_sale_id=SALE1786-385799DM-ZQAI1IJ2-54HZYKQT&payme_sale_code=106414297'
    '&sale_created=2026-08-10+21%3A16%3A39&payme_sale_status=completed&sale_status=completed'
    '&currency=ILS&sale_payment_method=apple-pay&is_token_sale=0&price=535'
    '&payme_signature=ce7c84801d5b3822c514b2b3a312facc'
    '&sale_description=TradeTix+%E2%80%94+%D7%9E%D7%95%D7%A8+%D7%A8%D7%91%D7%99%D7%A2%D7%99+-+%D7%94%D7%99%D7%9B%D7%9C+%D7%9E%D7%A0%D7%95%D7%A8%D7%94+%D7%9E%D7%91%D7%98%D7%97%D7%99%D7%9D+%E2%80%94+13.08.2026'
    '&sale_type=Sale&payme_transaction_id=TRAN1786-385808HA-B1NSVCOX-ZMQ9FHAP'
    '&payme_transaction_total=535&payme_transaction_card_brand=Visa'
    '&payme_transaction_auth_number=+072725&payme_transaction_voucher=77005986'
    '&payme_transaction_emv_uid=26081021164919921985050&payme_transaction_acquirer=PayMe'
    '&payme_transaction_auth_source=Issuer&payme_transaction_card_issuer=Max'
    '&payme_transaction_credit_type=RegularCredit&buyer_name=Shoham+Yakov'
    '&buyer_email=shohamyaccov%40gmail.com&buyer_phone=0509003638'
    '&buyer_card_mask=401047%2A%2A%2A%2A%2A%2A0511&buyer_card_exp=1231'
    '&buyer_card_is_foreign=0&installments=1&transaction_first_payment=535'
    '&transaction_periodical_payment=0&transaction_arn=26081021164919921985050'
    '&sale_paid_date=2026-08-10+21%3A16%3A48&sale_3ds=0&notify_type=sale-complete'
)
PRODUCTION_TARGET_SIG_LOG6 = 'ce7c84801d5b3822c514b2b3a312facc'


def _golden_env_ready() -> bool:
    return bool((os.environ.get('PAYME_API_KEY') or '').strip()) and bool(
        (os.environ.get('PAYME_API_PASSWORD') or os.environ.get('PAYME_API_SECRET') or '').strip()
    )


class PayMeIpnMd5AlgorithmUnitTests(TestCase):
    def test_ipn_md5_key_password_txn_sale(self):
        digest = compute_payme_ipn_md5_signature(
            merchant_key='key_a',
            merchant_password='pass_b',
            payme_transaction_id='TRAN-1',
            payme_sale_id='SALE-1',
        )
        self.assertEqual(len(digest), 32)
        self.assertEqual(
            digest,
            compute_payme_ipn_md5_signature(
                merchant_key='key_a',
                merchant_password='pass_b',
                payme_transaction_id='TRAN-1',
                payme_sale_id='SALE-1',
            ),
        )

    def test_parse_qsl_decodes_plus_and_percent(self):
        fields = parse_payme_raw_body_fields(PRODUCTION_APPLE_PAY_RAW_ORDER_129.encode('utf-8'))
        self.assertEqual(fields.get('buyer_name'), 'Shoham Yakov')
        self.assertEqual(fields.get('buyer_email'), 'shohamyaccov@gmail.com')
        self.assertEqual(fields.get('buyer_card_mask'), '532619******1322')
        self.assertIn('—', fields.get('sale_description', ''))
        self.assertNotIn('%E2%80%94', fields.get('sale_description', ''))
        self.assertNotIn('+', fields.get('sale_description', ''))


@unittest.skipUnless(_golden_env_ready(), 'Set PAYME_API_KEY and PAYME_API_PASSWORD for golden tests')
class PayMeProductionApplePayIpnGoldenTests(TestCase):
    def _assert_payload_matches(self, raw: str, target_sig: str, *, order_pk: int, stored_sale_id: str):
        api_key = (os.environ.get('PAYME_API_KEY') or '').strip()
        api_password = (
            os.environ.get('PAYME_API_PASSWORD') or os.environ.get('PAYME_API_SECRET') or ''
        ).strip()
        raw_bytes = raw.encode('utf-8')
        fields = parse_payme_raw_body_fields(raw_bytes)
        txn = fields.get('payme_transaction_id', '')
        sale = fields.get('payme_sale_id', '')
        digest = compute_payme_ipn_md5_signature(
            merchant_key=api_key,
            merchant_password=api_password,
            payme_transaction_id=txn,
            payme_sale_id=sale,
        )
        self.assertEqual(digest, target_sig, msg=f'txn={txn} sale={sale} got={digest} expected={target_sig}')

        request = APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=raw_bytes,
            content_type='application/x-www-form-urlencoded',
        )
        order = SimpleNamespace(
            pk=order_pk,
            payme_transaction_id=stored_sale_id,
            currency='ILS',
            total_paid_by_buyer=Decimal('5.35'),
            total_amount=Decimal('5.35'),
        )
        with override_settings(
            PAYME_API_KEY=api_key,
            PAYME_API_PASSWORD=api_password,
            PAYME_IS_SANDBOX=False,
            DEBUG=False,
        ):
            ok, reason = verify_payme_webhook_request(
                request,
                payload=dict(fields),
                order=order,
                raw_body=raw_bytes,
            )
        self.assertNotEqual(reason, 'bad_signature', msg=f'verify failed: {reason}')
        self.assertNotEqual(reason, 'missing_signature_header')

    def test_order_129_production_payload(self):
        self._assert_payload_matches(
            PRODUCTION_APPLE_PAY_RAW_ORDER_129,
            PRODUCTION_TARGET_SIG_ORDER_129,
            order_pk=129,
            stored_sale_id='SALE1786-378288U7-ZKNHJCKI-1NH0A43E',
        )

    def test_log6_order_131_production_payload(self):
        self._assert_payload_matches(
            PRODUCTION_APPLE_PAY_RAW_LOG6,
            PRODUCTION_TARGET_SIG_LOG6,
            order_pk=131,
            stored_sale_id='SALE1786-385799DM-ZQAI1IJ2-54HZYKQT',
        )
