"""
Payme (Payme.io) marketplace / platform integration — test/sandbox first.

Docs vary by merchant onboarding; we POST JSON to PAYME_GENERATE_SALE_URL (default test host)
and merge PAYME_EXTRA_BODY_JSON so ops can align with Payme support without redeploying.

Escrow: prefer authorize / non-capture flow (see PAYME_EXTRA_BODY_JSON defaults in settings).
"""
from __future__ import annotations

import json
import logging
import hashlib
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.utils import OperationalError
from django.utils import timezone

logger = logging.getLogger(__name__)

QUANT = Decimal('0.01')


def _short_hash(value: Any) -> str:
    raw = str(value or '').encode('utf-8', errors='ignore')
    return hashlib.sha256(raw).hexdigest()[:12]


def _sanitize_payme_log_value(key: str, value: Any) -> Any:
    key_l = str(key).lower()
    if any(part in key_l for part in ('secret', 'token', 'key', 'authorization', 'signature')):
        return '***'
    if any(part in key_l for part in ('email', 'phone', 'buyer', 'payee')):
        return '***'
    if 'url' in key_l:
        return '<url>'
    if any(part in key_l for part in ('transaction', 'sale_id', 'tid')) or key_l == 'id':
        return f'hash:{_short_hash(value)}' if value else ''
    if any(part in key_l for part in ('amount', 'price', 'commission', 'total')):
        return '<amount>'
    if isinstance(value, dict):
        return _sanitize_payme_log_payload(value)
    if isinstance(value, list):
        return f'<list:{len(value)}>'
    if isinstance(value, (str, int, float, bool)) or value is None:
        if key_l in ('status', 'normalized', 'currency', 'reason', 'http', 'merchant_order_id'):
            return value
        return '<present>' if value not in (None, '', False) else value
    return f'<{value.__class__.__name__}>'


def _sanitize_payme_log_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(k): _sanitize_payme_log_value(str(k), v) for k, v in payload.items()}
    if isinstance(payload, list):
        return f'<list:{len(payload)}>'
    if payload is None:
        return None
    return f'<{payload.__class__.__name__}>'


def _money_to_agorot(amount: Decimal | str | float | int) -> int:
    d = Decimal(str(amount)).quantize(QUANT, rounding=ROUND_HALF_UP)
    return int(d * 100)


def _dev_payme_payload(payload: Any) -> Any:
    """Sandbox-friendly payload view: keep status/ids, mask secrets and PII."""
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for k, v in payload.items():
            kl = str(k).lower()
            if any(part in kl for part in ('secret', 'signature', 'api_key', 'authorization', 'password')):
                out[str(k)] = '***'
            elif any(part in kl for part in ('email', 'phone', 'buyer_name')):
                out[str(k)] = '***'
            elif isinstance(v, dict):
                out[str(k)] = _dev_payme_payload(v)
            elif isinstance(v, list):
                out[str(k)] = [_dev_payme_payload(x) if isinstance(x, dict) else x for x in v[:20]]
            else:
                out[str(k)] = v
        return out
    return payload


def log_payme_dev(stage: str, *, order_id: int | None = None, **fields: Any) -> None:
    """
    Verbose Payme trace when DEBUG=True (logger + stdout) for sandbox E2E QA.
    Never logs API secrets; emails are masked.
    """
    if not getattr(settings, 'DEBUG', False):
        return
    safe = {k: _dev_payme_payload(v) for k, v in fields.items()}
    msg = f'[PayMe SANDBOX DEBUG] {stage} order_id={order_id} fields={safe}'
    logger.info(msg)
    print(msg, flush=True)


def log_payme(stage: str, *, order_id: int | None = None, payload: Any = None, response: Any = None, exc: BaseException | None = None) -> None:
    """Structured Payme logging (never log raw API secrets)."""
    extra = {'payme_stage': stage, 'order_id': order_id}
    if exc is not None:
        logger.exception('Payme [%s] order_id=%s failed: %s', stage, order_id, exc.__class__.__name__, extra=extra)
        return
    logger.info(
        'Payme [%s] order_id=%s payload=%s response=%s',
        stage,
        order_id,
        _sanitize_payme_log_payload(payload),
        _sanitize_payme_log_payload(response),
        extra=extra,
    )


def _payme_api_password() -> str:
    """Merchant password for PayMe API + IPN signature (PAYME_API_PASSWORD or PAYME_API_SECRET)."""
    return (
        (getattr(settings, 'PAYME_API_PASSWORD', '') or '').strip()
        or (getattr(settings, 'PAYME_API_SECRET', '') or '').strip()
    )


def get_payme_config() -> dict[str, Any]:
    seller_id = (
        getattr(settings, 'PAYME_SELLER_ID', '')
        or getattr(settings, 'PAYME_MERCHANT_ID', '')
        or getattr(settings, 'PAYME_API_KEY', '')
        or ''
    )
    api_key = (getattr(settings, 'PAYME_API_KEY', '') or seller_id or '').strip()
    return {
        'seller_id': (seller_id or '').strip(),
        'merchant_id': (getattr(settings, 'PAYME_MERCHANT_ID', '') or seller_id or '').strip(),
        'api_key': api_key,
        'api_secret': getattr(settings, 'PAYME_API_SECRET', '') or '',
        'api_password': _payme_api_password(),
        'api_url': getattr(settings, 'PAYME_API_URL', 'https://testpay.payme.io/api'),
        'generate_sale_url': getattr(settings, 'PAYME_GENERATE_SALE_URL', 'https://testpay.payme.io/api/generate-sale'),
        'webhook_secret': getattr(settings, 'PAYME_WEBHOOK_SECRET', '') or '',
        'sub_seller_payee_id': getattr(settings, 'PAYME_SUB_SELLER_PAYEE_ID', '') or '',
        'extra_body': getattr(settings, 'PAYME_EXTRA_BODY_JSON', None) or {},
    }


