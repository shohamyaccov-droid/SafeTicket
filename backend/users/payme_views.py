"""
Payme HTTP handlers: hosted-checkout init + PSP webhooks.
Payme webhook lives at /api/payments/webhook/payme/ (see safeticket.urls).
"""
from __future__ import annotations

import logging
import time
from typing import Any

from django.conf import settings
from django.db.utils import OperationalError
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from services.payme_service import (
    PayMeError,
    PayMeSettings,
    confirm_payme_sale_status,
    fallback_buyer_name_from_email,
    generate_payme_sale_for_order,
    normalize_payme_buyer_phone,
    resolve_buyer_details_for_order,
)

from .models import Order, PayMeWebhookLog
from .payments import (
    build_payme_webhook_idempotency_key,
    extract_payme_raw_sign_fields,
    finalize_payme_webhook_once,
    log_payme,
    log_payme_dev,
    normalize_payme_webhook_status,
    parse_payme_raw_body_fields,
    payme_webhook_already_completed,
    verify_payme_webhook_request,
)
from .shabbat import shabbat_forbidden_response

logger = logging.getLogger(__name__)

_PAYME_WEBHOOK_PARSERS = (FormParser, MultiPartParser, JSONParser)


def _headers_to_jsonable(request) -> dict[str, str]:
    try:
        return {str(k): str(v) for k, v in request.headers.items()}
    except Exception:
        return {}


def _capture_payme_webhook_log(request) -> PayMeWebhookLog | None:
    """
    Persist exact wire bytes + headers before any business parsing / HMAC.
    Must be the first side-effect in payme_webhook.
    """
    try:
        raw_bytes = getattr(request, 'body', None) or b''
        if isinstance(raw_bytes, memoryview):
            raw_bytes = raw_bytes.tobytes()
        raw_text = raw_bytes.decode('utf-8', errors='replace') if isinstance(raw_bytes, (bytes, bytearray)) else str(raw_bytes)
        return PayMeWebhookLog.objects.create(
            raw_body=raw_text,
            headers=_headers_to_jsonable(request),
            is_valid=False,
            error_message='unprocessed',
        )
    except Exception:
        logger.exception('PayMe webhook: failed to persist PayMeWebhookLog (continuing without log)')
        return None


def _finalize_payme_webhook_log(
    webhook_log: PayMeWebhookLog | None,
    *,
    is_valid: bool,
    error_message: str | None,
) -> None:
    if webhook_log is None:
        return
    try:
        webhook_log.is_valid = bool(is_valid)
        webhook_log.error_message = error_message
        webhook_log.save(update_fields=['is_valid', 'error_message'])
    except Exception:
        logger.exception('PayMe webhook: failed to update PayMeWebhookLog id=%s', getattr(webhook_log, 'pk', None))


def _coerce_payme_payload_dict(data: Any) -> dict[str, Any]:
    """Normalize DRF request.data / Django POST into a flat string-keyed dict."""
    if data is None:
        return {}
    raw: dict[str, Any]
    if hasattr(data, 'dict'):
        try:
            raw = data.dict()
        except Exception:
            raw = {str(k): data.get(k) for k in data.keys()} if hasattr(data, 'keys') else {}
    elif isinstance(data, dict):
        raw = dict(data)
    elif hasattr(data, 'keys'):
        raw = {str(k): data.get(k) for k in data.keys()}
    else:
        return {}

    # Bit / wallet notifies include empty card fields in the HMAC string. Keep keys
    # with empty-string values so signature verification still matches PayMe.
    out: dict[str, Any] = {}
    for key, value in raw.items():
        key_s = str(key)
        if value in (None, 'null', 'None'):
            out[key_s] = ''
        else:
            out[key_s] = value
    return out


def _parse_payme_webhook_payload(request, *, raw_body: bytes | None = None) -> dict[str, Any]:
    """
    Business payload from the raw body only (parse_qsl / JSON), not request.POST.
    Falls back to DRF data only when the body is empty.
    """
    try:
        body = raw_body if raw_body is not None else (getattr(request, 'body', None) or b'')
        fields = parse_payme_raw_body_fields(body)
        if fields:
            return dict(fields)
        if hasattr(request, 'data') and request.data:
            return _coerce_payme_payload_dict(request.data)
    except Exception as exc:
        logger.warning('payme_webhook payload parse failed: %s', exc)
        return {}
    return {}


