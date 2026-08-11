"""
Ticket availability helpers — permanent "taken" (נתפס) vs temporary cart "reserved".
"""
from __future__ import annotations

from rest_framework import status as drf_status
from rest_framework.response import Response

# Permanent marketplace lock — not the temporary 10-minute cart hold.
TICKET_STATUS_TAKEN = 'taken'

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