def build_marketplace_generate_sale_body(
    order,
    *,
    buyer_email: str,
    success_url: str,
    failure_url: str,
    seller_payee_id: str | None = None,
) -> dict[str, Any]:
    """
    Marketplace split: seller receives listing proceeds; platform keeps buyer service fee (10% default).
    seller_pay_full_sum=False per Payme marketplace pattern.
    """
    cfg = get_payme_config()
    total = order.total_paid_by_buyer if order.total_paid_by_buyer is not None else order.total_amount
    buyer_fee = order.buyer_service_fee if order.buyer_service_fee is not None else Decimal('0')
    if buyer_fee is None or buyer_fee < 0:
        buyer_fee = Decimal('0')

    sale_price_agorot = _money_to_agorot(total)
    commission_agorot = _money_to_agorot(buyer_fee)

    payee = (seller_payee_id or cfg['sub_seller_payee_id'] or '').strip()
    if not payee and order.ticket and order.ticket.seller_id:
        payee = (getattr(order.ticket.seller, 'email', None) or str(order.ticket.seller_id)).strip()

    body: dict[str, Any] = {
        'seller_pay_full_sum': False,
        'sale_price': sale_price_agorot,
        'currency': (order.currency or 'ILS').upper(),
        'product_name': f'TradeTix Order {order.id}',
        'merchant_order_id': str(order.id),
        'buyer_email': buyer_email,
        'success_url': success_url,
        'failure_url': failure_url,
        'transaction_type': 'authorize',
        'capture': False,
    }
    if payee:
        body['sub_seller'] = {'payee_id': payee}
    if commission_agorot > 0:
        body['commission'] = {'amount': commission_agorot}
    extra = cfg['extra_body']
    if isinstance(extra, dict) and extra:
        body = {**body, **extra}
    return body


def post_generate_sale(body: dict[str, Any]) -> tuple[int, Any]:
    """POST to Payme generate-sale; returns (http_status, parsed_json_or_text)."""
    cfg = get_payme_config()
    url = cfg['generate_sale_url']
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    mid = cfg['merchant_id']
    key = cfg['api_key']
    if mid:
        headers['X-Payme-Merchant-Id'] = mid
    if key:
        headers['X-Api-Key'] = key
        headers['Authorization'] = f'Bearer {key}'

    log_payme('generate_sale_request', order_id=int(body.get('merchant_order_id') or 0) or None, payload=body)
    try:
        r = requests.post(url, json=body, headers=headers, timeout=45)
    except requests.RequestException as e:
        log_payme('generate_sale_http_error', order_id=int(body.get('merchant_order_id') or 0) or None, exc=e)
        raise

    try:
        data = r.json()
    except ValueError:
        data = {'raw': r.text[:2000]}

    log_payme('generate_sale_response', order_id=int(body.get('merchant_order_id') or 0) or None, response={'status': r.status_code, 'body': data})
    return r.status_code, data


def extract_redirect_url(payme_response: Any) -> str | None:
    """Best-effort keys used across Payme / hosted-checkout responses."""
    if not isinstance(payme_response, dict):
        return None
    for key in (
        'payme_sale_url',
        'redirect_url',
        'sale_url',
        'payment_url',
        'payme_url',
        'url',
        'hosted_page_url',
        'checkout_url',
    ):
        v = payme_response.get(key)
        if isinstance(v, str) and v.startswith('http'):
            return v
    nested = payme_response.get('data') or payme_response.get('result')
    if isinstance(nested, dict):
        return extract_redirect_url(nested)
    return None


def extract_transaction_id(payme_response: Any) -> str | None:
    if not isinstance(payme_response, dict):
        return None
    for key in ('transaction_id', 'transactionId', 'payme_transaction_id', 'sale_id', 'id'):
        v = payme_response.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    nested = payme_response.get('data') or payme_response.get('result')
    if isinstance(nested, dict):
        return extract_transaction_id(nested)
    return None


def _nested_dicts(payload: dict[str, Any]):
    """PayMe payloads vary by account/API version; inspect common top-level wrappers only."""
    yield payload
    for key in ('data', 'result', 'payment', 'transaction', 'sale', 'metadata'):
        nested = payload.get(key)
        if isinstance(nested, dict):
            yield nested


def _first_payload_value(payload: dict[str, Any], *keys: str) -> Any:
    wanted = {k.lower() for k in keys}
    for source in _nested_dicts(payload):
        for k, v in source.items():
            if str(k).lower() in wanted:
                return v
    return None


def _extract_merchant_order_id(payload: dict[str, Any]) -> int | None:
    raw = _first_payload_value(
        payload,
        'merchant_order_id',
        'merchantOrderId',
        'order_id',
        'orderId',
    )
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _extract_currency(payload: dict[str, Any]) -> str:
    raw = _first_payload_value(payload, 'currency', 'currency_code', 'currencyCode')
    return str(raw or '').strip().upper()


def _payload_amount_candidates_agorot(payload: dict[str, Any]) -> set[int]:
    """
    Return possible webhook amount interpretations in agorot/cents.

    PayMe docs/responses can use `sale_price` or `price` in minor units, while
    some gateway payloads use decimal major units. We accept only values that
    exactly match the order total after converting either plausible interpretation.
    """
    candidates: set[int] = set()
    minor_keys = {
        'sale_price',
        'saleprice',
        'amount_agorot',
        'amount_cents',
        'amount_minor',
        'price',
        'payme_transaction_total',
        'paymetransactiontotal',
        'transaction_total',
        'transactiontotal',
        'buyer_total',
        'buyertotal',
    }
    all_keys = minor_keys | {
        'amount',
        'total',
        'total_amount',
        'totalamount',
        'transaction_amount',
        'transactionamount',
    }
    for source in _nested_dicts(payload):
        for key, value in source.items():
            key_norm = str(key).lower().replace('-', '').replace('_', '')
            # Compare against underscore-stripped forms for Bit/wallet field aliases.
            minor_compact = {k.replace('_', '') for k in minor_keys}
            all_compact = {k.replace('_', '') for k in all_keys}
            if key_norm not in all_compact:
                continue
            if value in (None, ''):
                continue
            try:
                dec = Decimal(str(value)).quantize(QUANT, rounding=ROUND_HALF_UP)
            except Exception:
                continue
            if key_norm in minor_compact:
                candidates.add(int(dec))
            # Also allow decimal major-unit fields; exact comparison below still protects the order.
            candidates.add(int((dec * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)))
    return candidates


