"""
Payme HTTP handlers: hosted-checkout init + PSP webhooks.
Webhook lives at /api/payments/webhook/ (see safeticket.urls).
"""
from __future__ import annotations

import json
import logging

from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Order
from .payments import (
    build_marketplace_generate_sale_body,
    extract_redirect_url,
    extract_transaction_id,
    finalize_pending_order_to_paid,
    get_payme_config,
    log_payme,
    normalize_payme_webhook_status,
    post_generate_sale,
    verify_payme_webhook_request,
)

logger = logging.getLogger(__name__)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def payme_webhook(request):
    """
    Payme → TradeTix status updates. Configure Payme dashboard to POST here.
    """
    raw_body = request.body or b''
    try:
        payload = json.loads(raw_body or b'{}')
    except Exception as e:
        log_payme('webhook_bad_json', exc=e)
        return Response({'error': 'invalid json'}, status=status.HTTP_400_BAD_REQUEST)

    if not isinstance(payload, dict):
        return Response({'error': 'expected object'}, status=status.HTTP_400_BAD_REQUEST)

    oid_raw = (
        payload.get('merchant_order_id')
        or payload.get('merchantOrderId')
        or (payload.get('metadata') or {}).get('order_id')
    )
    try:
        order_id = int(oid_raw)
    except (TypeError, ValueError):
        log_payme('webhook_missing_order', payload=payload)
        return Response({'error': 'merchant_order_id required'}, status=status.HTTP_400_BAD_REQUEST)

    tid, norm = normalize_payme_webhook_status(payload)
    order = Order.objects.filter(pk=order_id).first()
    if not order:
        log_payme('webhook_order_not_found', order_id=order_id, payload={'merchant_order_id': oid_raw})
        return Response({'error': 'order not found'}, status=status.HTTP_404_NOT_FOUND)

    verified, verify_reason = verify_payme_webhook_request(
        request,
        payload=payload,
        order=order,
        raw_body=raw_body,
    )
    if not verified:
        log_payme(
            'webhook_rejected_validation',
            order_id=order_id,
            payload={
                'reason': verify_reason,
                'stored_transaction_id': order.payme_transaction_id,
                'order_currency': order.currency,
            },
        )
        return Response({'error': 'invalid webhook'}, status=status.HTTP_403_FORBIDDEN)

    if order.status == 'paid':
        return Response({'received': True, 'finalized': True, 'order_status': 'paid'})

    update_fields = ['payme_status', 'updated_at']
    order.payme_status = norm or payload.get('status') or 'unknown'
    if tid:
        order.payme_transaction_id = tid
        update_fields.insert(0, 'payme_transaction_id')
    order.save(update_fields=list(dict.fromkeys(update_fields)))

    log_payme('webhook_received', order_id=order_id, payload={'normalized': norm, 'transaction_id': tid})

    if norm in ('success', 'authorized') and order.status == 'pending_payment':
        ok, err = finalize_pending_order_to_paid(order_id, source='payme_webhook')
        if not ok:
            logger.warning('payme_webhook finalize failed order_id=%s err=%s', order_id, err)
            return Response({'received': True, 'finalized': False, 'reason': err}, status=status.HTTP_200_OK)
        order.refresh_from_db()
        return Response({'received': True, 'finalized': True, 'order_status': order.status})

    if norm == 'failed':
        return Response({'received': True, 'finalized': False, 'order_status': order.status})

    return Response({'received': True, 'finalized': False, 'order_status': order.status})


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def payme_init_checkout(request):
    """
    Create Payme hosted session for an existing pending_payment order.
    Auth: logged-in owner OR guest_email matching order.
    """
    cfg = get_payme_config()
    if not (cfg.get('api_key') or cfg.get('merchant_id')):
        return Response(
            {'error': 'Payme is not configured (set PAYME_API_KEY / PAYME_MERCHANT_ID).'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    order_id = request.data.get('order_id')
    try:
        oid = int(order_id)
    except (TypeError, ValueError):
        return Response({'error': 'order_id required'}, status=status.HTTP_400_BAD_REQUEST)

    order = Order.objects.filter(pk=oid, status='pending_payment').first()
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

    success_url = (request.data.get('success_url') or '').strip()
    failure_url = (request.data.get('failure_url') or '').strip()
    if not success_url or not failure_url:
        return Response({'error': 'success_url and failure_url required'}, status=status.HTTP_400_BAD_REQUEST)

    body = build_marketplace_generate_sale_body(
        order,
        buyer_email=buyer_email,
        success_url=success_url,
        failure_url=failure_url,
    )

    try:
        http_status, payme_response = post_generate_sale(body)
    except Exception as e:
        log_payme('init_post_error', order_id=oid, exc=e)
        return Response({'error': 'Payme request failed'}, status=status.HTTP_502_BAD_GATEWAY)

    redirect_url = extract_redirect_url(payme_response)
    p_tid = extract_transaction_id(payme_response)

    if http_status >= 400 or not redirect_url or not p_tid:
        log_payme('init_unexpected_response', order_id=oid, response={'http': http_status, 'body': payme_response})
        return Response(
            {
                'error': 'Payme did not return a redirect URL and transaction ID',
                'payme_http_status': http_status,
                'payme_response': payme_response,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    order.payme_transaction_id = p_tid
    order.payme_status = 'initialized'
    order.save(update_fields=['payme_transaction_id', 'payme_status', 'updated_at'])

    return Response(
        {
            'order_id': order.id,
            'redirect_url': redirect_url,
            'payme_transaction_id': p_tid,
            'payme_raw': payme_response,
        },
        status=status.HTTP_200_OK,
    )
