"""
Golden test: production Apple Pay PayMe notify signature (MD5).

Uses the exact raw body captured via PayMeWebhookLog. Requires PAYME_WEBHOOK_SECRET
(the production signing secret) in the environment — never hardcode it.
"""
from __future__ import annotations

import hashlib
import os
import unittest

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from users.payments import (
    build_payme_sorted_values_sign_string,
    compute_payme_md5_signature,
    extract_payme_raw_sign_fields,
    parse_payme_raw_body_fields,
    verify_payme_webhook_request,
)

# Exact production wire body (Order ~129 Apple Pay bad_signature capture).
PRODUCTION_APPLE_PAY_RAW = (
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
PRODUCTION_TARGET_SIG = 'd061550eeb2184b59d51ceb8c2c62f34'


class PayMeMd5AlgorithmUnitTests(TestCase):
    def test_md5_string_to_hash_plus_secret(self):
        sth = 'ILSsale-completetxn_x110.50'
        secret = 'unit_test_secret'
        expected = hashlib.md5((sth + secret).encode('utf-8')).hexdigest()
        self.assertEqual(compute_payme_md5_signature(sth, secret), expected)
        self.assertEqual(len(expected), 32)

    def test_parse_qsl_decodes_plus_and_percent(self):
        fields = parse_payme_raw_body_fields(PRODUCTION_APPLE_PAY_RAW.encode('utf-8'))
        self.assertEqual(fields.get('buyer_name'), 'Shoham Yakov')
        self.assertEqual(fields.get('buyer_email'), 'shohamyaccov@gmail.com')
        self.assertEqual(fields.get('buyer_card_mask'), '532619******1322')
        self.assertIn('—', fields.get('sale_description', ''))  # em-dash from %E2%80%94
        self.assertNotIn('%E2%80%94', fields.get('sale_description', ''))
        self.assertNotIn('+', fields.get('sale_description', ''))  # + became spaces


@unittest.skipUnless(
    bool((os.environ.get('PAYME_WEBHOOK_SECRET') or '').strip()),
    'Set PAYME_WEBHOOK_SECRET to run the production Apple Pay MD5 golden test',
)
class PayMeProductionApplePayMd5GoldenTests(TestCase):
    def test_exact_production_payload_md5_matches(self):
        secret = (os.environ.get('PAYME_WEBHOOK_SECRET') or '').strip()
        raw = PRODUCTION_APPLE_PAY_RAW.encode('utf-8')
        fields = parse_payme_raw_body_fields(raw)
        sign_fields = {k: v for k, v in fields.items() if k != 'payme_signature'}
        string_to_hash = build_payme_sorted_values_sign_string(sign_fields)
        digest = compute_payme_md5_signature(string_to_hash, secret)
        self.assertEqual(
            digest,
            PRODUCTION_TARGET_SIG,
            msg=(
                f'MD5 mismatch.\nstring_to_hash={string_to_hash!r}\n'
                f'got={digest}\nexpected={PRODUCTION_TARGET_SIG}'
            ),
        )

        request = APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=raw,
            content_type='application/x-www-form-urlencoded',
        )
        extracted = extract_payme_raw_sign_fields(request, raw_body=raw)
        self.assertEqual(
            build_payme_sorted_values_sign_string(extracted),
            string_to_hash,
        )

        order = type(
            'O',
            (),
            {
                'pk': 129,
                'payme_transaction_id': 'SALE1786-378288U7-ZKNHJCKI-1NH0A43E',
                'currency': 'ILS',
                'total_paid_by_buyer': type('D', (), {'__str__': lambda self: '5.35'})(),
                'total_amount': type('D', (), {'__str__': lambda self: '5.35'})(),
            },
        )()
        # Amount in payload is agorot-style 535; verification uses order totals — use Decimal.
        from decimal import Decimal
        from types import SimpleNamespace

        order = SimpleNamespace(
            pk=129,
            payme_transaction_id='SALE1786-378288U7-ZKNHJCKI-1NH0A43E',
            currency='ILS',
            total_paid_by_buyer=Decimal('5.35'),
            total_amount=Decimal('5.35'),
        )

        with override_settings(PAYME_WEBHOOK_SECRET=secret, PAYME_IS_SANDBOX=False, DEBUG=False):
            # Signature-only check path: verify will also check amount/currency/txn.
            # price=535 means 5.35 ILS in agorot.
            ok, reason = verify_payme_webhook_request(
                request,
                payload=dict(fields),
                order=order,
                raw_body=raw,
                signature_payload=extracted,
            )
        # Signature must not fail; amount mismatch is acceptable to surface separately.
        self.assertNotEqual(reason, 'bad_signature', msg=f'verify failed: {reason}')
        self.assertNotEqual(reason, 'missing_signature_header')
