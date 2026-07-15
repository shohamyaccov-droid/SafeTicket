"""
Order pricing: buyer service fee + seller withholding (rates from Django settings).

Base model: 15% buyer fee (added at checkout) + 0% seller fee (sellers keep 100% of asking price).

Affiliate coupon split (of listing base):
  - 5% buyer discount (buyer pays base + 10% fee instead of +15%)
  - 5% affiliate commission
  - 5% platform net fee

Amounts use Decimal quantized to 0.01 in the listing currency.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Optional

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from .models import Offer, Ticket

QUANT = Decimal('0.01')
ESCROW_RELEASE_DELAY_HOURS = 36


def _buyer_fee_rate() -> Decimal:
    r = getattr(settings, 'PLATFORM_BUYER_SERVICE_FEE_RATE', None)
    if r is None:
        return Decimal('0.15')
    return Decimal(str(r)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def _seller_fee_rate() -> Decimal:
    r = getattr(settings, 'PLATFORM_SELLER_SERVICE_FEE_RATE', None)
    if r is None:
        return Decimal('0.00')
    return Decimal(str(r)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def _affiliate_buyer_discount_rate() -> Decimal:
    r = getattr(settings, 'AFFILIATE_BUYER_DISCOUNT_RATE', None)
    if r is None:
        return Decimal('0.05')
    return Decimal(str(r)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def _affiliate_commission_rate() -> Decimal:
    r = getattr(settings, 'AFFILIATE_COMMISSION_RATE', None)
    if r is None:
        return Decimal('0.05')
    return Decimal(str(r)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def _affiliate_platform_net_rate() -> Decimal:
    r = getattr(settings, 'AFFILIATE_PLATFORM_NET_RATE', None)
    if r is None:
        return Decimal('0.05')
    return Decimal(str(r)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def decimal_money(x: Any) -> Decimal:
    """Parse to Decimal with 2 decimal places (half-up)."""
    if x is None:
        return Decimal('0.00')
    if isinstance(x, Decimal):
        return x.quantize(QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(x)).quantize(QUANT, rounding=ROUND_HALF_UP)


def seller_fee_from_base_amount(base: Any) -> Decimal:
    """Seller-side platform fee withheld from the negotiated / list subtotal."""
    b = decimal_money(base)
    if b <= 0:
        return Decimal('0.00')
    return (b * _seller_fee_rate()).quantize(QUANT, rounding=ROUND_HALF_UP)


def buyer_charge_from_base_amount(base: Any) -> tuple[Decimal, Decimal, Decimal]:
    """
    Returns (base, buyer_service_fee, total_buyer_pays) each quantized to 0.01.
    Total always equals base + fee after quantization.
    """
    b = decimal_money(base)
    if b <= 0:
        return Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
    fee = (b * _buyer_fee_rate()).quantize(QUANT, rounding=ROUND_HALF_UP)
    total = (b + fee).quantize(QUANT, rounding=ROUND_HALF_UP)
    return b, fee, total


def affiliate_checkout_amounts(
    base: Any,
    *,
    buyer_discount_rate: Any = None,
    affiliate_rate: Any = None,
    platform_rate: Any = None,
) -> dict[str, Decimal]:
    """
    Affiliate coupon economics on listing base:
      buyer_fee = base * (full_fee_rate - buyer_discount_rate)  # typically 10%
      buyer_discount = base * buyer_discount_rate               # 5%
      affiliate_commission = base * affiliate_rate              # 5%
      platform_net_fee = base * platform_rate                    # 5%
      total = base + buyer_fee
    """
    b = decimal_money(base)
    if b <= 0:
        zero = Decimal('0.00')
        return {
            'base': zero,
            'buyer_fee': zero,
            'buyer_discount': zero,
            'affiliate_commission': zero,
            'platform_net_fee': zero,
            'total': zero,
        }
    disc = Decimal(str(buyer_discount_rate if buyer_discount_rate is not None else _affiliate_buyer_discount_rate()))
    aff = Decimal(str(affiliate_rate if affiliate_rate is not None else _affiliate_commission_rate()))
    plat = Decimal(str(platform_rate if platform_rate is not None else _affiliate_platform_net_rate()))
    full = _buyer_fee_rate()
    charged_rate = (full - disc).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    if charged_rate < 0:
        charged_rate = Decimal('0.0000')
    buyer_fee = (b * charged_rate).quantize(QUANT, rounding=ROUND_HALF_UP)
    buyer_discount = (b * disc).quantize(QUANT, rounding=ROUND_HALF_UP)
    affiliate_commission = (b * aff).quantize(QUANT, rounding=ROUND_HALF_UP)
    platform_net_fee = (b * plat).quantize(QUANT, rounding=ROUND_HALF_UP)
    total = (b + buyer_fee).quantize(QUANT, rounding=ROUND_HALF_UP)
    return {
        'base': b,
        'buyer_fee': buyer_fee,
        'buyer_discount': buyer_discount,
        'affiliate_commission': affiliate_commission,
        'platform_net_fee': platform_net_fee,
        'total': total,
    }


def list_price_checkout_amounts(unit_asking: Any, quantity: int) -> tuple[Decimal, Decimal, Decimal]:
    """Buy-now at list price: (base_subtotal, service_fee, total) in agorot-accurate Decimal."""
    q = max(1, int(quantity or 1))
    unit = decimal_money(unit_asking)
    base = (unit * Decimal(q)).quantize(QUANT, rounding=ROUND_HALF_UP)
    return buyer_charge_from_base_amount(base)


def expected_negotiated_total_from_offer_base(offer_base: Any) -> Decimal:
    """Total buyer pays for an accepted offer (bundle base amount before fee)."""
    _, _, total = buyer_charge_from_base_amount(offer_base)
    return total


def expected_buy_now_total(unit_asking: Any, quantity: int) -> Decimal:
    """List-price checkout: fee on (unit × qty) subtotal."""
    _, _, total = list_price_checkout_amounts(unit_asking, quantity)
    return total


def payment_amounts_match(received: Any, expected: Any, tol: Any = None) -> bool:
    """Compare checkout totals using Decimal; default ±0.02 ILS tolerance."""
    if tol is None:
        tol = Decimal('0.02')
    return abs(decimal_money(received) - decimal_money(expected)) <= decimal_money(tol)


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
        buyer_fee = total_paid_dec - final_neg
    else:
        base_unit = decimal_money(ticket.asking_price)
        final_neg = (base_unit * Decimal(qty)).quantize(QUANT, rounding=ROUND_HALF_UP)
        buyer_fee = total_paid_dec - final_neg

    seller_fee = seller_fee_from_base_amount(final_neg)
    net_to_seller = (final_neg - seller_fee).quantize(QUANT, rounding=ROUND_HALF_UP)

    return {
        'final_negotiated_price': final_neg,
        'buyer_service_fee': buyer_fee,
        'seller_service_fee': seller_fee,
        'total_paid_by_buyer': total_paid_dec,
        'net_seller_revenue': net_to_seller,
    }


def compute_payout_eligible_date(ticket: 'Ticket'):
    """
    Escrow: seller funds unlock 36 hours after event ends when `event.ends_at` is set;
    otherwise 36 hours after `event.date` (legacy / start time).
    """
    ref_dt = None
    try:
        if ticket.event_id and ticket.event:
            ev = ticket.event
            ref_dt = getattr(ev, 'ends_at', None) or ev.date
    except Exception:
        ref_dt = None
    if ref_dt is None:
        ref_dt = ticket.event_date
    if ref_dt is None:
        return None
    if timezone.is_naive(ref_dt):
        ref_dt = timezone.make_aware(ref_dt, timezone.get_current_timezone())
    return ref_dt + timedelta(hours=ESCROW_RELEASE_DELAY_HOURS)
