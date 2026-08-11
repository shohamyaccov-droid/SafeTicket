"""
Offline verifier for PayMe IPN payme_signature (official PayMe support rule).

Usage (from backend/):
  set PAYME_API_KEY=your_mpl_key
  set PAYME_API_PASSWORD=your_api_password
  python match_payme_signature.py

Or:
  python match_payme_signature.py YOUR_MPL_KEY YOUR_API_PASSWORD
"""
from __future__ import annotations

import os
import sys
from urllib.parse import parse_qsl

from users.payments import compute_payme_ipn_md5_signature

# Order ~129 / Log #1 Apple Pay capture
RAW_ORDER_129 = (
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
TARGET_ORDER_129 = 'd061550eeb2184b59d51ceb8c2c62f34'

# PayMeWebhookLog #6 / Order 131 Apple Pay capture
RAW_LOG6 = (
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
TARGET_LOG6 = 'ce7c84801d5b3822c514b2b3a312facc'


def verify_raw(raw: str, target: str, merchant_key: str, merchant_password: str, label: str) -> bool:
    fields = {k: v for k, v in parse_qsl(raw, keep_blank_values=True)}
    txn = fields.get('payme_transaction_id', '')
    sale = fields.get('payme_sale_id', '')
    digest = compute_payme_ipn_md5_signature(
        merchant_key=merchant_key,
        merchant_password=merchant_password,
        payme_transaction_id=txn,
        payme_sale_id=sale,
    )
    hit = digest == target
    mark = ' HIT' if hit else ''
    print(f'{label}: txn={txn} sale={sale}')
    print(f'  computed={digest}{mark}')
    print(f'  target  ={target}')
    return hit


def main() -> int:
    merchant_key = (
        sys.argv[1] if len(sys.argv) > 1 else os.environ.get('PAYME_API_KEY', '')
    ).strip()
    merchant_password = (
        sys.argv[2] if len(sys.argv) > 2 else os.environ.get('PAYME_API_PASSWORD', '')
    ).strip()
    if not merchant_key or not merchant_password:
        print(
            'ERROR: pass MPL key + API password as argv or set PAYME_API_KEY and PAYME_API_PASSWORD',
            file=sys.stderr,
        )
        return 2

    hits = [
        verify_raw(RAW_ORDER_129, TARGET_ORDER_129, merchant_key, merchant_password, 'Order ~129'),
        verify_raw(RAW_LOG6, TARGET_LOG6, merchant_key, merchant_password, 'Log #6 / Order 131'),
    ]
    if all(hits):
        print('ALL MATCH')
        return 0
    print('NO MATCH')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
