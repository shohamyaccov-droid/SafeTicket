"""Staff-only offer analytics and tracking API."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Prefetch, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import Offer, Order


OFFER_STATUSES = {value for value, _label in Offer.STATUS_CHOICES}


def _is_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def _safe_positive_int(raw, default: int, *, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def _percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return '0.00'
    value = (Decimal(numerator) * Decimal('100') / Decimal(denominator)).quantize(
        Decimal('0.01')
    )
    return str(value)


def _conversation_root_id(offer: Offer) -> int:
    current = offer
    seen = set()
    while current.parent_offer_id and current.parent_offer_id not in seen:
        seen.add(current.pk)
        current = current.parent_offer
    return current.pk


def _offer_row(offer: Offer) -> dict:
    ticket = offer.ticket
    event = getattr(ticket, 'event', None)
    completed_orders = getattr(offer, 'completed_orders', [])
    completed_order = completed_orders[0] if completed_orders else None
    quantity = max(1, int(offer.quantity or 1))
    unit_asking = Decimal(ticket.asking_price or 0).quantize(Decimal('0.01'))
    asking_total = (unit_asking * Decimal(quantity)).quantize(Decimal('0.01'))
    discount_percent = None
    if asking_total > 0:
        discount_percent = (
            (asking_total - Decimal(offer.amount)) * Decimal('100') / asking_total
        ).quantize(Decimal('0.01'))

    round_count = int(offer.offer_round_count or 0)
    sender = offer.buyer if round_count in (0, 2) else ticket.seller
    recipient = ticket.seller if round_count in (0, 2) else offer.buyer

    def _party(user_obj, user_id):
        return {
            'id': user_id,
            'username': getattr(user_obj, 'username', '') or '',
            'email': getattr(user_obj, 'email', '') or '',
            'phone_number': (getattr(user_obj, 'phone_number', None) or '').strip(),
            'full_name': (
                f'{(getattr(user_obj, "first_name", None) or "").strip()} '
                f'{(getattr(user_obj, "last_name", None) or "").strip()}'
            ).strip(),
        }

    return {
        'id': offer.pk,
        'conversation_id': _conversation_root_id(offer),
        'buyer': _party(offer.buyer, offer.buyer_id),
        'seller': _party(ticket.seller, ticket.seller_id),
        'sender_username': sender.username,
        'recipient_username': recipient.username,
        'ticket_id': ticket.pk,
        'event_name': (getattr(event, 'name', '') or ticket.event_name or '').strip(),
        'original_price': str(unit_asking),
        'amount': str(offer.amount),
        'asking_total': str(asking_total),
        'discount_percent': str(discount_percent) if discount_percent is not None else None,
        'currency': (offer.currency or 'ILS').strip().upper(),
        'quantity': quantity,
        'status': offer.status,
        'round': round_count,
        'parent_offer_id': offer.parent_offer_id,
        'expires_at': offer.expires_at.isoformat() if offer.expires_at else None,
        'accepted_at': offer.accepted_at.isoformat() if offer.accepted_at else None,
        'checkout_expires_at': (
            offer.checkout_expires_at.isoformat() if offer.checkout_expires_at else None
        ),
        'checkout_expired': bool(
            offer.status == 'accepted'
            and offer.checkout_expires_at
            and offer.checkout_expires_at < timezone.now()
            and completed_order is None
        ),
        'purchase_completed': completed_order is not None,
        'order_id': completed_order.pk if completed_order else None,
        'created_at': offer.created_at.isoformat() if offer.created_at else None,
        'updated_at': offer.updated_at.isoformat() if offer.updated_at else None,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_offers_dashboard(request):
    """Offer rows, filters, and engagement metrics for the dedicated staff dashboard."""
    if not _is_admin(request.user):
        return Response(
            {'error': 'Permission denied. Admin access required.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    now = timezone.now()
    Offer.objects.filter(status='pending', expires_at__lt=now).update(status='expired')

    metrics_qs = Offer.objects.all()
    status_counts = {key: 0 for key in OFFER_STATUSES}
    for row in metrics_qs.values('status').annotate(total=Count('id')):
        status_counts[row['status']] = int(row['total'])

    root_count = metrics_qs.filter(offer_round_count=0).count()
    accepted_count = metrics_qs.filter(status='accepted').count()
    purchased_count = (
        metrics_qs.filter(
            status='accepted',
            orders__status__in=['paid', 'completed'],
        )
        .distinct()
        .count()
    )
    responded_roots = metrics_qs.filter(
        offer_round_count=0,
        status__in=['accepted', 'rejected', 'countered', 'expired'],
    ).count()
    # A round-1 row can only be created once per root conversation.
    countered_conversations = metrics_qs.filter(offer_round_count=1).count()

    by_currency = []
    for row in metrics_qs.values('currency').annotate(
        count=Count('id'),
        average_amount=Avg('amount'),
    ).order_by('currency'):
        by_currency.append(
            {
                'currency': (row['currency'] or 'ILS').strip().upper(),
                'count': int(row['count']),
                'average_amount': str(
                    Decimal(row['average_amount'] or 0).quantize(Decimal('0.01'))
                ),
            }
        )

    timeline_start = now - timedelta(days=13)
    timeline_map = {
        row['day'].isoformat(): int(row['count'])
        for row in metrics_qs.filter(created_at__gte=timeline_start)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    }
    daily_activity = []
    for offset in range(13, -1, -1):
        day = (now - timedelta(days=offset)).date().isoformat()
        daily_activity.append({'date': day, 'count': timeline_map.get(day, 0)})

    rows_qs = metrics_qs.select_related(
        'buyer',
        'ticket',
        'ticket__seller',
        'ticket__event',
        'parent_offer',
        'parent_offer__parent_offer',
    ).prefetch_related(
        Prefetch(
            'orders',
            queryset=Order.objects.filter(status__in=['paid', 'completed']).only(
                'id', 'related_offer_id', 'status'
            ),
            to_attr='completed_orders',
        )
    )

    status_filter = (request.query_params.get('status') or 'all').strip().lower()
    if status_filter != 'all':
        if status_filter not in OFFER_STATUSES:
            return Response(
                {'error': 'Invalid offer status filter.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows_qs = rows_qs.filter(status=status_filter)

    days_raw = (request.query_params.get('days') or '30').strip().lower()
    if days_raw != 'all':
        days = _safe_positive_int(days_raw, 30, maximum=3650)
        rows_qs = rows_qs.filter(created_at__gte=now - timedelta(days=days))

    query = (request.query_params.get('q') or '').strip()[:100]
    if query:
        search = (
            Q(buyer__username__icontains=query)
            | Q(buyer__email__icontains=query)
            | Q(ticket__seller__username__icontains=query)
            | Q(ticket__seller__email__icontains=query)
            | Q(ticket__event__name__icontains=query)
            | Q(ticket__event_name__icontains=query)
        )
        if query.isdigit():
            search |= Q(pk=int(query)) | Q(ticket_id=int(query))
        rows_qs = rows_qs.filter(search)

    page = _safe_positive_int(request.query_params.get('page'), 1, maximum=1000000)
    page_size = _safe_positive_int(
        request.query_params.get('page_size'),
        50,
        maximum=100,
    )
    total_filtered = rows_qs.count()
    offset = (page - 1) * page_size
    offers = list(rows_qs.order_by('-created_at', '-id')[offset:offset + page_size])

    return Response(
        {
            'metrics': {
                'total_offers': metrics_qs.count(),
                'total_conversations': root_count,
                'status_counts': status_counts,
                'unique_buyers': metrics_qs.values('buyer_id').distinct().count(),
                'unique_sellers': metrics_qs.values('ticket__seller_id').distinct().count(),
                'response_rate_percent': _percent(responded_roots, root_count),
                'acceptance_rate_percent': _percent(accepted_count, root_count),
                'purchase_conversion_percent': _percent(purchased_count, accepted_count),
                'accepted_offers': accepted_count,
                'completed_purchases': purchased_count,
                'countered_conversations': countered_conversations,
                'by_currency': by_currency,
                'daily_activity': daily_activity,
            },
            'filters': {
                'status': status_filter,
                'days': days_raw,
                'q': query,
            },
            'count': total_filtered,
            'page': page,
            'page_size': page_size,
            'results': [_offer_row(offer) for offer in offers],
        }
    )
