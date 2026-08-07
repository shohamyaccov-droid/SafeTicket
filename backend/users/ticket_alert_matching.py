"""
Helpers for matching TicketAlert desired_quantity against a new listing.
"""
from __future__ import annotations

from django.db.models import Q, Sum


def listing_available_quantity(ticket) -> int:
    """
    Units available for matching: sum of active tickets in the listing group,
    otherwise the single ticket's available_quantity.
    """
    group_id = getattr(ticket, 'listing_group_id', None)
    if group_id:
        from .models import Ticket

        total = (
            Ticket.objects.filter(listing_group_id=group_id, status='active').aggregate(
                s=Sum('available_quantity'),
            )['s']
            or 0
        )
        return int(total)
    return int(getattr(ticket, 'available_quantity', None) or 0)


def is_any_quantity(desired_quantity) -> bool:
    """Null or 0 means the subscriber accepts any listing size."""
    return desired_quantity is None or int(desired_quantity) <= 0


def alert_matches_desired_quantity(desired_quantity, available: int) -> bool:
    """True if this alert should be notified for a listing of `available` units."""
    if is_any_quantity(desired_quantity):
        return True
    return int(available) >= int(desired_quantity)


def matching_alerts_filter(available: int) -> Q:
    """ORM filter: any-quantity alerts, or those whose desired count fits the listing."""
    available = int(available or 0)
    return (
        Q(desired_quantity__isnull=True)
        | Q(desired_quantity__lte=0)
        | Q(desired_quantity__lte=available)
    )


def prioritize_alerts(alerts):
    """
    Prefer specific quantity requests over "any", then larger desired counts,
    then earlier subscribers.
    """
    def sort_key(alert):
        want = alert.desired_quantity
        specific = 0 if not is_any_quantity(want) else 1
        return (specific, -(int(want) if want else 0), alert.created_at)

    return sorted(list(alerts), key=sort_key)