def _payload_sources(payload: dict[str, Any]):
    for source in (
        payload,
        payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {},
        payload.get('data') if isinstance(payload.get('data'), dict) else {},
        payload.get('result') if isinstance(payload.get('result'), dict) else {},
        payload.get('payment') if isinstance(payload.get('payment'), dict) else {},
        payload.get('transaction') if isinstance(payload.get('transaction'), dict) else {},
        payload.get('sale') if isinstance(payload.get('sale'), dict) else {},
    ):
        yield source


def _extract_payme_value(payload: dict[str, Any], keys: tuple[str, ...]) -> tuple[Any, str | None]:
    for source in _payload_sources(payload):
        for key in keys:
            value = source.get(key)
            if value not in (None, ''):
                return value, key
    return None, None


def _extract_payme_order_reference(payload: dict[str, Any]) -> tuple[Any, str | None]:
    """Legacy merchant order fields, if PayMe sends them."""
    return _extract_payme_value(payload, ('merchant_order_id', 'merchantOrderId', 'order_id', 'orderId'))


def _extract_explicit_merchant_order_id(payload: dict[str, Any]) -> tuple[Any, str | None]:
    """Prefer TradeTix merchant fields; avoid PayMe-internal order_id when possible."""
    return _extract_payme_value(payload, ('merchant_order_id', 'merchantOrderId'))


def _extract_payme_transaction_reference(payload: dict[str, Any]) -> tuple[Any, str | None]:
    """PayMe sale/transaction id stored on Order.payme_transaction_id during init."""
    return _extract_payme_value(
        payload,
        ('payme_sale_code', 'payme_sale_id', 'sale_id', 'payme_transaction_id', 'transaction_id', 'transactionId'),
    )


