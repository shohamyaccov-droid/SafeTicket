"""
Ticket availability helpers — permanent "taken" (נתפס) vs temporary cart "reserved".
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import status as drf_status
from rest_framework.response import Response

# Permanent marketplace lock — not the temporary cart hold.
TICKET_STATUS_TAKEN = 'taken'
# Stage 1: Buy Now / details form. Must stay in sync with views.RESERVATION_TIMEOUT_MINUTES.
CART_HOLD_MINUTES = 2
# Stage 2: pending_payment / PayMe — extended when the Order is created.
PAYMENT_HOLD_MINUTES = 10

# Marketplace rows that must show as unavailable (נתפס) to buyers.
TAKEN_LIKE_STATUSES = frozenset({TICKET_STATUS_TAKEN, 'sold', 'pending_payout'})

HE_TICKET_TAKEN = 'הכרטיס נתפס ואינו זמין לרכישה.'
HE_PRICE_EDIT_LOCKED = 'לא ניתן לעדכן מחיר, משתמש אחר נמצא כרגע בתהליך רכישה.'

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


def cart_hold_expires_at(now=None):
    return (now or timezone.now()) + timedelta(minutes=CART_HOLD_MINUTES)


def payment_hold_expires_at(now=None):
    return (now or timezone.now()) + timedelta(minutes=PAYMENT_HOLD_MINUTES)


def stamp_cart_hold(ticket, *, now=None):
    """Stage 1 lock: 2 minutes to fill checkout details."""
    now = now or timezone.now()
    ticket.reserved_at = now
    ticket.locked_until = cart_hold_expires_at(now)
    return ticket.locked_until


def stamp_payment_hold(ticket, *, now=None):
    """Stage 2 lock: 10 minutes to complete PayMe after the Order exists."""
    now = now or timezone.now()
    ticket.locked_until = payment_hold_expires_at(now)
    return ticket.locked_until


def clear_cart_hold_fields(ticket):
    ticket.reserved_at = None
    ticket.locked_until = None
    ticket.reserved_by = None
    ticket.reservation_email = None


def cart_locked_until(ticket):
    """Expiry instant for an in-progress cart hold, or None."""
    if getattr(ticket, 'status', None) != 'reserved':
        return None
    until = getattr(ticket, 'locked_until', None)
    if until is not None:
        return until
    reserved_at = getattr(ticket, 'reserved_at', None)
    if reserved_at is None:
        return None
    return reserved_at + timedelta(minutes=CART_HOLD_MINUTES)


def ticket_is_cart_locked(ticket, *, now=None) -> bool:
    until = cart_locked_until(ticket)
    if until is None:
        return False
    return until > (now or timezone.now())


def expired_cart_reservation_q(now=None):
    """ORM filter for reserved rows whose two-stage TTL has elapsed."""
    now = now or timezone.now()
    cart_cutoff = now - timedelta(minutes=CART_HOLD_MINUTES)
    return (
        Q(status='reserved')
        & (
            Q(locked_until__isnull=False, locked_until__lte=now)
            | Q(locked_until__isnull=True, reserved_at__lt=cart_cutoff)
            | Q(locked_until__isnull=True, reserved_at__isnull=True)
        )
    )


def extend_payment_hold_for_ticket_ids(ticket_ids, *, now=None):
    """Bump reserved rows to the 10-minute PayMe hold. Returns the new expiry."""
    from users.models import Ticket

    now = now or timezone.now()
    until = payment_hold_expires_at(now)
    ids = []
    seen = set()
    for raw in ticket_ids or []:
        try:
            tid = int(raw)
        except (TypeError, ValueError):
            continue
        if tid not in seen:
            seen.add(tid)
            ids.append(tid)
    if not ids:
        return until
    Ticket.objects.filter(pk__in=ids, status='reserved').update(locked_until=until)
    return until


def marketplace_listing_status_q() -> Q:
    """Public event/ticket lists: buyable, in-cart hold, or permanently taken/sold."""
    return (
        Q(status='active')
        | Q(status='reserved')
        | Q(status=TICKET_STATUS_TAKEN)
        | Q(status__in=('sold', 'pending_payout'))
    )
