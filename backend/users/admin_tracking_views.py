"""Staff/superuser God Mode — offers, waitlist alerts, and site contact messages."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import ContactMessage, Offer, Order, TicketAlert
from users.offer_admin_views import _is_admin, _offer_row, _safe_positive_int

User = get_user_model()


def _phones_by_email(emails: set[str]) -> dict[str, str]:
    cleaned = {e.strip().lower() for e in emails if (e or '').strip()}
    if not cleaned:
        return {}
    out = {}
    for row in User.objects.filter(email__in=cleaned).only('email', 'phone_number'):
        email = (row.email or '').strip().lower()
        phone = (row.phone_number or '').strip()
        if email and phone and email not in out:
            out[email] = phone
    return out


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_god_mode_dashboard(request):
    """
    Central facilitation dashboard: offers, waitlist alerts, and contact messages.
    Restricted to staff / superuser.
    """
    if not _is_admin(request.user):
        return Response(
            {'error': 'Permission denied. Admin access required.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    limit = _safe_positive_int(request.query_params.get('limit'), 100, maximum=300)

    offers_qs = (
        Offer.objects.select_related(
            'buyer',
            'ticket',
            'ticket__seller',
            'ticket__event',
            'parent_offer',
            'parent_offer__parent_offer',
        )
        .prefetch_related(
            Prefetch(
                'orders',
                queryset=Order.objects.filter(status__in=['paid', 'completed']).only(
                    'id', 'related_offer_id', 'status'
                ),
                to_attr='completed_orders',
            )
        )
        .order_by('-created_at', '-id')[:limit]
    )
    offers = [_offer_row(offer) for offer in offers_qs]

    alerts_qs = (
        TicketAlert.objects.select_related('user', 'event', 'artist')
        .order_by('-created_at')[:limit]
    )
    alert_emails = {(a.email or '').strip().lower() for a in alerts_qs}
    alert_emails |= {
        (a.user.email or '').strip().lower()
        for a in alerts_qs
        if a.user_id and getattr(a.user, 'email', None)
    }
    phones = _phones_by_email(alert_emails)

    alerts = []
    for alert in alerts_qs:
        email = (alert.email or '').strip()
        user_phone = (getattr(alert.user, 'phone_number', None) or '').strip() if alert.user_id else ''
        phone = (alert.phone or '').strip() or user_phone or phones.get(email.lower(), '')
        event_name = ''
        if alert.event_id:
            event_name = (alert.event.name or '').strip()
        elif alert.artist_id:
            event_name = f'כל המופעים · {(alert.artist.name or "").strip()}'
        alerts.append(
            {
                'id': alert.pk,
                'email': email,
                'phone': phone,
                'user_id': alert.user_id,
                'username': alert.user.username if alert.user_id else '',
                'event_name': event_name,
                'event_id': alert.event_id,
                'artist_id': alert.artist_id,
                'notified': bool(alert.notified),
                'created_at': alert.created_at.isoformat() if alert.created_at else None,
            }
        )

    messages_qs = ContactMessage.objects.order_by('-created_at')[:limit]
    message_emails = {(m.email or '').strip().lower() for m in messages_qs}
    message_phones = _phones_by_email(message_emails)
    messages = []
    for msg in messages_qs:
        email = (msg.email or '').strip()
        messages.append(
            {
                'id': msg.pk,
                'name': msg.name or '',
                'email': email,
                'phone': message_phones.get(email.lower(), ''),
                'order_number': msg.order_number or '',
                'message': msg.message or '',
                'is_resolved': bool(msg.is_resolved),
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
                # Contact form is site-bound; no peer-to-peer inbox exists yet.
                'receiver': 'TradeTix Support',
            }
        )

    return Response(
        {
            'offers': offers,
            'alerts': alerts,
            'messages': messages,
            'meta': {
                'offers_count': Offer.objects.count(),
                'alerts_count': TicketAlert.objects.count(),
                'messages_count': ContactMessage.objects.count(),
                'limit': limit,
            },
        }
    )
