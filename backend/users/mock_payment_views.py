"""
DEBUG-only mock payment finalization — simulates a successful PayMe webhook for local E2E QA.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Order
from .payments import finalize_pending_order_to_paid, log_payme_dev
from .serializers import OrderSerializer

logger = logging.getLogger(__name__)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def mock_payment_success(request):
    """
    POST /api/payments/mock-success/ — finalize a pending_payment order (DEBUG only).

    Runs the same path as the PayMe webhook: order → paid, tickets → sold,
    SellerPayout ledger (15% platform fee / 85% net).
    """
    if not settings.DEBUG:
        logger.warning('mock_payment_success rejected: DEBUG is False')
        return Response(
            {'error': 'Mock payment is only available when DEBUG=True.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    order_id = request.data.get('order_id')
    try:
        oid = int(order_id)
    except (TypeError, ValueError):
        return Response({'error': 'order_id required'}, status=status.HTTP_400_BAD_REQUEST)

    order = Order.objects.filter(pk=oid).first()
    if not order:
        return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

    if order.user_id:
        if not request.user.is_authenticated or request.user.id != order.user_id:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
    else:
        body_email = (request.data.get('guest_email') or '').strip().lower()
        order_email = (order.guest_email or '').strip().lower()
        if not body_email or body_email != order_email:
            return Response(
                {'error': 'guest_email must match this order.'},
                status=status.HTTP_403_FORBIDDEN,
            )

    if order.status == 'paid':
        log_payme_dev('mock_payment_already_paid', order_id=oid, order_status=order.status)
        order.refresh_from_db()
        return Response(
            {
                'finalized': True,
                'order_status': order.status,
                'order': OrderSerializer(order, context={'request': request}).data,
            },
            status=status.HTTP_200_OK,
        )

    if order.status != 'pending_payment':
        return Response(
            {'error': 'Order is not awaiting payment.', 'order_status': order.status},
            status=status.HTTP_400_BAD_REQUEST,
        )

    log_payme_dev(
        'mock_payment_start',
        order_id=oid,
        order_status_before=order.status,
        ticket_ids=order.ticket_ids,
    )

    ok, err = finalize_pending_order_to_paid(oid, source='mock_payment_dev')
    if not ok:
        log_payme_dev('mock_payment_failed', order_id=oid, error=err)
        return Response(
            {'error': err or 'Could not finalize order.', 'finalized': False},
            status=status.HTTP_400_BAD_REQUEST,
        )

    order.refresh_from_db()
    log_payme_dev(
        'mock_payment_success',
        order_id=oid,
        order_status_after=order.status,
        ticket_status=getattr(order.ticket, 'status', None) if order.ticket_id else None,
    )

    return Response(
        {
            'finalized': True,
            'order_status': order.status,
            'order': OrderSerializer(order, context={'request': request}).data,
        },
        status=status.HTTP_200_OK,
    )