def _expected_order_total_agorot(order) -> int:
    total = order.total_paid_by_buyer if order.total_paid_by_buyer is not None else order.total_amount
    return _money_to_agorot(total)


def _payload_transaction_refs(payload: dict[str, Any]) -> set[str]:
    """All sale/transaction identifiers present in a PayMe webhook (top-level + nested)."""
    keys = {
        'transaction_id',
        'transactionid',
        'payme_transaction_id',
        'paymetransactionid',
        'payme_sale_id',
        'paymesaleid',
        'payme_sale_code',
        'paymesalecode',
        'sale_id',
        'saleid',
        'sale_code',
        'salecode',
        'id',
    }
    refs: set[str] = set()
    for source in _nested_dicts(payload):
        for key, value in source.items():
            kl = str(key).lower().replace('-', '_')
            compact = kl.replace('_', '')
            if kl not in keys and compact not in keys:
                continue
            if value in (None, ''):
                continue
            ref = str(value).strip()
            if ref:
                refs.add(ref)
    return refs


def _status_token_match(normalized: str, tokens: tuple[str, ...]) -> bool:
    """Match status tokens as whole segments (avoids 'complete' matching 'incomplete')."""
    if not normalized:
        return False
    if normalized in tokens:
        return True
    parts = set(normalized.split('_'))
    return any(token in parts for token in tokens)


def _normalize_status_text(raw: Any) -> str:
    s = str(raw or '').strip().lower()
    # Hebrew PayMe dashboard labels arrive URL-encoded / as UTF-8 in Bit notifies.
    hebrew_map = {
        'תפיסת מסגרת': 'authorized',
        'תפיסת_מסגרת': 'authorized',
        'מסגרת': 'authorized',
        'מכירה': 'sale',
        'הושלם': 'completed',
        'שולם': 'paid',
        'בוצע': 'completed',
        'נכשל': 'failed',
        'נדחה': 'declined',
        'בוטל': 'cancelled',
    }
    stripped = str(raw or '').strip()
    if stripped in hebrew_map:
        s = hebrew_map[stripped]
    return s.replace(' ', '_').replace('-', '_')


def _extract_payme_status_raw(payload: dict[str, Any]) -> Any:
    """
    Prefer PayMe notify / sale status fields over a generic `status` / numeric code.

    Bit (and some wallet) IPNs often send status=1 alongside notify_type=sale-complete;
    reading the first matching key in dict order used to treat that as pending and skip
    finalization.
    """
    priority_groups = (
        ('notify_type', 'notifyType', 'event', 'event_type', 'eventType'),
        ('payme_sale_status', 'sale_status', 'saleStatus', 'transaction_status', 'transactionStatus'),
        ('payme_status', 'payment_status', 'paymentStatus'),
        ('status_code', 'payme_status_code', 'statusCode'),
        ('status', 'state'),
    )
    for keys in priority_groups:
        value = _first_payload_value(payload, *keys)
        if value not in (None, ''):
            return value
    return None


