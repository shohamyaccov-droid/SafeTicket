"""
Ticket availability helpers — permanent "taken" (נתפס) vs temporary cart "reserved".
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import status as drf_status
from rest_framework.response import Response

# Permanent marketplace lock — not the temporary 10-minute cart hold.
TICKET_STATUS_TAKEN = 'taken'
# Must stay in sync with views.RESERVATION_TIMEOUT_MINUTES.
CART_HOLD_MINUTES = 10

# Marketplace rows that must show as unavailable (נתפס) to buyers.
TAKEN_LIKE_STATUSES = frozenset({TICKET_STATUS_TAKEN, 'sold', 'pending_payout'})

HE_TICKET_TAKEN = 'הכרטיס נתפס ואינו זמין לרכישה.'

# Statuses that may proceed through checkout / reserve (when held by the same buyer).
PURCHASABLE_STATUSES = frozenset({'active', 'reserved'})


def is_ticket_taken(ticket) -> bool:
    return getattr(ticket, 'status', None) in TAKEN_LIKE_STATUSES


def ticket_is_taken_flag(ticket) -> bool:
    """Serializer helper: True when listing must render as נתפס."""
    return is_ticket_taken(ticket)


def taken_error_response(*, http_status=drf_status.HTTP_400_BAD_REQUEST) -> Response:
    return Response(
        {'error': HE_TICKET_TAKEN, 'status': TICKET_STATUS_TAKEN},
        status=http_status,
    )


def assert_ticket_not_taken(ticket) -> Response | None:
    """Return a Response if ticket is permanently taken; otherwise None."""
    if is_ticket_taken(ticket):
        return taken_error_response()
    return None


def ticket_has_lockable_inventory(ticket) -> bool:
    """True when this row still has remaining seats that can enter a cart hold."""
    if getattr(ticket, 'status', None) != 'active':
        return False
    return int(getattr(ticket, 'available_quantity', 0) or 0) > 0


def listing_group_id_value(ticket) -> str | None:
    if ticket is None:
        return None
    gid = getattr(ticket, 'listing_group_id', None)
    if gid is None:
        return None
    gid_s = str(gid).strip()
    return gid_s or None


def cart_locked_until(ticket):
    """Naive expiry instant for an in-progress cart hold, or None."""
    if getattr(ticket, 'status', None) != 'reserved':
        return None
    reserved_at = getattr(ticket, 'reserved_at', None)
    if reserved_at is None:
        return None
    return reserved_at + timedelta(minutes=CART_HOLD_MINUTES)


def ticket_is_cart_locked(ticket, *, now=None) -> bool:
    until = cart_locked_until(ticket)
    if until is None:
        return False
    return until > (now or timezone.now())


def marketplace_listing_status_q() -> Q:
    """Public event/ticket lists: buyable, in-cart hold, or permanently taken/sold."""
    return (
        Q(status='active')
        | Q(status='reserved')
        | Q(status=TICKET_STATUS_TAKEN)
        | Q(status__in=('sold', 'pending_payout'))
    )
