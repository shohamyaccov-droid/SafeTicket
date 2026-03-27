"""
Order price breakdown: negotiated vs list price, buyer fee, seller net.
Aligned with frontend: negotiated total = ceil(base * 1.10), fee = ceil(base * 0.10).
"""
from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from django.utils import timezone

if TYPE_CHECKING:
    from .models import Offer, Ticket


def expected_negotiated_total_from_offer_base(offer_base: float) -> float:
    """Total buyer pays for an accepted offer (matches CheckoutModal Math.ceil)."""
    return float(math.ceil(offer_base * 1.10))


def compute_order_price_breakdown(
    total_paid: Any,
    negotiated_offer: Optional['Offer'],
    ticket: 'Ticket',
    order_quantity: int,
) -> dict:
    """
    Populate Order pricing fields from actual charge and listing/offer context.
    - Negotiated: final_negotiated_price = offer amount (seller bundle); net_seller_revenue = same.
    - Buy-now: final_negotiated_price = asking * qty (seller base); fee = total - base.
    """
    total_paid_dec = Decimal(str(total_paid))
    qty = max(1, int(order_quantity or 1))

    if negotiated_offer is not None:
        final_neg = Decimal(str(negotiated_offer.amount))
        fee = total_paid_dec - final_neg
        net = final_neg
    else:
        base_unit = Decimal(str(ticket.asking_price))
        final_neg = base_unit * qty
        fee = total_paid_dec - final_neg
        net = final_neg

    return {
        'final_negotiated_price': final_neg,
        'buyer_service_fee': fee,
        'total_paid_by_buyer': total_paid_dec,
        'net_seller_revenue': net,
    }


def compute_payout_eligible_date(ticket: 'Ticket'):
    """
    Escrow: seller funds unlock 24 hours after event start (event date/time in DB).
    Returns timezone-aware datetime or None if event time unknown.
    """
    event_dt = None
    try:
        if ticket.event_id and ticket.event:
            event_dt = ticket.event.date
    except Exception:
        event_dt = None
    if event_dt is None:
        event_dt = ticket.event_date
    if event_dt is None:
        return None
    if timezone.is_naive(event_dt):
        event_dt = timezone.make_aware(event_dt, timezone.get_current_timezone())
    return event_dt + timedelta(hours=24)
