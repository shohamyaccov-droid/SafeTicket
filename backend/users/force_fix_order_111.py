"""
TEMPORARY emergency endpoint to force-finalize Order #111 (Apple Pay webhook miss).

Remove this module and its URL after the stuck order is fixed.
"""
from __future__ import annotations

import logging
import secrets

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from users.models import Order, Ticket
from users.payments import finalize_pending_order_to_paid

logger = logging.getLogger(__name__)

# Hardcoded one-off gate so this works without Render Shell / new env vars.
# DELETE this endpoint after use.
_FORCE_FIX_ORDER_ID = 111
_FORCE_FIX_BUYER_EMAIL = 'sagi.sabag.19@gmail.com'
_FORCE_FIX_KEY = 'ttx-fix-111-sagi-2026-07-27-a8f3c9'


@csrf_exempt
@require_GET
def force_fix_order_111(request):
    """
    GET /api/force-fix-111/?key=...

    Force-finalizes Order 111 (or Sagi's stuck order) to paid + sold tickets.
    """
    provided = (request.GET.get('key') or '').strip()
    if not provided or not secrets.compare_digest(provided, _FORCE_FIX_KEY):
        return JsonResponse({'status': 'error', 'message': 'Not found.'}, status=404)

    User = get_user_model()
    order = Order.objects.filter(pk=_FORCE_FIX_ORDER_ID).first()
    if order is None:
        order = (
            Order.objects.filter(
                Q(guest_email__iexact=_FORCE_FIX_BUYER_EMAIL)
                | Q(user__email__iexact=_FORCE_FIX_BUYER_EMAIL)
            )
            .filter(status__in=('pending_payment', 'cancelled', 'canceled', 'pending'))
            .order_by('-id')
            .first()
        )

    if order is None:
        return JsonResponse(
            {
                'status': 'error',
                'message': f'Order {_FORCE_FIX_ORDER_ID} / {_FORCE_FIX_BUYER_EMAIL} not found.',
            },
            status=404,
        )

    if order.status == 'paid':
        tids = list(order.ticket_ids or []) or ([order.ticket_id] if order.ticket_id else [])
        tickets = list(
            Ticket.objects.filter(pk__in=tids).values('id', 'status', 'available_quantity')
        )
        return JsonResponse(
            {
                'status': 'success',
                'message': f'Order {order.pk} already paid',
                'order_id': order.pk,
                'order_status': order.status,
                'tickets': tickets,
            }
        )

    if not (order.payme_transaction_id or '').strip():
        return JsonResponse(
            {
                'status': 'error',
                'message': f'Order {order.pk} has no payme_transaction_id; refuse to force-finalize.',
                'order_id': order.pk,
                'order_status': order.status,
            },
            status=400,
        )

    if not order.user_id:
        buyer = User.objects.filter(email__iexact=_FORCE_FIX_BUYER_EMAIL).first()
        if buyer:
            order.user = buyer
            order.save(update_fields=['user', 'updated_at'])
            logger.warning(
                'force_fix_order_111 linked user_id=%s to order_id=%s',
                buyer.pk,
                order.pk,
            )

    ok, err = finalize_pending_order_to_paid(
        order.pk,
        source='http_force_fix_111',
        force_from_admin=True,
    )
    order.refresh_from_db()
    tids = list(order.ticket_ids or []) or ([order.ticket_id] if order.ticket_id else [])
    tickets = list(
        Ticket.objects.filter(pk__in=tids).values('id', 'status', 'available_quantity')
    )

    if not ok:
        logger.warning(
            'force_fix_order_111 failed order_id=%s err=%s status=%s',
            order.pk,
            err,
            order.status,
        )
        return JsonResponse(
            {
                'status': 'error',
                'message': f'Finalize failed: {err}',
                'order_id': order.pk,
                'order_status': order.status,
                'tickets': tickets,
            },
            status=409,
        )

    logger.warning(
        'force_fix_order_111 success order_id=%s status=%s tickets=%s',
        order.pk,
        order.status,
        tickets,
    )
    return JsonResponse(
        {
            'status': 'success',
            'message': f'Order {order.pk} finalized',
            'order_id': order.pk,
            'order_status': order.status,
            'payme_status': order.payme_status,
            'tickets': tickets,
        }
    )
