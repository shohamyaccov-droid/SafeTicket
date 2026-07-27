"""
Payme HTTP handlers: hosted-checkout init + PSP webhooks.
Payme webhook lives at /api/payments/webhook/payme/ (see safeticket.urls).
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from services.payme_service import (
    PayMeError,
    PayMeSettings,
    generate_payme_sale_for_order,
    resolve_buyer_details_for_order,
)

from .models import Order
from .payments import (
    finalize_pending_order_to_paid,
    log_payme,
    log_payme_dev,
    normalize_payme_webhook_status,
    verify_payme_webhook_request,
)
from .shabbat import shabbat_forbidden_response

logger = logging.getLogger(__name__)

_PAYME_WEBHOOK_PARSERS = (FormParser, MultiPartParser, JSONParser)


def _coerce_payme_payload_dict(data: Any) -> dict[str, Any]:
    """Normalize DRF request.data / Django POST into a flat string-keyed dict."""
    if data is None:
        return {}
    if hasattr(data, 'dict'):
        try:
            return data.dict()
        except Exception:
            pass
    if isinstance(data, dict):
        return data
    if hasattr(data, 'keys'):
        return {str(k): data.get(k) for k in data.keys()}
    return {}


def _parse_payme_webhook_payload(request) -> dict[str, Any]:
    """Use Django/DRF parsed request data for PayMe callbacks."""
    try:
        if hasattr(request, 'POST') and request.POST:
            return _coerce_payme_payload_dict(request.POST)
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
    """
    payload: dict[str, Any] | None = None
    order_id: int | None = None
    try:
        try:
            incoming_for_log = request.POST if getattr(request, 'POST', None) else getattr(request, 'data', {})
        except Exception as exc:
            logger.warning('PayMe webhook incoming payload parse error: %s', exc)
            _log_payme_webhook_rejection('payload_parse_error', payload={'error': str(exc)})
            return Response({'error': 'empty payload', 'reason': 'payload_parse_error'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(
            'PayMe webhook incoming content_type=%s remote_addr=%s',
            request.content_type,
            request.META.get('REMOTE_ADDR'),
        )
        log_payme(
            'webhook_incoming',
            payload={'content_type': request.content_type, 'raw': incoming_for_log},
        )

        payload = _parse_payme_webhook_payload(request)
        if not payload:
            _log_payme_webhook_rejection('empty_payload', payload={'content_type': request.content_type})
            return Response({'error': 'empty payload', 'reason': 'empty_payload'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(payload, dict):
            reason = f'invalid_payload_type:{type(payload).__name__}'
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

        try:
            payload = _canonicalize_webhook_payload_for_order(payload, order)
        except Exception as canon_exc:
            logger.exception(
                'PayMe webhook canonicalize failed order_id=%s: %s',
                order_id,
                canon_exc,
            )
            _log_payme_webhook_rejection(
                'canonicalize_failed',
                order_id=order_id,
                payload={'error': str(canon_exc), 'raw_keys': list(payload.keys())},
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
            )
        except Exception as verify_exc:
            logger.exception(
                'PayMe webhook verify/normalize crashed order_id=%s: %s payload=%s',
                order_id,
                verify_exc,
                payload,
            )
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
                    'canonical_payload_keys': list(payload.keys()),
                },
            )
            return Response({'error': 'invalid webhook', 'reason': verify_reason}, status=status.HTTP_403_FORBIDDEN)

        if order.status == 'paid':
            try:
                ok, err = finalize_pending_order_to_paid(order_id, source='payme_webhook_idempotent_reconcile')
            except Exception as fin_exc:
                logger.exception('PayMe webhook paid reconcile crashed order_id=%s: %s', order_id, fin_exc)
                return Response(
                    {'received': True, 'finalized': False, 'reason': 'paid_reconcile_exception'},
                    status=status.HTTP_409_CONFLICT,
                )
            if not ok:
                logger.warning('PayMe webhook rejection reason: paid_reconcile_failed:%s order_id=%s', err, order_id)
                return Response(
                    {'received': True, 'finalized': False, 'reason': err or 'paid_reconcile_failed'},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response({'received': True, 'finalized': True, 'order_status': 'paid'})

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

        if norm in ('success', 'authorized') and order.status == 'pending_payment':
            try:
                ok, err = finalize_pending_order_to_paid(order_id, source='payme_webhook')
            except Exception as fin_exc:
                logger.exception(
                    'PayMe webhook finalize crashed order_id=%s: %s payload=%s',
                    order_id,
                    fin_exc,
                    payload,
                )
                return Response(
                    {'received': True, 'finalized': False, 'reason': 'finalize_exception'},
                    status=status.HTTP_409_CONFLICT,
                )
            log_payme_dev(
                'webhook_finalize',
                order_id=order_id,
                finalized=ok,
                error=err,
                normalized_status=norm,
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
            )
            return Response({'received': True, 'finalized': True, 'order_status': order.status})

        if norm == 'failed':
            return Response({'received': True, 'finalized': False, 'order_status': order.status})

        _log_payme_webhook_rejection(
            'webhook_status_not_finalizable',
            order_id=order_id,
            payload={
                'transaction_id': tid,
                'normalized_status': norm,
                'raw_status': payload.get('status')
                or payload.get('payment_status')
                or payload.get('state')
                or payload.get('transaction_status')
                or payload.get('sale_status')
                or payload.get('payme_sale_status')
                or payload.get('payme_status')
                or payload.get('status_code')
                or payload.get('payme_status_code'),
                'order_status': order.status,
                'lookup_via': lookup_via,
            },
        )
        return Response(
            {
                'received': True,
                'finalized': False,
                'reason': 'webhook_status_not_finalizable',
                'order_status': order.status,
                'normalized_status': norm,
            },
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
        reason = str(exc) if settings.DEBUG else 'internal_error'
        return Response({'error': 'webhook failed', 'reason': reason}, status=status.HTTP_400_BAD_REQUEST)


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

    buyer_details = resolve_buyer_details_for_order(order)
    if not buyer_details.get('buyer_name'):
        return Response(
            {'error': 'Buyer name is required for PayMe checkout. Complete guest details or update your profile.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not buyer_details.get('buyer_phone'):
        return Response(
            {'error': 'Buyer phone is required for PayMe checkout. Complete guest details or update your profile.'},
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
            buyer_name=buyer_details.get('buyer_name'),
            buyer_phone=buyer_details.get('buyer_phone'),
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
