"""Shared PayMe IPN signature helpers for webhook tests."""
from __future__ import annotations

import json
from unittest.mock import patch
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
}

MOCK_PAYME_SALE_SUCCESS = {
    'ok': True,
    'found': True,
    'status': 'success',
    'raw': {'sale_status': 'completed'},
    'error': None,
}

MOCK_PAYME_SALE_PENDING = {
    'ok': True,
    'found': True,
    'status': 'pending',
    'raw': {'sale_status': 'pending'},
    'error': None,
}

MOCK_PAYME_SALE_AUTHORIZED = {
    'ok': True,
    'found': True,
    'status': 'authorized',
    'raw': {'sale_status': 'authorized'},
    'error': None,
}

MOCK_PAYME_SALE_FAILED = {
    'ok': True,
    'found': True,
    'status': 'failed',
    'raw': {'sale_status': 'failed'},
    'error': None,
}

MOCK_PAYME_SALE_NOT_FOUND = {
    'ok': True,
    'found': False,
    'status': None,
    'raw': {'items': [], 'status_code': 0},
    'error': None,
}

MOCK_PAYME_SALE_TIMEOUT = {
    'ok': False,
    'found': False,
    'status': None,
    'raw': None,
    'error': 'timeout',
}


class MockPayMeSaleConfirmMixin:
    """Fulfillment is gated on get-sales/get-transactions; tests mock that lookup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._payme_confirm_patcher = patch(
            'users.payme_views.confirm_payme_sale_status',
            return_value=dict(MOCK_PAYME_SALE_SUCCESS),
        )
        cls.mock_confirm_payme_sale_status = cls._payme_confirm_patcher.start()
        cls.addClassCleanup(cls._payme_confirm_patcher.stop)

    def _pre_setup(self):
        super()._pre_setup()
        mock = getattr(type(self), 'mock_confirm_payme_sale_status', None)
        if mock is not None:
            mock.reset_mock(return_value=True, side_effect=True)
            mock.return_value = dict(MOCK_PAYME_SALE_SUCCESS)
            mock.side_effect = None


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
