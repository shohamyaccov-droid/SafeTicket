"""Shared PayMe IPN signature helpers for webhook tests."""
from __future__ import annotations

import json
from urllib.parse import urlencode

from rest_framework.test import APIRequestFactory

from users.payments import compute_payme_ipn_md5_signature

TEST_PAYME_API_KEY = 'test_merchant_key'
TEST_PAYME_API_PASSWORD = 'test_merchant_password'

PAYME_IPN_TEST_SETTINGS = {
    'PAYME_API_KEY': TEST_PAYME_API_KEY,
    'PAYME_API_PASSWORD': TEST_PAYME_API_PASSWORD,
    'PAYME_IS_SANDBOX': False,
    'DEBUG': False,
    'PAYME_CONFIRM_SUCCESS_VIA_API': False,
}


def _ipn_ids_from_payload(payload: dict) -> tuple[str, str]:
    txn = str(
        payload.get('payme_transaction_id')
        or payload.get('transaction_id')
        or payload.get('transactionId')
        or ''
    )
    sale = str(payload.get('payme_sale_id') or payload.get('sale_id') or txn)
    return txn, sale


def sign_payme_ipn_payload(
    payload: dict,
    *,
    merchant_key: str = TEST_PAYME_API_KEY,
    merchant_password: str = TEST_PAYME_API_PASSWORD,
) -> dict:
    unsigned = {
        k: v
        for k, v in payload.items()
        if k not in ('payme_signature', 'paymeSignature', 'signature')
    }
    txn, sale = _ipn_ids_from_payload(unsigned)
    sig = compute_payme_ipn_md5_signature(
        merchant_key=merchant_key,
        merchant_password=merchant_password,
        payme_transaction_id=txn,
        payme_sale_id=sale,
    )
    signed = {**unsigned, 'payme_signature': sig}
    if txn and 'payme_transaction_id' not in signed:
        signed['payme_transaction_id'] = txn
    if sale and 'payme_sale_id' not in signed:
        signed['payme_sale_id'] = sale
    return signed


def payme_ipn_json_request(payload: dict, **sign_kw):
    signed = sign_payme_ipn_payload(payload, **sign_kw)
    body = json.dumps(signed, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    request = APIRequestFactory().post(
        '/api/payments/webhook/payme/',
        data=body,
        content_type='application/json',
    )
    return request, signed, body


def payme_ipn_form_request(fields: dict, **sign_kw):
    signed = sign_payme_ipn_payload(fields, **sign_kw)
    form_body = urlencode(signed)
    request = APIRequestFactory().post(
        '/api/payments/webhook/payme/',
        data=form_body,
        content_type='application/x-www-form-urlencoded',
    )
    return request, signed, form_body
