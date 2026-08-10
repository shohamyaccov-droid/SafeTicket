"""
Offline matcher for PayMe Apple Pay payme_signature.

Usage (from backend/):
  set PAYME_WEBHOOK_SECRET=your_secret
  python match_payme_signature.py

Or:
  python match_payme_signature.py YOUR_SECRET
"""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
from urllib.parse import parse_qsl, unquote, unquote_plus

RAW = (
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
TARGET = 'd061550eeb2184b59d51ceb8c2c62f34'
SIG_KEYS = {'payme_signature', 'paymeSignature', 'signature'}


def md5_hex(s: str) -> str:
    return hashlib.md5(s.encode('utf-8')).hexdigest()


def sorted_values(fields: dict[str, str]) -> str:
    return ''.join(fields[k] for k in sorted(fields) if k not in SIG_KEYS)


def fields_parse_qsl() -> dict[str, str]:
    return {k: v for k, v in parse_qsl(RAW, keep_blank_values=True)}


def fields_unquote() -> dict[str, str]:
    out: dict[str, str] = {}
    for part in RAW.split('&'):
        k, _, v = part.partition('=')
        out[k] = unquote(v)
    return out


def fields_unquote_plus_manual() -> dict[str, str]:
    out: dict[str, str] = {}
    for part in RAW.split('&'):
        k, _, v = part.partition('=')
        out[k] = unquote_plus(v)
    return out


def fields_raw_encoded() -> dict[str, str]:
    out: dict[str, str] = {}
    for part in RAW.split('&'):
        k, _, v = part.partition('=')
        out[k] = v
    return out


def main() -> int:
    secret = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get('PAYME_WEBHOOK_SECRET', '')).strip()
    if not secret:
        print('ERROR: pass secret as argv1 or set PAYME_WEBHOOK_SECRET', file=sys.stderr)
        return 2

    variants: list[tuple[str, dict[str, str]]] = [
        ('parse_qsl', fields_parse_qsl()),
        ('unquote', fields_unquote()),
        ('unquote_plus', fields_unquote_plus_manual()),
        ('raw_encoded', fields_raw_encoded()),
    ]

    hits: list[str] = []
    for name, fields in variants:
        sth = sorted_values(fields)
        trials = {
            f'{name}: md5(sth+secret)': md5_hex(sth + secret),
            f'{name}: md5(secret+sth)': md5_hex(secret + sth),
            f'{name}: hmac_sha256(sth)': hmac.new(secret.encode(), sth.encode(), hashlib.sha256).hexdigest(),
            f'{name}: md5(sth) alone': md5_hex(sth),
        }
        txn = fields.get('payme_transaction_id', '')
        sale = fields.get('payme_sale_id', '')
        trials[f'{name}: md5(secret+txn+sale)'] = md5_hex(secret + txn + sale)
        trials[f'{name}: md5(txn+sale+secret)'] = md5_hex(txn + sale + secret)
        trials[f'{name}: md5(sale+txn+secret)'] = md5_hex(sale + txn + secret)
        for label, digest in trials.items():
            mark = ' HIT' if digest == TARGET else ''
            if mark:
                hits.append(label)
            print(f'{digest}{mark}  {label}')
        print(f'  string_to_hash[{name}] len={len(sth)}')

    print('TARGET', TARGET)
    if hits:
        print('MATCHED:', hits)
        return 0
    print('NO MATCH')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