def _extract_payme_transaction_references(payload: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """Collect all PayMe sale/transaction identifiers sent in the callback."""
    keys = ('payme_sale_code', 'payme_sale_id', 'sale_id', 'payme_transaction_id', 'transaction_id', 'transactionId')
    refs: list[str] = []
    sources: dict[str, str] = {}
    for source in _payload_sources(payload):
        for key in keys:
            value = source.get(key)
            if value in (None, ''):
                continue
            ref = str(value).strip()
            if not ref or ref in sources:
                continue
            refs.append(ref)
            sources[ref] = key
    return refs, sources


def _resolve_order_from_payme_webhook(
    payload: dict[str, Any],
    *,
    possible_payme_refs: list[str],
    oid_raw: Any,
) -> tuple[Order | None, str | None]:
    """
    Resolve Order for a PayMe callback.

    Primary: match any sale/transaction ref to Order.payme_transaction_id (set at init).
    Fallback: merchant_order_id / order_id — Apple Pay often posts a new TRAN id without
    the original payme_sale_id, so sale-id lookup alone would 404 a paid wallet charge.
    """
    if possible_payme_refs:
        order = Order.objects.filter(payme_transaction_id__in=possible_payme_refs).first()
        if order:
            return order, 'payme_transaction_id'

    # Explicit TradeTix merchant id first, then generic order_id (wallet notifies).
    candidates: list[tuple[Any, str]] = []
    explicit_raw, explicit_src = _extract_explicit_merchant_order_id(payload)
    if explicit_raw not in (None, ''):
        candidates.append((explicit_raw, explicit_src or 'merchant_order_id'))
    if oid_raw not in (None, '') and (explicit_raw in (None, '') or str(oid_raw) != str(explicit_raw)):
        candidates.append((oid_raw, 'order_id_fallback'))

    for raw, source in candidates:
        try:
            oid = int(raw)
        except (TypeError, ValueError):
            continue
        order = Order.objects.filter(pk=oid, status__in=('pending_payment', 'paid')).first()
        if order:
            logger.warning(
                'PayMe webhook resolved order_id=%s via %s (sale refs did not match stored payme_transaction_id)',
                oid,
                source,
            )
            return order, source
    return None, None


def _canonicalize_webhook_payload_for_order(payload: dict[str, Any], order: Order) -> dict[str, Any]:
    """
    Align Apple Pay / wallet payloads with verification expectations.

    - Fill merchant_order_id with Order.pk only when PayMe omitted our merchant field
      (wallet notifies often send a PayMe-internal order_id instead). Never overwrite an
      explicit merchant_order_id — verify must still reject mismatches.
    - If the notify has no sale/transaction refs at all, inject the init-time sale id.
      Never inject over a conflicting TRAN — that would let a forged merchant_order_id
      + wrong transaction_id finalize an order.
    """
    out = dict(payload)
    if out.get('merchant_order_id') in (None, '') and out.get('merchantOrderId') in (None, ''):
        out['merchant_order_id'] = str(order.pk)
        logger.warning(
            'PayMe webhook filled merchant_order_id=%s after order lookup (PayMe omitted merchant field)',
            order.pk,
        )
    stored = str(order.payme_transaction_id or '').strip()
    if stored:
        refs, _ = _extract_payme_transaction_references(out)
        if not refs:
            out['payme_sale_id'] = stored
            out['transaction_id'] = stored
            logger.warning(
                'PayMe webhook injected stored payme_sale_id for order_id=%s (payload had no sale/transaction refs)',
                order.pk,
            )
        elif stored not in refs:
            logger.warning(
                'PayMe webhook payload refs=%s do not include stored payme_sale_id for order_id=%s '
                '(will fail verify unless a matching ref is present)',
                refs,
                order.pk,
            )
    return out


def _payme_ids_for_api_confirm(payload: dict[str, Any], order: Order) -> tuple[str | None, str | None]:
    """Extract sale_payme_id / payme_transaction_id from the webhook for live lookup."""
    sale = str(
        payload.get('payme_sale_id')
        or payload.get('sale_id')
        or payload.get('saleId')
        or payload.get('sale_payme_id')
        or ''
    ).strip()
    txn = str(
        payload.get('payme_transaction_id')
        or payload.get('transaction_id')
        or payload.get('transactionId')
        or ''
    ).strip()
    _ = order
    return (sale or None, txn or None)


def _log_payme_webhook_rejection(reason: str, *, order_id: int | None = None, payload: dict[str, Any] | None = None):
    logger.warning('PayMe webhook rejection reason: %s order_id=%s payload=%s', reason, order_id, payload)
    log_payme('webhook_rejected', order_id=order_id, payload={'reason': reason, 'payload': payload or {}})


@csrf_exempt
@api_view(['POST'])
@parser_classes(_PAYME_WEBHOOK_PARSERS)
@permission_classes([AllowAny])
def payme_webhook(request):
    """
    Payme → TradeTix status updates. Configure Payme dashboard to POST here.

    Handles card and Apple Pay / wallet notifies. Apple Pay often differs by:
    PayMe-internal order_id, nested sale.status, alternate TRAN vs init payme_sale_id,
    and sometimes omitted amount fields.

    Every notify is persisted to PayMeWebhookLog (raw body + headers) before parsing
    so unpaid / fake callbacks can be replayed offline. Fulfillment is gated on a
    direct PayMe get-sales / get-transactions lookup — not the webhook body.
    """
    # Absolute first side-effect: capture exact wire bytes before any business logic.
    webhook_log = _capture_payme_webhook_log(request)
    outcome: dict[str, Any] = {'is_valid': False, 'error_message': 'unprocessed'}

    payload: dict[str, Any] | None = None
    order_id: int | None = None
    try:
        try:
            raw_body = getattr(request, 'body', None) or b''
            if isinstance(raw_body, memoryview):
                raw_body = raw_body.tobytes()
        except Exception as exc:
            logger.warning('PayMe webhook body read error: %s', exc)
            outcome['error_message'] = 'payload_parse_error'
            _log_payme_webhook_rejection('payload_parse_error', payload={'error': str(exc)})
            return Response({'error': 'empty payload', 'reason': 'payload_parse_error'}, status=status.HTTP_400_BAD_REQUEST)

        incoming_for_log = parse_payme_raw_body_fields(raw_body)

        logger.info(
            'PayMe webhook incoming content_type=%s remote_addr=%s log_id=%s',
            request.content_type,
            request.META.get('REMOTE_ADDR'),
            getattr(webhook_log, 'pk', None),
        )
        log_payme(
            'webhook_incoming',
            payload={
                'content_type': request.content_type,
                'webhook_log_id': getattr(webhook_log, 'pk', None),
                'raw': incoming_for_log,
            },
        )

        payload = _parse_payme_webhook_payload(request, raw_body=raw_body)
        if not payload:
            outcome['error_message'] = 'empty_payload'
            _log_payme_webhook_rejection('empty_payload', payload={'content_type': request.content_type})
            return Response({'error': 'empty payload', 'reason': 'empty_payload'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(payload, dict):
            reason = f'invalid_payload_type:{type(payload).__name__}'
            outcome['error_message'] = reason
            _log_payme_webhook_rejection(reason)
            return Response({'error': 'expected object', 'reason': reason}, status=status.HTTP_400_BAD_REQUEST)

        # Always capture a sanitized snapshot of the exact callback for support/debug.
        try:
            log_payme('webhook_full_payload', payload=payload)
            log_payme_dev('webhook_full_payload', payload=payload)
        except Exception as log_exc:
            logger.warning('PayMe webhook payload logging failed: %s', log_exc)

        payme_ref_raw, payme_ref_source = _extract_payme_transaction_reference(payload)
        possible_payme_refs, payme_ref_sources = _extract_payme_transaction_references(payload)
        oid_raw, oid_source = _extract_payme_order_reference(payload)
        logger.warning(
            'PayMe webhook extracted payme reference=%s source=%s possible_payme_refs=%s '
            'merchant_order_reference=%s merchant_source=%s payload_keys=%s',
            payme_ref_raw,
            payme_ref_source,
            possible_payme_refs,
            oid_raw,
            oid_source,
            list(payload.keys()),
        )

        log_payme(
            'webhook_incoming',
            payload={
                'keys': list(payload.keys()),
                'merchant_order_id': oid_raw,
                'merchant_order_id_source': oid_source,
                'payme_reference': payme_ref_raw,
                'payme_reference_source': payme_ref_source,
                'possible_payme_references': possible_payme_refs,
                'status': payload.get('status') or payload.get('payment_status'),
                'payment_method': payload.get('payment_method')
                or payload.get('paymentMethod')
                or payload.get('payme_transaction_card_brand'),
            },
        )
        log_payme_dev(
            'webhook_raw_payload',
            order_id=None,
            content_type=request.content_type,
            merchant_order_id=oid_raw,
            merchant_order_id_source=oid_source,
            payme_reference=payme_ref_raw,
            payme_reference_source=payme_ref_source,
            possible_payme_references=possible_payme_refs,
            payload=payload,
        )

        if not possible_payme_refs and oid_raw in (None, ''):
            outcome['error_message'] = 'payme_transaction_reference_required'
            _log_payme_webhook_rejection('payme_transaction_reference_required', payload=payload)
            return Response(
                {'error': 'payme transaction reference required', 'reason': 'payme_transaction_reference_required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.warning(
            'PayMe webhook looking up Order by payme_transaction_id__in=%s sources=%s merchant_order=%s',
            possible_payme_refs,
            payme_ref_sources,
            oid_raw,
        )
        order, lookup_via = _resolve_order_from_payme_webhook(
            payload,
            possible_payme_refs=possible_payme_refs,
            oid_raw=oid_raw,
        )
        if not order:
            outcome['error_message'] = 'order_not_found_for_payme_transaction_id'
            _log_payme_webhook_rejection(
                'order_not_found_for_payme_transaction_id',
                payload={
                    'possible_payme_transaction_ids': possible_payme_refs,
                    'payme_reference_sources': payme_ref_sources,
                    'merchant_order_id': oid_raw,
                    'merchant_order_id_source': oid_source,
                },
            )
            return Response(
                {'error': 'order not found', 'reason': 'order_not_found_for_payme_transaction_id'},
                status=status.HTTP_404_NOT_FOUND,
            )

        order_id = int(order.pk)
        payme_ref = str(order.payme_transaction_id or '').strip()
        payme_ref_source = payme_ref_sources.get(payme_ref) or payme_ref_source or lookup_via

        # HMAC must use the original PayMe fields from raw body only (parse_qsl).
        raw_sign_fields = extract_payme_raw_sign_fields(request, raw_body=raw_body)
        signature_payload = raw_sign_fields if raw_sign_fields else dict(payload)

        try:
            payload = _canonicalize_webhook_payload_for_order(payload, order)
        except Exception as canon_exc:
            logger.exception(
                'PayMe webhook canonicalize failed order_id=%s: %s',
                order_id,
                canon_exc,
            )
            outcome['error_message'] = 'canonicalize_failed'
            _log_payme_webhook_rejection(
                'canonicalize_failed',
                order_id=order_id,
                payload={'error': str(canon_exc), 'raw_keys': list(signature_payload.keys())},
            )
            return Response(
                {'error': 'webhook failed', 'reason': 'canonicalize_failed'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tid, norm = normalize_payme_webhook_status(payload)
            verified, verify_reason = verify_payme_webhook_request(
                request,
                payload=payload,
                order=order,
                raw_body=raw_body,
                signature_payload=signature_payload,
            )
        except Exception as verify_exc:
            logger.exception(
                'PayMe webhook verify/normalize crashed order_id=%s: %s payload=%s',
                order_id,
                verify_exc,
                payload,
            )
            outcome['error_message'] = 'verify_exception'
            _log_payme_webhook_rejection(
                'verify_exception',
                order_id=order_id,
                payload={'error': str(verify_exc), 'payload': payload},
            )
            return Response(
                {'error': 'webhook failed', 'reason': 'verify_exception'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not verified:
            outcome['error_message'] = verify_reason or 'order_binding_failed'
            _log_payme_webhook_rejection(
                verify_reason,
                order_id=order_id,
                payload={
                    'lookup_via': lookup_via,
                    'merchant_order_id': oid_raw,
                    'merchant_order_id_source': oid_source,
                    'payme_reference': payme_ref,
                    'payme_reference_source': payme_ref_source,
                    'possible_payme_references': possible_payme_refs,
                    'transaction_id': tid,
                    'normalized_status': norm,
                    'stored_transaction_id': order.payme_transaction_id,
                    'order_currency': order.currency,
                    'order_total_paid_by_buyer': str(order.total_paid_by_buyer),
                    'order_total_amount': str(order.total_amount),
                    'signature_payload_keys': list(signature_payload.keys()),
                    'canonical_payload_keys': list(payload.keys()),
                    'webhook_log_id': getattr(webhook_log, 'pk', None),
                },
            )
            return Response({'error': 'invalid webhook', 'reason': verify_reason}, status=status.HTTP_403_FORBIDDEN)

        sale_for_confirm, txn_for_confirm = _payme_ids_for_api_confirm(payload, order)
        sale_for_log = sale_for_confirm
        try:
            confirmed = confirm_payme_sale_status(
                payme_sale_id=sale_for_confirm,
                payme_transaction_id=txn_for_confirm,
            )
        except Exception as confirm_exc:
            logger.warning(
                'PayMe webhook API confirm crashed order_id=%s: %s',
                order_id,
                confirm_exc,
            )
            confirmed = {'ok': False, 'found': False, 'status': None, 'error': str(confirm_exc)}

        if not isinstance(confirmed, dict):
            confirmed = {'ok': False, 'found': False, 'status': None, 'error': 'confirm_failed'}
        api_status = confirmed.get('status')
        confirm_error = confirmed.get('error') or 'confirm_failed'
        confirm_http = confirmed.get('http_status')
        confirm_url = confirmed.get('url')
        confirm_body = (confirmed.get('response_text') or '')[:800]
        if not confirmed.get('ok'):
            outcome['error_message'] = (
                f'payme_api_unavailable http={confirm_http} url={confirm_url} '
                f'error={confirm_error} body={confirm_body}'
            )[:2000]
            logger.error(
                'PayMe webhook API unavailable order_id=%s http=%s url=%s error=%s body=%s',
                order_id,
                confirm_http,
                confirm_url,
                confirm_error,
                confirm_body,
            )
            _log_payme_webhook_rejection(
                'payme_api_unavailable',
                order_id=order_id,
                payload={
                    'error': confirm_error,
                    'http_status': confirm_http,
                    'url': confirm_url,
                    'response_text': confirm_body,
                    'sale': sale_for_log,
                    'txn': txn_for_confirm,
                    'attempts': confirmed.get('attempts'),
                },
            )
            return Response(
                {
                    'received': True,
                    'finalized': False,
                    'reason': 'payme_api_unavailable',
                    'error': confirm_error,
                    'http_status': confirm_http,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not confirmed.get('found'):
            outcome['error_message'] = (
                f'payme_sale_not_found http={confirmed.get("http_status")} '
                f'url={confirmed.get("url")} body={(confirmed.get("response_text") or "")[:400]}'
            )[:2000]
            _log_payme_webhook_rejection(
                'payme_sale_not_found',
                order_id=order_id,
                payload={'sale': sale_for_log, 'txn': txn_for_confirm},
            )
            if order.status == 'paid':
                return Response(
                    {'received': True, 'finalized': True, 'reason': 'already_paid', 'order_status': 'paid'},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {'received': True, 'finalized': False, 'reason': 'payme_sale_not_found'},
                status=status.HTTP_200_OK,
            )

        if api_status != 'success':
            reason = f'api_status_{api_status or "unknown"}'
            outcome['error_message'] = reason
            _log_payme_webhook_rejection(
                reason,
                order_id=order_id,
                payload={
                    'api_status': api_status,
                    'sale': sale_for_log,
                    'txn': txn_for_confirm,
                },
            )
            if order.status == 'paid':
                return Response(
                    {'received': True, 'finalized': True, 'reason': 'already_paid', 'order_status': 'paid'},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {'received': True, 'finalized': False, 'reason': reason},
                status=status.HTTP_200_OK,
            )

        # Direct PayMe API confirmed completed/paid. Ignore webhook-claimed status.
        norm = 'success'
        outcome['is_valid'] = True
        outcome['error_message'] = None

        idem_key = build_payme_webhook_idempotency_key(order, payload)
        sale_for_key = str(sale_for_confirm or txn_for_confirm or order.payme_transaction_id or '')[:128]
        for attempt in range(8):
            try:
                order.payme_status = norm
                order.save(update_fields=['payme_status', 'updated_at'])
                break
            except OperationalError as lock_exc:
                if 'locked' not in str(lock_exc).lower() or attempt == 7:
                    raise
                time.sleep(0.05 * (attempt + 1))
                order.refresh_from_db()

        if order.status == 'paid' and payme_webhook_already_completed(idem_key):
            return Response(
                {
                    'received': True,
                    'finalized': True,
                    'reason': 'already_processed',
                    'order_status': 'paid',
                    'idempotency_key': idem_key,
                }
            )

        if order.status == 'paid' or (norm == 'success' and order.status == 'pending_payment'):
            try:
                last_lock = None
                ok = err = claim = None
                for attempt in range(8):
                    try:
                        ok, err, claim = finalize_payme_webhook_once(
                            order_id,
                            idempotency_key=idem_key,
                            sale_id=sale_for_key,
                            source=(
                                'payme_webhook'
                                if order.status == 'pending_payment'
                                else 'payme_webhook_idempotent_reconcile'
                            ),
                        )
                        last_lock = None
                        break
                    except OperationalError as lock_exc:
                        if 'locked' not in str(lock_exc).lower() or attempt == 7:
                            raise
                        last_lock = lock_exc
                        time.sleep(0.05 * (attempt + 1))
                        order.refresh_from_db()
                if last_lock is not None:
                    raise last_lock
            except Exception as fin_exc:
                logger.exception('PayMe webhook finalize crashed order_id=%s: %s', order_id, fin_exc)
                return Response(
                    {'received': True, 'finalized': False, 'reason': 'finalize_exception'},
                    status=status.HTTP_409_CONFLICT,
                )
            if not ok:
                logger.warning('PayMe webhook rejection reason: finalize_failed:%s order_id=%s', err, order_id)
                return Response(
                    {'received': True, 'finalized': False, 'reason': err or 'finalize_failed'},
                    status=status.HTTP_409_CONFLICT,
                )
            order.refresh_from_db()
            log_payme_dev(
                'webhook_finalize_success',
                order_id=order_id,
                order_status_after=order.status,
                ticket_status=getattr(order.ticket, 'status', None) if order.ticket_id else None,
                idempotency_claim=claim,
            )
            return Response(
                {
                    'received': True,
                    'finalized': True,
                    'order_status': order.status,
                    'idempotency_claim': claim,
                }
            )

        update_fields = ['payme_status', 'updated_at']
        order.payme_status = norm or payload.get('status') or 'unknown'
        # Keep the init-time sale id stable; Apple Pay may send a different TRAN first.
        if tid and tid != payme_ref and payme_ref and tid in possible_payme_refs:
            logger.info(
                'PayMe webhook alternate transaction_id=%s retained stored payme_sale_id=%s order_id=%s',
                tid,
                payme_ref,
                order_id,
            )
        order.save(update_fields=list(dict.fromkeys(update_fields)))

        log_payme(
            'webhook_received',
            order_id=order_id,
            payload={'normalized': norm, 'transaction_id': tid, 'lookup_via': lookup_via},
        )
        log_payme_dev(
            'webhook_verified',
            order_id=order_id,
            normalized_status=norm,
            transaction_id=tid,
            order_status_before=order.status,
            payme_status_saved=order.payme_status,
            verified=verified,
            lookup_via=lookup_via,
        )

        if norm == 'failed':
            return Response({'received': True, 'finalized': False, 'order_status': order.status})

        # Bit often sends Authorisation before Capture. If we cannot finalize yet,
        # ACK 200 so PayMe still delivers the sale/capture notify (409 aborts the chain).
        logger.info(
            'PayMe webhook non-final status acknowledged order_id=%s normalized=%s raw_status=%s',
            order_id,
            norm,
            payload.get('notify_type')
            or payload.get('payme_sale_status')
            or payload.get('status'),
        )
        return Response(
            {
                'received': True,
                'finalized': False,
                'reason': 'webhook_status_not_finalizable',
                'order_status': order.status,
                'normalized_status': norm,
            },
            status=status.HTTP_200_OK,
        )
    except OperationalError as exc:
        if 'locked' not in str(exc).lower():
            raise
        logger.warning(
            'PayMe webhook hit a database write lock order_id=%s; waiting for the winning worker',
            order_id,
        )
        if order_id:
            for _ in range(20):
                time.sleep(0.1)
                locked_order = Order.objects.filter(pk=order_id).first()
                if locked_order is not None and locked_order.status == 'paid':
                    outcome['is_valid'] = True
                    outcome['error_message'] = None
                    return Response(
                        {
                            'received': True,
                            'finalized': True,
                            'reason': 'lock_wait_already_paid',
                            'order_status': 'paid',
                        }
                    )
        outcome['error_message'] = 'db_write_lock'
        return Response(
            {'received': True, 'finalized': False, 'reason': 'db_write_lock'},
            status=status.HTTP_409_CONFLICT,
        )
    except Exception as exc:
        logger.exception(
            'PayMe webhook failed unexpectedly: %s order_id=%s payload=%s',
            exc,
            order_id,
            payload,
        )
        _log_payme_webhook_rejection(
            'unexpected_exception',
            order_id=order_id,
            payload={'error': str(exc), 'payload': payload or {}},
        )
        outcome['error_message'] = str(exc) if settings.DEBUG else 'internal_error'
        reason = str(exc) if settings.DEBUG else 'internal_error'
        return Response({'error': 'webhook failed', 'reason': reason}, status=status.HTTP_400_BAD_REQUEST)
    finally:
        _finalize_payme_webhook_log(
            webhook_log,
            is_valid=bool(outcome.get('is_valid')),
            error_message=outcome.get('error_message'),
        )


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def payme_init_checkout(request):
    """
    Create Payme hosted session for an existing pending_payment order.
    Auth: logged-in owner OR guest_email matching order.
    """
    blocked = shabbat_forbidden_response()
    if blocked is not None:
        return blocked

    if not PayMeSettings.from_django().is_configured:
        return Response(
            {'error': 'Payme is not configured (set PAYME_SELLER_ID).'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    order_id = request.data.get('order_id')
    try:
        oid = int(order_id)
    except (TypeError, ValueError):
        return Response({'error': 'order_id required'}, status=status.HTTP_400_BAD_REQUEST)

    order = Order.objects.select_related('user').filter(pk=oid, status='pending_payment').first()
    if not order:
        return Response({'error': 'Order not found or not awaiting payment.'}, status=status.HTTP_404_NOT_FOUND)

    if order.user_id:
        if not request.user.is_authenticated or request.user.id != order.user_id:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
    else:
        body_email = (request.data.get('guest_email') or '').strip().lower()
        order_email = (order.guest_email or '').strip().lower()
        if not body_email or body_email != order_email:
            return Response({'error': 'guest_email must match this order.'}, status=status.HTTP_403_FORBIDDEN)

    buyer_email = ''
    if order.user_id and order.user:
        buyer_email = (order.user.email or '').strip()
    if not buyer_email:
        buyer_email = (order.guest_email or '').strip()
    if not buyer_email:
        return Response({'error': 'No buyer email on order.'}, status=status.HTTP_400_BAD_REQUEST)

    # Allow checkout to supply / refresh identity (dashboard negotiation path often needs this).
    body_first = (request.data.get('buyer_first_name') or request.data.get('first_name') or '').strip()
    body_last = (request.data.get('buyer_last_name') or request.data.get('last_name') or '').strip()
    body_name = (
        (request.data.get('buyer_full_name') or request.data.get('buyer_name') or '')
        .strip()
    )
    if not body_name and (body_first or body_last):
        body_name = f'{body_first} {body_last}'.strip()
    body_phone = (
        (request.data.get('buyer_phone_number') or request.data.get('buyer_phone') or '')
        .strip()
    )
    if order.user_id and (body_name or body_first or body_last or body_phone):
        user = order.user
        fields = []
        if body_first or body_last:
            if body_first:
                user.first_name = body_first[:150]
                fields.append('first_name')
            if body_last:
                user.last_name = body_last[:150]
                fields.append('last_name')
        elif body_name:
            parts = body_name.split(None, 1)
            user.first_name = parts[0][:150]
            user.last_name = (parts[1] if len(parts) > 1 else '')[:150]
            fields.extend(['first_name', 'last_name'])
        if body_phone:
            user.phone_number = body_phone
            fields.append('phone_number')
        if fields:
            user.save(update_fields=list(dict.fromkeys(fields)))
            order.user = user

    buyer_details = resolve_buyer_details_for_order(order)
    if body_first or body_last:
        buyer_details['buyer_first_name'] = body_first or buyer_details.get('buyer_first_name', '')
        buyer_details['buyer_last_name'] = body_last or buyer_details.get('buyer_last_name', '')
        composed = f"{buyer_details['buyer_first_name']} {buyer_details['buyer_last_name']}".strip()
        if composed:
            buyer_details['buyer_name'] = composed
            buyer_details['buyer_full_name'] = composed
    elif body_name:
        buyer_details['buyer_name'] = body_name
        buyer_details['buyer_full_name'] = body_name
        from services.payme_service import split_buyer_name

        bf, bl = split_buyer_name(body_name)
        buyer_details['buyer_first_name'] = bf
        buyer_details['buyer_last_name'] = bl
    if body_phone:
        phone_norm = normalize_payme_buyer_phone(body_phone)
        buyer_details['buyer_phone'] = phone_norm
        buyer_details['buyer_phone_number'] = phone_norm

    if not buyer_details.get('buyer_name'):
        fallback = fallback_buyer_name_from_email(buyer_email)
        if fallback:
            buyer_details['buyer_name'] = fallback
            buyer_details['buyer_full_name'] = fallback
            buyer_details['buyer_first_name'] = buyer_details.get('buyer_first_name') or fallback
    if not buyer_details.get('buyer_phone'):
        return Response(
            {
                'error': 'Buyer phone is required for PayMe checkout. Complete guest details or update your profile.',
                'code': 'missing_buyer_phone',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    success_url = (request.data.get('success_url') or '').strip()
    failure_url = (request.data.get('failure_url') or '').strip()
    if not success_url or not failure_url:
        return Response({'error': 'success_url and failure_url required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = generate_payme_sale_for_order(
            order,
            buyer_email=buyer_email,
            success_url=success_url,
            failure_url=failure_url,
            buyer_name=buyer_details.get('buyer_full_name') or buyer_details.get('buyer_name'),
            buyer_phone=buyer_details.get('buyer_phone_number') or buyer_details.get('buyer_phone'),
            buyer_first_name=buyer_details.get('buyer_first_name'),
            buyer_last_name=buyer_details.get('buyer_last_name'),
        )
    except PayMeError as exc:
        log_payme(
            'init_payme_error',
            order_id=oid,
            response={'error': str(exc), 'http': exc.http_status},
        )
        # Never expose PayMe upstream payloads or exception text to clients in production.
        if settings.DEBUG:
            return Response(
                {
                    'error': str(exc),
                    'payme_http_status': exc.http_status,
                    'payme_response': exc.payload,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                'error': 'Payment provider is temporarily unavailable. Please try again later.',
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    p_tid = result.get('transaction_id')
    payme_sale_url = result['payme_sale_url']

    if not p_tid:
        log_payme('init_missing_transaction_id', order_id=oid, response=result.get('raw'))
        if settings.DEBUG:
            return Response(
                {'error': 'Payme did not return a transaction ID', 'payme_response': result.get('raw')},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {'error': 'Payment provider did not start checkout. Please try again later.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    order.payme_transaction_id = p_tid
    order.payme_status = 'initialized'
    order.save(update_fields=['payme_transaction_id', 'payme_status', 'updated_at'])

    log_payme_dev(
        'init_checkout_ready',
        order_id=oid,
        transaction_id=p_tid,
        redirect_host=(payme_sale_url or '').split('/')[2] if payme_sale_url else None,
        sandbox=PayMeSettings.from_django().api_url,
    )

    body = {
        'order_id': order.id,
        'redirect_url': payme_sale_url,
        'payme_sale_url': payme_sale_url,
        'payme_transaction_id': p_tid,
    }
    if settings.DEBUG:
        body['payme_raw'] = result.get('raw')
    return Response(body, status=status.HTTP_200_OK)
