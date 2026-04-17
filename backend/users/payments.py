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
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

QUANT = Decimal('0.01')


def _money_to_agorot(amount: Decimal | str | float | int) -> int:
    d = Decimal(str(amount)).quantize(QUANT, rounding=ROUND_HALF_UP)
    return int(d * 100)


def log_payme(stage: str, *, order_id: int | None = None, payload: Any = None, response: Any = None, exc: BaseException | None = None) -> None:
    """Structured Payme logging (never log raw API secrets)."""
    extra = {'payme_stage': stage, 'order_id': order_id}
    if exc is not None:
        logger.exception('Payme [%s] order_id=%s failed: %s', stage, order_id, exc, extra=extra)
        return
    safe_payload = payload
    if isinstance(payload, dict):
        safe_payload = {k: ('***' if 'key' in k.lower() or 'secret' in k.lower() or 'token' in k.lower() else v) for k, v in payload.items()}
    logger.info('Payme [%s] order_id=%s payload=%s response=%s', stage, order_id, safe_payload, response, extra=extra)


def get_payme_config() -> dict[str, Any]:
    return {
        'merchant_id': getattr(settings, 'PAYME_MERCHANT_ID', '') or '',
        'api_key': getattr(settings, 'PAYME_API_KEY', '') or '',
        'api_secret': getattr(settings, 'PAYME_API_SECRET', '') or '',
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


def normalize_payme_webhook_status(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (transaction_id, normalized_status) where normalized is success|authorized|failed|pending."""
    tid = None
    for k in ('transaction_id', 'transactionId', 'payme_transaction_id', 'sale_id', 'id'):
        v = payload.get(k)
        if v is not None and str(v).strip():
            tid = str(v).strip()
            break

    raw = (
        payload.get('status')
        or payload.get('payment_status')
        or payload.get('state')
        or payload.get('transaction_status')
        or ''
    )
    s = str(raw).strip().lower()

    success_tokens = ('success', 'succeeded', 'completed', 'paid', 'captured', 'ok', 'approved')
    auth_tokens = ('authorized', 'authorised', 'auth', 'pre_auth', 'preauth', 'hold')
    fail_tokens = ('fail', 'failed', 'declined', 'error', 'cancel', 'void', 'rejected')

    if any(t in s for t in fail_tokens):
        return tid, 'failed'
    if any(t in s for t in success_tokens):
        return tid, 'success'
    if any(t in s for t in auth_tokens):
        return tid, 'authorized'
    return tid, 'pending' if s else None


def verify_payme_webhook_request(request) -> bool:
    secret = (get_payme_config()['webhook_secret'] or '').strip()
    if not secret:
        return True
    got = (request.headers.get('X-Payme-Signature') or request.headers.get('X-Webhook-Signature') or '').strip()
    if not got:
        return False
    import hmac
    import hashlib

    body = request.body or b''
    expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    from secrets import compare_digest

    return compare_digest(got, expected) or compare_digest(got, f'sha256={expected}')


def finalize_pending_order_to_paid(order_id: int, source: str = 'payme') -> tuple[bool, str | None]:
    """
    Run the same inventory + status transition as confirm_order_payment (without user session checks).
    Caller must verify webhook signature / PSP trust first.
    """
    from django.db import close_old_connections

    from users.models import Order, Ticket
    from users.views import (
        RESERVATION_TIMEOUT_MINUTES,
        _apply_order_pricing_fields,
        _finalize_group_sale_ticket_rows,
        _reject_pending_offers_for_ticket_ids,
        _verify_reservations_fresh,
        release_abandoned_carts,
    )
    from datetime import timedelta

    try:
        with transaction.atomic():
            release_abandoned_carts()
            order = Order.objects.select_for_update().filter(pk=order_id).first()
            if not order:
                return False, 'order_missing'
            if order.status == 'paid':
                return True, None
            if order.status != 'pending_payment':
                return False, 'order_not_pending'

            negotiated_offer = order.pending_offer
            ticket_ref = order.ticket

            if order.held_ticket_id and order.held_quantity:
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

            _reject_pending_offers_for_ticket_ids(list(order.ticket_ids or []))
            order.status = 'paid'
            order.payment_confirm_token = None
            order.save(update_fields=['status', 'payment_confirm_token', 'updated_at'])
            _apply_order_pricing_fields(order, negotiated_offer, ticket_ref, order.quantity)
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
