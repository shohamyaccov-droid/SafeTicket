"""
Payme (Payme.io) marketplace / platform integration — test/sandbox first.

Docs vary by merchant onboarding; we POST JSON to PAYME_GENERATE_SALE_URL (default test host)
and merge PAYME_EXTRA_BODY_JSON so ops can align with Payme support without redeploying.

Escrow: prefer authorize / non-capture flow (see PAYME_EXTRA_BODY_JSON defaults in settings).
"""
from __future__ import annotations

import json
import logging
import threading
import hashlib
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
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


def get_payme_config() -> dict[str, Any]:
    seller_id = getattr(settings, 'PAYME_SELLER_ID', '') or getattr(settings, 'PAYME_MERCHANT_ID', '') or ''
    return {
        'seller_id': seller_id,
        'merchant_id': getattr(settings, 'PAYME_MERCHANT_ID', '') or seller_id,
        'api_key': getattr(settings, 'PAYME_API_KEY', '') or '',
        'api_secret': getattr(settings, 'PAYME_API_SECRET', '') or '',
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
            key_norm = str(key).lower()
            if key_norm not in all_keys:
                continue
            try:
                dec = Decimal(str(value)).quantize(QUANT, rounding=ROUND_HALF_UP)
            except Exception:
                continue
            if key_norm in minor_keys:
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

    raw = _first_payload_value(
        payload,
        'status',
        'payment_status',
        'state',
        'transaction_status',
        'sale_status',
        'payme_sale_status',
        'payme_status',
        'notify_type',
        'notifyType',
        'event',
        'event_type',
        'status_code',
        'payme_status_code',
    )
    s = str(raw or '').strip().lower().replace(' ', '_').replace('-', '_')

    if s in ('0', '00'):
        return tid, 'success'
    if s in ('1', '01'):
        return tid, 'pending'

    success_tokens = (
        'success',
        'succeeded',
        'completed',
        'complete',
        'paid',
        'captured',
        'capture',
        'ok',
        'approved',
        'salecomplete',
        'chargesucceeded',
        'paymentcompleted',
    )
    auth_tokens = ('authorized', 'authorised', 'auth', 'preauth', 'hold')
    fail_tokens = ('fail', 'failed', 'declined', 'error', 'cancel', 'cancelled', 'void', 'rejected')

    # Compact form catches sale_complete / charge_succeeded without false positives.
    compact = s.replace('_', '')
    if _status_token_match(s, fail_tokens) or compact in {t.replace('_', '') for t in fail_tokens}:
        return tid, 'failed'
    if _status_token_match(s, success_tokens) or compact in {t.replace('_', '') for t in success_tokens}:
        return tid, 'success'
    if _status_token_match(s, auth_tokens) or compact in {t.replace('_', '') for t in auth_tokens}:
        return tid, 'authorized'
    return tid, 'pending' if s else None


def _payme_webhook_hmac_bypassed() -> bool:
    """Skip HMAC only in DEBUG dev/sandbox. Production (DEBUG=False) never bypasses."""
    if not getattr(settings, 'DEBUG', False):
        return False
    secret = (get_payme_config()['webhook_secret'] or '').strip()
    is_sandbox = bool(getattr(settings, 'PAYME_IS_SANDBOX', False))
    return is_sandbox or not secret


_PAYME_SIGNATURE_BODY_KEYS = ('payme_signature', 'paymeSignature', 'signature')


def _extract_payme_webhook_signature(request, payload: dict[str, Any]) -> str:
    """
    PayMe may send the HMAC in headers (X-Payme-Signature) or inside the POST body
    as payme_signature (production IPN / form callbacks). Prefer header, then body.
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

    # Last resort: DRF / Django parsed body (same keys)
    try:
        data = getattr(request, 'data', None)
        if data is not None:
            for key in _PAYME_SIGNATURE_BODY_KEYS:
                value = data.get(key) if hasattr(data, 'get') else None
                if value not in (None, ''):
                    return str(value).strip()
    except Exception:
        pass
    try:
        post = getattr(request, 'POST', None)
        if post:
            for key in _PAYME_SIGNATURE_BODY_KEYS:
                value = post.get(key)
                if value not in (None, ''):
                    return str(value).strip()
    except Exception:
        pass
    return ''


def _payme_hmac_body_candidates(raw_body: bytes, payload: dict[str, Any]) -> list[bytes]:
    """
    Bodies PayMe may have signed.

    Header signatures: HMAC over the raw request bytes.
    Body-embedded payme_signature: HMAC over the payload *without* the signature field
    (JSON compact or form-urlencoded), since including the sig would be circular.
    """
    candidates: list[bytes] = []
    if raw_body:
        candidates.append(raw_body)

    if not isinstance(payload, dict):
        return candidates

    has_body_sig = any(payload.get(k) not in (None, '') for k in _PAYME_SIGNATURE_BODY_KEYS)
    if not has_body_sig:
        return candidates

    cleaned = {k: v for k, v in payload.items() if k not in _PAYME_SIGNATURE_BODY_KEYS}
    try:
        candidates.append(json.dumps(cleaned, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
        candidates.append(json.dumps(cleaned, separators=(',', ':')).encode('utf-8'))
    except (TypeError, ValueError):
        pass
    try:
        from urllib.parse import urlencode

        flat = {str(k): '' if v is None else str(v) for k, v in cleaned.items()}
        candidates.append(urlencode(flat).encode('utf-8'))
    except Exception:
        pass

    # Preserve order, drop empties/dupes
    seen: set[bytes] = set()
    out: list[bytes] = []
    for item in candidates:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def verify_payme_webhook_request(
    request,
    *,
    payload: dict[str, Any],
    order,
    raw_body: bytes | None = None,
) -> tuple[bool, str]:
    """
    Validate that a PayMe webhook is both authentic and for this exact order.

    Finalization is irreversible from a marketplace perspective (inventory is sold
    and PDFs are released), so every success webhook must prove:
    signature (production only), merchant order id, PayMe transaction id, amount, and currency.

    HMAC verification is skipped when PAYME_IS_SANDBOX is True or PAYME_WEBHOOK_SECRET is unset.

    Apple Pay / wallet callbacks often send PayMe-internal `order_id` and a TRAN id that
    differs from the `payme_sale_id` stored at init — verification accepts any matching
    sale/transaction reference and prefers explicit merchant_order_id fields.
    """
    if _payme_webhook_hmac_bypassed():
        is_sandbox = bool(getattr(settings, 'PAYME_IS_SANDBOX', False))
        secret = (get_payme_config()['webhook_secret'] or '').strip()
        if is_sandbox:
            logger.warning(
                'PayMe webhook: bypassing HMAC signature verification (sandbox/preprod mode) order_id=%s',
                getattr(order, 'pk', None),
            )
        else:
            logger.warning(
                'PayMe webhook: bypassing HMAC signature verification (PAYME_WEBHOOK_SECRET not set) order_id=%s',
                getattr(order, 'pk', None),
            )
    else:
        secret = (get_payme_config()['webhook_secret'] or '').strip()
        got = _extract_payme_webhook_signature(request, payload or {})
        if not got:
            return False, 'missing_signature_header'
        import hmac

        try:
            body = raw_body if raw_body is not None else (request.body or b'')
        except Exception as exc:
            logger.warning(
                'PayMe webhook: unable to read request body for HMAC verification order_id=%s error=%s',
                getattr(order, 'pk', None),
                exc,
            )
            return False, 'body_unavailable_for_signature'
        from secrets import compare_digest

        matched = False
        for candidate in _payme_hmac_body_candidates(body, payload or {}):
            expected = hmac.new(secret.encode('utf-8'), candidate, hashlib.sha256).hexdigest()
            if compare_digest(got, expected) or compare_digest(got, f'sha256={expected}'):
                matched = True
                break
        if not matched:
            return False, 'bad_signature'

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
        for tid in ticket_ids:
            t = Ticket.objects.select_for_update().get(pk=tid)
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
        return


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
    from django.db import close_old_connections

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
        with transaction.atomic():
            if not force_from_admin:
                release_abandoned_carts()
            order = Order.objects.select_for_update().filter(pk=order_id).first()
            if not order:
                return False, 'order_missing'
            if order.status == 'paid':
                _fulfill_paid_order_ticket_rows(order)
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
                    .order_by('id')
                )
                if len(tix) != len(order.ticket_ids or []):
                    raise ValueError('ticket_mismatch')
                user_obj = order.user if order.user_id else None
                ge = (order.guest_email or '').strip()
                _verify_reservations_fresh(tix, user=user_obj, guest_email=ge)
                _finalize_group_sale_ticket_rows(order.ticket_ids)

            _finalize_offers_after_sale(
                ticket_ids=list(order.ticket_ids or []),
                winning_offer=negotiated_offer,
            )
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

    recipient = ''
    try:
        ord_row = Order.objects.filter(pk=order_id).first()
        if ord_row:
            recipient = (ord_row.user.email if ord_row.user_id else ord_row.guest_email) or ''
    except Exception:
        recipient = ''

    order_pk = order_id
    recipient_copy = recipient

    def _send_order_receipt_background():
        close_old_connections()
        try:
            from users.models import Order as O2
            from users.utils.emails import send_receipt_with_pdf

            ord_row = O2.objects.filter(pk=order_pk).first()
            if ord_row and recipient_copy:
                send_receipt_with_pdf(recipient_copy, ord_row)
        except Exception:
            logger.exception('payme finalize: receipt email failed')
        finally:
            close_old_connections()

    if recipient_copy:
        transaction.on_commit(lambda: threading.Thread(target=_send_order_receipt_background, daemon=True).start())

    try:
        from users.notifications import notify_seller_ticket_sold_escrow

        ord_row = Order.objects.filter(pk=order_pk).first()
        if ord_row:
            notify_seller_ticket_sold_escrow(ord_row)
    except Exception:
        logger.exception('payme finalize: seller notification failed')

    logger.info('Order %s finalized to paid via %s', order_id, source)
    return True, None
