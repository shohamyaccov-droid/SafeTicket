"""
Payme HTTP handlers: hosted-checkout init + PSP webhooks.
Payme webhook lives at /api/payments/webhook/payme/ (see safeticket.urls).
"""
from __future__ import annotations

import logging
from typing import Any

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


def _log_payme_webhook_rejection(reason: str, *, order_id: int | None = None, payload: dict[str, Any] | None = None):
    logger.warning('PayMe webhook rejection reason: %s order_id=%s payload=%s', reason, order_id, payload)
    print(f'PayMe webhook rejection reason: {reason} order_id={order_id} payload={payload}')
    log_payme('webhook_rejected', order_id=order_id, payload={'reason': reason, 'payload': payload or {}})


@csrf_exempt
@api_view(['POST'])
@parser_classes(_PAYME_WEBHOOK_PARSERS)
@permission_classes([AllowAny])
def payme_webhook(request):
    """
    Payme → TradeTix status updates. Configure Payme dashboard to POST here.
    """
    try:
        try:
            incoming_for_log = request.POST if getattr(request, 'POST', None) else getattr(request, 'data', {})
        except Exception as exc:
            logger.warning('PayMe webhook incoming payload parse error: %s', exc)
            print(f'PayMe webhook incoming payload parse error: {exc}')
            _log_payme_webhook_rejection('payload_parse_error', payload={'error': str(exc)})
            return Response({'error': 'empty payload', 'reason': 'payload_parse_error'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info('PayMe webhook incoming payload=%s content_type=%s', incoming_for_log, request.content_type)
        print(f'PayMe webhook incoming payload={incoming_for_log} content_type={request.content_type}')
        logger.info(
            'PayMe webhook incoming content_type=%s remote_addr=%s',
            request.content_type,
            request.META.get('REMOTE_ADDR'),
        )

        payload = _parse_payme_webhook_payload(request)
        if not payload:
            _log_payme_webhook_rejection('empty_payload', payload={'content_type': request.content_type})
            return Response({'error': 'empty payload', 'reason': 'empty_payload'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(payload, dict):
            reason = f'invalid_payload_type:{type(payload).__name__}'
            _log_payme_webhook_rejection(reason)
            return Response({'error': 'expected object', 'reason': reason}, status=status.HTTP_400_BAD_REQUEST)

        payme_ref_raw, payme_ref_source = _extract_payme_transaction_reference(payload)
        possible_payme_refs, payme_ref_sources = _extract_payme_transaction_references(payload)
        oid_raw, oid_source = _extract_payme_order_reference(payload)
        logger.warning(
            'PayMe webhook extracted payme reference=%s source=%s possible_payme_refs=%s merchant_order_reference=%s merchant_source=%s payload_keys=%s',
            payme_ref_raw,
            payme_ref_source,
            possible_payme_refs,
            oid_raw,
            oid_source,
            list(payload.keys()),
        )
        print(
            f'PayMe webhook extracted payme reference={payme_ref_raw} source={payme_ref_source} '
            f'possible_payme_refs={possible_payme_refs} '
            f'merchant_order_reference={oid_raw} merchant_source={oid_source} '
            f'payload_keys={list(payload.keys())}'
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

        if not possible_payme_refs:
            _log_payme_webhook_rejection('payme_transaction_reference_required', payload=payload)
            return Response(
                {'error': 'payme transaction reference required', 'reason': 'payme_transaction_reference_required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.warning(
            'PayMe webhook looking up Order by payme_transaction_id__in=%s sources=%s',
            possible_payme_refs,
            payme_ref_sources,
        )
        print(
            f'PayMe webhook looking up Order by payme_transaction_id__in={possible_payme_refs} '
            f'sources={payme_ref_sources}'
        )
        order = Order.objects.filter(payme_transaction_id__in=possible_payme_refs).first()
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
        payme_ref_source = payme_ref_sources.get(payme_ref) or payme_ref_source
        if not payload.get('merchant_order_id'):
            logger.warning(
                'PayMe webhook normalized merchant_order_id=%s after payme_transaction_id lookup=%s',
                order_id,
                payme_ref,
            )
            print(
                f'PayMe webhook normalized merchant_order_id={order_id} '
                f'after payme_transaction_id lookup={payme_ref}'
            )
            payload['merchant_order_id'] = str(order_id)
        if not payload.get('transaction_id'):
            payload['transaction_id'] = payme_ref

        tid, norm = normalize_payme_webhook_status(payload)
        verified, verify_reason = verify_payme_webhook_request(
            request,
            payload=payload,
            order=order,
        )
        if not verified:
            _log_payme_webhook_rejection(
                verify_reason,
                order_id=order_id,
                payload={
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
                },
            )
            return Response({'error': 'invalid webhook', 'reason': verify_reason}, status=status.HTTP_403_FORBIDDEN)

        if order.status == 'paid':
            ok, err = finalize_pending_order_to_paid(order_id, source='payme_webhook_idempotent_reconcile')
            if not ok:
                logger.warning('PayMe webhook rejection reason: paid_reconcile_failed:%s order_id=%s', err, order_id)
                print(f'PayMe webhook rejection reason: paid_reconcile_failed:{err} order_id={order_id}')
                return Response(
                    {'received': True, 'finalized': False, 'reason': err or 'paid_reconcile_failed'},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response({'received': True, 'finalized': True, 'order_status': 'paid'})

        update_fields = ['payme_status', 'updated_at']
        order.payme_status = norm or payload.get('status') or 'unknown'
        if tid:
            order.payme_transaction_id = tid
            update_fields.insert(0, 'payme_transaction_id')
        order.save(update_fields=list(dict.fromkeys(update_fields)))

        log_payme('webhook_received', order_id=order_id, payload={'normalized': norm, 'transaction_id': tid})
        log_payme_dev(
            'webhook_verified',
            order_id=order_id,
            normalized_status=norm,
            transaction_id=tid,
            order_status_before=order.status,
            payme_status_saved=order.payme_status,
            verified=verified,
        )

        if norm in ('success', 'authorized') and order.status == 'pending_payment':
            ok, err = finalize_pending_order_to_paid(order_id, source='payme_webhook')
            log_payme_dev(
                'webhook_finalize',
                order_id=order_id,
                finalized=ok,
                error=err,
                normalized_status=norm,
            )
            if not ok:
                logger.warning('PayMe webhook rejection reason: finalize_failed:%s order_id=%s', err, order_id)
                print(f'PayMe webhook rejection reason: finalize_failed:{err} order_id={order_id}')
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
                or payload.get('payme_status')
                or payload.get('status_code')
                or payload.get('payme_status_code'),
                'order_status': order.status,
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
        logger.exception('PayMe webhook failed unexpectedly: %s', exc)
        print(f'PayMe webhook failed unexpectedly: {exc}')
        _log_payme_webhook_rejection('unexpected_exception', payload={'error': str(exc)})
        return Response({'error': 'webhook failed', 'reason': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def payme_init_checkout(request):
    """
    Create Payme hosted session for an existing pending_payment order.
    Auth: logged-in owner OR guest_email matching order.
    """
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
        return Response(
            {
                'error': str(exc),
                'payme_http_status': exc.http_status,
                'payme_response': exc.payload,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    p_tid = result.get('transaction_id')
    payme_sale_url = result['payme_sale_url']

    if not p_tid:
        log_payme('init_missing_transaction_id', order_id=oid, response=result.get('raw'))
        return Response(
            {'error': 'Payme did not return a transaction ID', 'payme_response': result.get('raw')},
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

    return Response(
        {
            'order_id': order.id,
            'redirect_url': payme_sale_url,
            'payme_sale_url': payme_sale_url,
            'payme_transaction_id': p_tid,
            'payme_raw': result.get('raw'),
        },
        status=status.HTTP_200_OK,
    )
