"""
Order pricing: buyer pays base (seller bundle) + 10% service fee.
All amounts use Decimal quantized to 0.01 ILS (agorot); no Math.ceil drift.

Formula: fee = round(base * 0.10, 2), total = round(base + fee, 2) — equivalent to
charging 10% on the base subtotal in one pass.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Optional

from django.utils import timezone

if TYPE_CHECKING:
    from .models import Offer, Ticket

QUANT = Decimal('0.01')


def decimal_money(x: Any) -> Decimal:
    """Parse to Decimal with 2 decimal places (half-up)."""
    if x is None:
        return Decimal('0.00')
    if isinstance(x, Decimal):
        return x.quantize(QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(x)).quantize(QUANT, rounding=ROUND_HALF_UP)


def buyer_charge_from_base_amount(base: Any) -> tuple[Decimal, Decimal, Decimal]:
    """
    Returns (base, buyer_service_fee, total_buyer_pays) each quantized to 0.01.
    Total always equals base + fee after quantization.
    """
    b = decimal_money(base)
    if b <= 0:
        return Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
    fee = (b * Decimal('0.10')).quantize(QUANT, rounding=ROUND_HALF_UP)
    total = (b + fee).quantize(QUANT, rounding=ROUND_HALF_UP)
    return b, fee, total


def expected_negotiated_total_from_offer_base(offer_base: float) -> float:
    """Total buyer pays for an accepted offer (bundle base amount before fee)."""
    _, _, total = buyer_charge_from_base_amount(offer_base)
    return float(total)


def expected_buy_now_total(unit_asking: Any, quantity: int) -> float:
    """List-price checkout: fee on (unit * qty) subtotal."""
    q = max(1, int(quantity or 1))
    unit = decimal_money(unit_asking)
    base = (unit * Decimal(q)).quantize(QUANT, rounding=ROUND_HALF_UP)
    _, _, total = buyer_charge_from_base_amount(base)
    return float(total)


def amounts_close(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(decimal_money(a) - decimal_money(b)) <= decimal_money(tol)


def compute_order_price_breakdown(
    total_paid: Any,
    negotiated_offer: Optional['Offer'],
    ticket: 'Ticket',
    order_quantity: int,
) -> dict:
    """
    Populate Order pricing fields from actual charge and listing/offer context.
    """
    total_paid_dec = decimal_money(total_paid)
    qty = max(1, int(order_quantity or 1))

    if negotiated_offer is not None:
        final_neg = decimal_money(negotiated_offer.amount)
        fee = total_paid_dec - final_neg
        net = final_neg
    else:
        base_unit = decimal_money(ticket.asking_price)
        final_neg = (base_unit * Decimal(qty)).quantize(QUANT, rounding=ROUND_HALF_UP)
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