def normalize_payme_webhook_status(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (transaction_id, normalized_status) where normalized is success|authorized|failed|pending."""
    tid = None
    for k in (
        'transaction_id',
        'transactionId',
        'payme_transaction_id',
        'payme_sale_id',
        'payme_sale_code',
        'sale_id',
        'sale_code',
        'id',
    ):
        v = _first_payload_value(payload, k)
        if v is not None and str(v).strip():
            tid = str(v).strip()
            break

    raw = _extract_payme_status_raw(payload)
    s = _normalize_status_text(raw)

    if s in ('0', '00'):
        return tid, 'success'
    if s in ('1', '01'):
        # Numeric pending only when no richer notify/sale status was preferred above.
        return tid, 'pending'

    success_tokens = (
        'success',
        'succeeded',
        'completed',
        'complete',
        'paid',
        'captured',
        'capture',
        'sale',
        'ok',
        'approved',
        'salecomplete',
        'chargesucceeded',
        'paymentcompleted',
        'sold',
    )
    auth_tokens = (
        'authorized',
        'authorised',
        'authorization',
        'authorisation',
        'auth',
        'preauth',
        'hold',
        'saleauthorized',
        'saleauthorised',
    )
    fail_tokens = ('fail', 'failed', 'declined', 'error', 'cancel', 'cancelled', 'void', 'rejected')

    # Compact form catches sale_complete / charge_succeeded without false positives.
    # Auth BEFORE success: sale_authorized contains both "sale" and "authorized".
    compact = s.replace('_', '')
    if _status_token_match(s, fail_tokens) or compact in {t.replace('_', '') for t in fail_tokens}:
        return tid, 'failed'
    if _status_token_match(s, auth_tokens) or compact in {t.replace('_', '') for t in auth_tokens}:
        return tid, 'authorized'
    if s == 'sale' or _status_token_match(s, success_tokens) or compact in {
        t.replace('_', '') for t in success_tokens
    }:
        return tid, 'success'
    return tid, 'pending' if s else None


def _payme_webhook_hmac_bypassed() -> bool:
    """Skip IPN signature check only in DEBUG dev/sandbox. Production (DEBUG=False) never bypasses."""
    if not getattr(settings, 'DEBUG', False):
        return False
    cfg = get_payme_config()
    has_creds = bool((cfg['api_key'] or '').strip() and (cfg['api_password'] or '').strip())
    is_sandbox = bool(getattr(settings, 'PAYME_IS_SANDBOX', False))
    return is_sandbox or not has_creds


def compute_payme_ipn_md5_signature(
    *,
    merchant_key: str,
    merchant_password: str,
    payme_transaction_id: str,
    payme_sale_id: str,
) -> str:
    """
    Official PayMe IPN ``payme_signature`` for one-time sales (PayMe support):

    MD5(merchant_key + merchant_password + payme_transaction_id + payme_sale_id)

    Values are concatenated with no separators. Digest is lowercase hex.
    """
    material = (
        f'{merchant_key or ""}'
        f'{merchant_password or ""}'
        f'{payme_transaction_id or ""}'
        f'{payme_sale_id or ""}'
    )
    return hashlib.md5(material.encode('utf-8')).hexdigest()


_PAYME_SIGNATURE_BODY_KEYS = ('payme_signature', 'paymeSignature', 'signature')


def _payme_signable_value(value: Any) -> str:
    """
    Normalize a field for PayMe IPN HMAC material.

    Prefer values that are already strings (raw POST). Never emit Python's
    ``str(True)`` / ``str(False)`` (``'True'``/``'False'``) — PayMe uses lowercase.
    ``None`` becomes ``''`` (empty card fields on Apple Pay / Bit).
    """
    if value is None:
        return ''
    if isinstance(value, bool):
        # JSON booleans only — form POST keeps the literal 'true'/'false' string.
        return 'true' if value else 'false'
    if isinstance(value, (list, tuple)):
        if not value:
            return ''
        return _payme_signable_value(value[-1])
    if isinstance(value, str):
        return value
    # Last resort for leftover parsed numbers — avoid float repr surprises when possible.
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        # Decimal-ish: prefer non-scientific repr; still inferior to raw POST strings.
        text = format(value, 'f')
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
        return text or '0'
    return str(value)


def _payme_signable_items(payload: dict[str, Any]) -> dict[str, str]:
    """
    Flatten webhook fields for HMAC: drop signature keys, keep empty strings.
    """
    items: dict[str, str] = {}
    if not isinstance(payload, dict):
        return items
    for key, value in payload.items():
        key_s = str(key)
        if key_s in _PAYME_SIGNATURE_BODY_KEYS:
            continue
        items[key_s] = _payme_signable_value(value)
    return items


def build_payme_sorted_values_sign_string(payload: dict[str, Any]) -> str:
    """
    PayMe Bit/IPN HMAC material: all POST keys except payme_signature, sorted
    alphabetically, then exact string values concatenated (empty string for nulls).
    """
    items = _payme_signable_items(payload)
    return ''.join(items[k] for k in sorted(items.keys()))


def compute_payme_md5_signature(string_to_hash: str, secret: str) -> str:
    """
    Production PayMe notify signature: MD5(string_to_hash + secret) as lowercase hex.

    ``string_to_hash`` is the alphabetical concatenation of POST field values
    (excluding payme_signature), using form-decoded strings (``parse_qsl`` /
    ``unquote_plus`` so ``+`` → space and ``%XX`` are decoded).
    """
    material = f'{string_to_hash or ""}{secret or ""}'
    return hashlib.md5(material.encode('utf-8')).hexdigest()


def _payme_md5_signature_candidates(
    *,
    string_to_hash: str,
    secret: str,
    sign_source: dict[str, Any],
    raw_body: bytes,
) -> list[tuple[str, str]]:
    """
    Build (label, hex_digest) candidates for PayMe MD5 verification.

    Primary (PayMe docs / production Apple Pay): md5(string_to_hash + secret).
    Also try alternate decode / hyperswitch-style txn+sale digests.
    """
    from urllib.parse import parse_qsl, unquote

    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(label: str, digest: str) -> None:
        if digest and digest not in seen:
            seen.add(digest)
            out.append((label, digest))

    add('md5_sth_plus_secret', compute_payme_md5_signature(string_to_hash, secret))
    add('md5_secret_plus_sth', compute_payme_md5_signature(secret, string_to_hash))

    # Alternate: unquote (keep literal '+') instead of unquote_plus.
    try:
        text = raw_body.decode('utf-8', errors='replace') if isinstance(raw_body, (bytes, bytearray)) else str(raw_body or '')
        alt: dict[str, str] = {}
        for part in text.split('&'):
            if '=' not in part:
                continue
            key, _, val = part.partition('=')
            key_s = str(key)
            if key_s in _PAYME_SIGNATURE_BODY_KEYS:
                continue
            alt[key_s] = unquote(val)
        if alt:
            alt_sth = ''.join(alt[k] for k in sorted(alt.keys()))
            add('md5_unquote_sth_plus_secret', compute_payme_md5_signature(alt_sth, secret))
    except Exception:
        pass

    txn = ''
    sale = ''
    if isinstance(sign_source, dict):
        txn = str(sign_source.get('payme_transaction_id') or '').strip()
        sale = str(sign_source.get('payme_sale_id') or '').strip()
    if txn and sale:
        # Hyperswitch PayMe connector: MD5(secret + txn + sale)
        add('md5_secret_txn_sale', compute_payme_md5_signature(secret + txn + sale, ''))
        add('md5_txn_sale_secret', compute_payme_md5_signature(txn + sale, secret))

    return out


def parse_payme_raw_body_fields(raw_body: bytes | str | None) -> dict[str, str]:
    """
    Parse PayMe notify body with zero Django/DRF interference.

    Form-urlencoded (PayMe IPN / Apple Pay default): ``urllib.parse.parse_qsl``
    with ``keep_blank_values=True`` so empty card fields stay in the dict.
    JSON: ``parse_int=str`` / ``parse_float=str`` so decimals stay textual.

    Never uses ``request.POST`` / ``request.data`` (QueryDict drops blanks / casts).
    """
    out: dict[str, str] = {}
    if raw_body is None:
        return out
    try:
        if isinstance(raw_body, bytes):
            text = raw_body.decode('utf-8', errors='replace')
        else:
            text = str(raw_body)
        if not text:
            return out
        stripped = text.lstrip()
        # Form body (PayMe IPN / Apple Pay notify default)
        if stripped and not stripped.startswith('{') and not stripped.startswith('[') and '=' in stripped:
            from urllib.parse import parse_qsl

            for key, val in parse_qsl(text, keep_blank_values=True):
                out[str(key)] = '' if val is None else str(val)
            return out
        # JSON: preserve number tokens as strings (avoid float 110.5 vs "110.50")
        if stripped.startswith('{'):
            data = json.loads(text, parse_int=str, parse_float=str)
            if isinstance(data, dict):
                for key, val in data.items():
                    key_s = str(key)
                    if isinstance(val, bool):
                        out[key_s] = 'true' if val else 'false'
                    elif val is None:
                        out[key_s] = ''
                    elif isinstance(val, (dict, list)):
                        continue
                    else:
                        out[key_s] = str(val)
    except Exception as exc:
        logger.warning('PayMe raw body parse failed: %s', exc)
    return out


def extract_payme_raw_sign_fields(request=None, *, raw_body: bytes | None = None) -> dict[str, str]:
    """
    Exact PayMe POST fields as strings for HMAC — never DRF/Django QueryDict.

    Source of truth is the raw request body via ``parse_payme_raw_body_fields``
    (``parse_qsl(keep_blank_values=True)``). Signature keys are excluded.
    """
    try:
        body = raw_body if raw_body is not None else (getattr(request, 'body', None) or b'')
    except Exception as exc:
        logger.warning('PayMe raw sign fields: request.body read failed: %s', exc)
        body = b''
    fields = parse_payme_raw_body_fields(body)
    return {k: v for k, v in fields.items() if k not in _PAYME_SIGNATURE_BODY_KEYS}


def _extract_payme_webhook_signature(
    request,
    payload: dict[str, Any],
    *,
    raw_body: bytes | None = None,
) -> str:
    """
    PayMe may send the HMAC in headers (X-Payme-Signature) or inside the POST body
    as payme_signature (production IPN / form callbacks). Prefer header, then raw body,
    then payload dict — never request.POST / request.data.
    """
    header_sig = (
        request.headers.get('X-Payme-Signature')
        or request.headers.get('X-Webhook-Signature')
        or request.META.get('HTTP_X_PAYME_SIGNATURE')
        or request.META.get('HTTP_X_WEBHOOK_SIGNATURE')
        or ''
    )
    if str(header_sig).strip():
        return str(header_sig).strip()

    try:
        body = raw_body if raw_body is not None else (getattr(request, 'body', None) or b'')
    except Exception:
        body = b''
    raw_fields = parse_payme_raw_body_fields(body)
    for key in _PAYME_SIGNATURE_BODY_KEYS:
        value = raw_fields.get(key)
        if value not in (None, ''):
            return str(value).strip()

    if isinstance(payload, dict):
        for key in _PAYME_SIGNATURE_BODY_KEYS:
            value = payload.get(key)
            if value not in (None, ''):
                return str(value).strip()
        # Nested envelopes occasionally used by PayMe/Grow-style notifies
        for nest_key in ('data', 'metadata', 'payment', 'sale', 'result'):
            nested = payload.get(nest_key)
            if not isinstance(nested, dict):
                continue
            for key in _PAYME_SIGNATURE_BODY_KEYS:
                value = nested.get(key)
                if value not in (None, ''):
                    return str(value).strip()
    return ''


def _payme_hmac_body_candidates(
    raw_body: bytes,
    payload: dict[str, Any],
    *,
    signature_payload: dict[str, Any] | None = None,
) -> list[bytes]:
    """
    Bodies / strings PayMe may have signed.

    Primary (Bit / body payme_signature): alphabetical keys → concatenate values.
    Also try key+value concat and form-urlencoded, plus raw body for header signatures.

    Prefer signature_payload (pre-canonicalize / raw POST strings). Always also try a
    variant that drops merchant_order_id / merchantOrderId so backend-injected merchant
    ids never poison HMAC.
    """
    from urllib.parse import urlencode

    candidates: list[bytes] = []
    primary_string_to_hash = ''
    sign_src = signature_payload if isinstance(signature_payload, dict) else payload
    if not isinstance(sign_src, dict):
        sign_src = {}
    else:
        # Shallow copy so callers cannot mutate HMAC input via the business payload.
        sign_src = dict(sign_src)

    # Never hash PayMe signature fields; also prepare a merchant-id-free variant.
    base_sources: list[dict[str, Any]] = [sign_src]
    stripped_merchant = {
        k: v
        for k, v in sign_src.items()
        if str(k) not in ('merchant_order_id', 'merchantOrderId')
    }
    if stripped_merchant.keys() != sign_src.keys():
        base_sources.append(stripped_merchant)

    for src in base_sources:
        items = _payme_signable_items(src)
        sorted_keys = sorted(items.keys())
        if not sorted_keys:
            continue
        # 1) PayMe IPN: sorted keys, join values only
        string_to_hash = ''.join(items[k] for k in sorted_keys)
        if not primary_string_to_hash:
            primary_string_to_hash = string_to_hash
        candidates.append(string_to_hash.encode('utf-8'))
        # 2) key+value concat (some PSP variants)
        candidates.append(''.join(f'{k}{items[k]}' for k in sorted_keys).encode('utf-8'))
        # 3) application/x-www-form-urlencoded in sorted key order
        candidates.append(urlencode([(k, items[k]) for k in sorted_keys]).encode('utf-8'))

        # Legacy: JSON without signature field (previous TradeTix behavior)
        cleaned = {k: v for k, v in src.items() if k not in _PAYME_SIGNATURE_BODY_KEYS}
        try:
            candidates.append(json.dumps(cleaned, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
            candidates.append(json.dumps(cleaned, separators=(',', ':'), sort_keys=True).encode('utf-8'))
        except (TypeError, ValueError):
            pass

    if raw_body:
        candidates.append(raw_body)

    seen: set[bytes] = set()
    out: list[bytes] = []
    for item in candidates:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out, primary_string_to_hash


def verify_payme_webhook_request(
    request,
    *,
    payload: dict[str, Any],
    order,
    raw_body: bytes | None = None,
    signature_payload: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """
    Bind a PayMe webhook payload to this exact TradeTix order.

    Standard Seller accounts do not receive ``merchant_password``, so PayMe IPN
    MD5 / HMAC signatures are not used as a security control. Authenticity is
    established later by a server-to-server ``get-transactions``
    call. This function only rejects payloads that do not match the stored order
    (merchant order id, PayMe sale/transaction id, amount, currency).

    Apple Pay / wallet callbacks often send PayMe-internal `order_id` and a TRAN id
    that differs from the `payme_sale_id` stored at init — verification accepts any
    matching sale/transaction reference and prefers explicit merchant_order_id fields.

    ``request``, ``raw_body``, and ``signature_payload`` are kept for call-site
    compatibility; they are not used for cryptographic verification.
    """
    _ = (request, raw_body, signature_payload)

    # Prefer explicit merchant order fields. Generic order_id is often PayMe-internal
    # (especially Apple Pay / Bit notify) and must not reject a sale-id match.
    explicit_merchant = _first_payload_value(payload, 'merchant_order_id', 'merchantOrderId')
    if explicit_merchant not in (None, ''):
        try:
            if int(explicit_merchant) != int(order.pk):
                return False, 'merchant_order_id_mismatch'
        except (TypeError, ValueError):
            return False, 'merchant_order_id_mismatch'
    else:
        generic_oid = _first_payload_value(payload, 'order_id', 'orderId')
        if generic_oid not in (None, ''):
            try:
                if int(generic_oid) == int(order.pk):
                    pass  # matches our order
                else:
                    logger.warning(
                        'PayMe webhook: ignoring non-matching generic order_id=%s for order_id=%s '
                        '(common on Apple Pay / wallet notifies)',
                        generic_oid,
                        getattr(order, 'pk', None),
                    )
            except (TypeError, ValueError):
                logger.warning(
                    'PayMe webhook: ignoring non-int generic order_id=%s for order_id=%s',
                    generic_oid,
                    getattr(order, 'pk', None),
                )

    stored_tid = (order.payme_transaction_id or '').strip()
    if not stored_tid:
        return False, 'missing_stored_transaction_id'

    payload_refs = _payload_transaction_refs(payload)
    if stored_tid not in payload_refs:
        return False, 'transaction_id_mismatch'

    currency = _extract_currency(payload)
    expected_currency = (order.currency or 'ILS').strip().upper()
    if currency and currency != expected_currency:
        return False, 'currency_mismatch'
    if not currency:
        logger.warning(
            'PayMe webhook: currency missing in payload; continuing with order currency=%s order_id=%s',
            expected_currency,
            getattr(order, 'pk', None),
        )

    expected_amount = _expected_order_total_agorot(order)
    amount_candidates = _payload_amount_candidates_agorot(payload)
    if amount_candidates:
        if expected_amount not in amount_candidates:
            return False, 'amount_mismatch'
    else:
        # Apple Pay / some wallet notifies omit price; sale id match is still required above.
        logger.warning(
            'PayMe webhook: no amount fields in payload; skipping amount check order_id=%s stored_tid_hash=%s',
            getattr(order, 'pk', None),
            _short_hash(stored_tid),
        )

    return True, 'ok'


def _order_ticket_id_set(order) -> set[int]:
    ids: set[int] = set()
    for tid in order.ticket_ids or []:
        try:
            ids.add(int(tid))
        except (TypeError, ValueError):
            continue
    if order.ticket_id:
        ids.add(int(order.ticket_id))
    if getattr(order, 'held_ticket_id', None):
        ids.add(int(order.held_ticket_id))
    return ids


def _tickets_claimed_by_other_paid_order(order) -> int | None:
    """Return conflicting paid/completed order id if any ticket is already owned elsewhere."""
    from users.models import Order

    wanted = _order_ticket_id_set(order)
    if not wanted:
        return None
    for other in (
        Order.objects.filter(status__in=('paid', 'completed'))
        .exclude(pk=order.pk)
        .only('id', 'ticket_ids', 'ticket_id', 'held_ticket_id')
        .iterator()
    ):
        if wanted & _order_ticket_id_set(other):
            return int(other.pk)
    return None


def lock_and_mark_tickets_sold(ticket_ids) -> list:
    """
    Row-lock ticket rows in pk order and mark them sold.

    Must run inside ``transaction.atomic()``. Locking in sorted pk order avoids
    deadlocks when two checkouts touch overlapping listings.
    """
    from users.models import Ticket

    ids: list[int] = []
    for tid in ticket_ids or []:
        try:
            ids.append(int(tid))
        except (TypeError, ValueError):
            continue
    ids = sorted(set(ids))
    if not ids:
        return []

    locked = list(Ticket.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    found = {t.pk for t in locked}
    missing = [i for i in ids if i not in found]
    if missing:
        raise Ticket.DoesNotExist(f'tickets missing for sale: {missing}')

    for t in locked:
        t.status = 'sold'
        t.available_quantity = 0
        t.reserved_at = None
        t.reserved_by = None
        t.reservation_email = None
        t.save(
            update_fields=[
                'status',
                'available_quantity',
                'reserved_at',
                'reserved_by',
                'reservation_email',
                'updated_at',
            ]
        )
    return locked


def _fulfill_paid_order_ticket_rows(order) -> None:
    """Ensure paid/completed orders leave fully purchased ticket rows unavailable."""
    from users.models import Ticket

    if order.held_ticket_id and order.held_quantity:
        t = Ticket.objects.select_for_update().get(pk=order.held_ticket_id)
        if (t.available_quantity or 0) <= 0:
            t.status = 'sold'
        t.reserved_at = None
        t.reserved_by = None
        t.reservation_email = None
        t.save(
            update_fields=[
                'status',
                'available_quantity',
                'reserved_at',
                'reserved_by',
                'reservation_email',
                'updated_at',
            ]
        )
        return

    ticket_ids = list(order.ticket_ids or [])
    if not ticket_ids and order.ticket_id:
        ticket_ids = [order.ticket_id]
    if ticket_ids:
        lock_and_mark_tickets_sold(ticket_ids)


def build_payme_webhook_idempotency_key(order, payload: dict[str, Any] | None = None) -> str:
    """Stable key for a PayMe success notify: order + sale/transaction id."""
    stored = str(getattr(order, 'payme_transaction_id', None) or '').strip()
    refs: list[str] = []
    payload = payload or {}
    for key in (
        'payme_sale_id',
        'sale_id',
        'payme_transaction_id',
        'transaction_id',
        'transactionId',
        'payme_sale_code',
    ):
        value = payload.get(key)
        if value not in (None, ''):
            refs.append(str(value).strip())
    ident = stored
    if stored and stored in refs:
        ident = stored
    elif refs:
        ident = refs[0]
    if not ident:
        ident = f'order-{getattr(order, "pk", "unknown")}'
    return f'payme:{int(order.pk)}:{ident}:success'


def payme_webhook_already_completed(idempotency_key: str) -> bool:
    from users.models import PayMeWebhookIdempotency

    return PayMeWebhookIdempotency.objects.filter(
        idempotency_key=idempotency_key,
        status=PayMeWebhookIdempotency.STATUS_COMPLETED,
    ).exists()


def _mark_payme_idempotency_completed(row) -> None:
    from users.models import PayMeWebhookIdempotency

    if row is None:
        return
    row.status = PayMeWebhookIdempotency.STATUS_COMPLETED
    row.completed_at = timezone.now()
    row.save(update_fields=['status', 'completed_at'])


def claim_payme_webhook_idempotency(*, key: str, order, sale_id: str = ''):
    """
    Insert-or-lock the unique webhook key.

    Returns ``('claimed', row)`` for the first worker, ``('duplicate', row)`` when
    fulfillment already finished, or ``('in_flight', row)`` while another worker
    still holds the claim.
    """
    from users.models import PayMeWebhookIdempotency

    try:
        with transaction.atomic():
            row = PayMeWebhookIdempotency.objects.create(
                idempotency_key=key,
                order=order,
                payme_sale_id=(sale_id or '')[:128],
                status=PayMeWebhookIdempotency.STATUS_PROCESSING,
            )
            return 'claimed', row
    except IntegrityError:
        pass

    with transaction.atomic():
        row = (
            PayMeWebhookIdempotency.objects.select_for_update()
            .filter(idempotency_key=key)
            .first()
        )
    if row is None:
        return 'missing', None
    if row.status == PayMeWebhookIdempotency.STATUS_COMPLETED:
        return 'duplicate', row
    return 'in_flight', row


def _retry_on_sqlite_lock(fn, *, attempts: int = 8, delay: float = 0.05):
    """SQLite serializes writers; brief retries keep concurrent IPN retries safe."""
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except OperationalError as exc:
            last = exc
            if 'locked' not in str(exc).lower():
                raise
            time.sleep(delay * (attempt + 1))
    raise last


def finalize_payme_webhook_once(
    order_id: int,
    *,
    idempotency_key: str,
    sale_id: str = '',
    source: str = 'payme_webhook',
) -> tuple[bool, str | None, str]:
    """
    Fulfill a PayMe success notify at most once for ``idempotency_key``.

    Concurrent retries share the unique key: the winner runs inventory + ledger;
    losers wait (or take the paid reconcile path) so tickets and balances move once.
    """
    from users.models import Order, PayMeWebhookIdempotency

    sale_id = (sale_id or '')[:128]

    def _run():
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            return False, 'order_missing', 'missing'

        claim, row = claim_payme_webhook_idempotency(
            key=idempotency_key,
            order=order,
            sale_id=sale_id,
        )

        if claim == 'duplicate':
            ok, err = finalize_pending_order_to_paid(order_id, source=f'{source}_replay')
            return ok, err, 'duplicate'

        if claim == 'in_flight':
            for _ in range(40):
                time.sleep(0.05)
                if row is None:
                    break
                row.refresh_from_db()
                if row.status == PayMeWebhookIdempotency.STATUS_COMPLETED:
                    ok, err = finalize_pending_order_to_paid(order_id, source=f'{source}_replay')
                    return ok, err, 'duplicate'
            ok, err = finalize_pending_order_to_paid(order_id, source=f'{source}_recover')
            if ok:
                fresh = PayMeWebhookIdempotency.objects.filter(idempotency_key=idempotency_key).first()
                _mark_payme_idempotency_completed(fresh or row)
            return ok, err, 'recovered'

        if claim != 'claimed' or row is None:
            return False, 'idempotency_claim_failed', claim

        ok, err = finalize_pending_order_to_paid(order_id, source=source)
        if ok:
            _mark_payme_idempotency_completed(row)
        return ok, err, 'claimed'

    return _retry_on_sqlite_lock(_run)


# Statuses the normal webhook/client path may finalize from.
_FINALIZE_DEFAULT_STATUSES = frozenset({'pending_payment'})
# Admin recovery only: abandoned cleanup may have cancelled a paid-in-PayMe order.
_FINALIZE_ADMIN_FORCE_STATUSES = frozenset(
    {
        'pending_payment',
        'cancelled',
        'canceled',  # defensive alias if ever stored
        'pending',
    }
)


def finalize_pending_order_to_paid(
    order_id: int,
    source: str = 'payme',
    *,
    force_from_admin: bool = False,
) -> tuple[bool, str | None]:
    """
    Run the same inventory + status transition as confirm_order_payment (without user session checks).
    Caller must verify webhook signature / PSP trust first.

    When force_from_admin=True (Django admin recovery only), also accepts cancelled/pending
    stuck orders, skips reservation-expiry checks, and re-claims released inventory so the
    buyer gets the same paid order + sold tickets + payout ledger as a successful webhook.
    """
    from users.models import Order, Ticket
    from users.views import (
        RESERVATION_TIMEOUT_MINUTES,
        _apply_order_pricing_fields,
        _finalize_group_sale_ticket_rows,
        _finalize_offers_after_sale,
        _verify_reservations_fresh,
        release_abandoned_carts,
    )
    from datetime import timedelta

    try:
        if not force_from_admin:
            release_abandoned_carts()
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=order_id).first()
            if not order:
                return False, 'order_missing'
            if order.status == 'paid':
                _fulfill_paid_order_ticket_rows(order)
                try:
                    from users.payout_ledger import ensure_seller_payout_for_order

                    ensure_seller_payout_for_order(order)
                except Exception as payout_exc:
                    logger.warning(
                        'finalize_pending_order_to_paid payout reconcile failed order_id=%s: %s',
                        order_id,
                        payout_exc,
                    )
                return True, None

            allowed = _FINALIZE_ADMIN_FORCE_STATUSES if force_from_admin else _FINALIZE_DEFAULT_STATUSES
            if order.status not in allowed:
                return False, 'order_not_pending'

            if force_from_admin:
                conflict = _tickets_claimed_by_other_paid_order(order)
                if conflict is not None:
                    logger.warning(
                        'finalize_pending_order_to_paid admin force blocked order_id=%s '
                        'tickets already on paid order_id=%s',
                        order_id,
                        conflict,
                    )
                    return False, f'ticket_already_sold_on_order_{conflict}'

            negotiated_offer = order.pending_offer
            ticket_ref = order.ticket

            if force_from_admin:
                # Cancelled / expired holds often released inventory back to active — reclaim.
                ticket_ids = list(order.ticket_ids or [])
                if not ticket_ids and order.ticket_id:
                    ticket_ids = [order.ticket_id]
                if order.held_ticket_id and order.held_ticket_id not in ticket_ids:
                    ticket_ids.append(order.held_ticket_id)
                if not ticket_ids:
                    return False, 'ticket_mismatch'
                _finalize_group_sale_ticket_rows(ticket_ids)
                ticket_ref = Ticket.objects.filter(pk=ticket_ids[0]).first() or ticket_ref
            elif order.held_ticket_id and order.held_quantity:
                t = Ticket.objects.select_for_update().get(pk=order.held_ticket_id)
                if timezone.now() - order.created_at > timedelta(minutes=RESERVATION_TIMEOUT_MINUTES + 5):
                    raise ValueError('checkout_expired')
                if (t.available_quantity or 0) <= 0:
                    t.status = 'sold'
                t.reserved_at = None
                t.reserved_by = None
                t.reservation_email = None
                t.save(
                    update_fields=[
                        'status',
                        'available_quantity',
                        'reserved_at',
                        'reserved_by',
                        'reservation_email',
                        'updated_at',
                    ]
                )
                ticket_ref = t
            else:
                tix = list(
                    Ticket.objects.select_for_update()
                    .filter(pk__in=(order.ticket_ids or []))
                    .order_by('pk')
                )
                if len(tix) != len(order.ticket_ids or []):
                    raise ValueError('ticket_mismatch')
                user_obj = order.user if order.user_id else None
                ge = (order.guest_email or '').strip()
                _verify_reservations_fresh(tix, user=user_obj, guest_email=ge)
                lock_and_mark_tickets_sold(order.ticket_ids)

            _finalize_offers_after_sale(
                ticket_ids=list(order.ticket_ids or []),
                winning_offer=negotiated_offer,
            )
            claimed = Order.objects.filter(pk=order.pk, status__in=tuple(allowed)).update(
                status='paid',
                payment_confirm_token=None,
                updated_at=timezone.now(),
            )
            if claimed != 1:
                order.refresh_from_db()
                if order.status == 'paid':
                    _fulfill_paid_order_ticket_rows(order)
                    try:
                        from users.payout_ledger import ensure_seller_payout_for_order

                        ensure_seller_payout_for_order(order)
                    except Exception as payout_exc:
                        logger.warning(
                            'finalize_pending_order_to_paid CAS loser payout reconcile failed order_id=%s: %s',
                            order_id,
                            payout_exc,
                        )
                    return True, None
                return False, 'order_not_pending'

            order.refresh_from_db()
            order.status = 'paid'
            order.payment_confirm_token = None
            update_fields = ['status', 'payment_confirm_token', 'updated_at']
            if force_from_admin:
                # Clear stale hold pointers left from abandoned-checkout cancel.
                order.held_ticket = None
                order.held_quantity = 0
                update_fields.extend(['held_ticket', 'held_quantity'])
                if not (order.payme_status or '').strip() or order.payme_status in (
                    'initialized',
                    'pending',
                    'unknown',
                ):
                    order.payme_status = 'admin_force_paid'
                    update_fields.append('payme_status')
            order.save(update_fields=list(dict.fromkeys(update_fields)))
            _apply_order_pricing_fields(order, negotiated_offer, ticket_ref, order.quantity)
            from users.coupons import finalize_coupon_redemption

            finalize_coupon_redemption(order)

            from users.payout_ledger import ensure_seller_payout_for_order

            ensure_seller_payout_for_order(order)
            logger.warning(
                'finalize_pending_order_to_paid ok order_id=%s source=%s force_from_admin=%s',
                order_id,
                source,
                force_from_admin,
            )
    except ValueError as e:
        logger.warning('finalize_pending_order_to_paid order_id=%s: %s', order_id, e)
        return False, str(e)
    except Exception:
        logger.exception('finalize_pending_order_to_paid order_id=%s', order_id)
        return False, 'internal_error'

    try:
        from users.utils.emails import queue_paid_order_receipt_email

        queue_paid_order_receipt_email(order_id, source=source)
    except Exception:
        logger.error(
            'payme finalize: receipt email dispatch crashed order_id=%s source=%s',
            order_id,
            source,
            exc_info=True,
        )

    try:
        from users.notifications import notify_seller_ticket_sold_escrow

        ord_row = Order.objects.filter(pk=order_id).first()
        if ord_row:
            notify_seller_ticket_sold_escrow(ord_row)
    except Exception:
        logger.error(
            'payme finalize: seller notification failed order_id=%s source=%s',
            order_id,
            source,
            exc_info=True,
        )

    logger.info('Order %s finalized to paid via %s', order_id, source)
    return True, None
