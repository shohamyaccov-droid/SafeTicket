"""
Cached access to GlobalFeeSettings rates for checkout math.

Cache is invalidated whenever the singleton is saved.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache
from django.db.utils import OperationalError, ProgrammingError

if TYPE_CHECKING:
    from users.models import Coupon

CACHE_KEY = 'users:global_fee_rates:v1'
CACHE_TTL_SECONDS = 120


@dataclass(frozen=True)
class FeeRates:
    base_buyer_fee_rate: Decimal
    base_seller_fee_rate: Decimal
    buyer_coupon_discount_rate: Decimal
    affiliate_commission_rate: Decimal
    affiliate_platform_net_rate: Decimal
    platform_coupon_platform_net_rate: Decimal

    @classmethod
    def from_percents(
        cls,
        *,
        base_buyer_fee_percent: Decimal,
        base_seller_fee_percent: Decimal,
        buyer_coupon_discount_percent: Decimal,
        affiliate_commission_percent: Decimal,
    ) -> FeeRates:
        q = Decimal('0.0001')

        def pct_to_rate(p: Decimal) -> Decimal:
            return (Decimal(str(p)) / Decimal('100')).quantize(q, rounding=ROUND_HALF_UP)

        buyer = pct_to_rate(base_buyer_fee_percent)
        seller = pct_to_rate(base_seller_fee_percent)
        discount = pct_to_rate(buyer_coupon_discount_percent)
        affiliate = pct_to_rate(affiliate_commission_percent)
        return cls(
            base_buyer_fee_rate=buyer,
            base_seller_fee_rate=seller,
            buyer_coupon_discount_rate=discount,
            affiliate_commission_rate=affiliate,
            affiliate_platform_net_rate=max(buyer - discount - affiliate, Decimal('0.0000')),
            platform_coupon_platform_net_rate=max(buyer - discount, Decimal('0.0000')),
        )


def _rates_from_django_settings() -> FeeRates:
    buyer = Decimal(str(getattr(settings, 'PLATFORM_BUYER_SERVICE_FEE_RATE', '0.07')))
    seller = Decimal(str(getattr(settings, 'PLATFORM_SELLER_SERVICE_FEE_RATE', '0.00')))
    discount = Decimal(str(getattr(settings, 'AFFILIATE_BUYER_DISCOUNT_RATE', '0.05')))
    affiliate = Decimal(str(getattr(settings, 'AFFILIATE_COMMISSION_RATE', '0.02')))
    q = Decimal('0.0001')
    buyer = buyer.quantize(q, rounding=ROUND_HALF_UP)
    seller = seller.quantize(q, rounding=ROUND_HALF_UP)
    discount = discount.quantize(q, rounding=ROUND_HALF_UP)
    affiliate = affiliate.quantize(q, rounding=ROUND_HALF_UP)
    return FeeRates(
        base_buyer_fee_rate=buyer,
        base_seller_fee_rate=seller,
        buyer_coupon_discount_rate=discount,
        affiliate_commission_rate=affiliate,
        affiliate_platform_net_rate=max(buyer - discount - affiliate, Decimal('0.0000')),
        platform_coupon_platform_net_rate=max(buyer - discount, Decimal('0.0000')),
    )


def clear_fee_settings_cache() -> None:
    cache.delete(CACHE_KEY)


def get_fee_rates(*, force_refresh: bool = False) -> FeeRates:
    """
    Return fractional fee rates. Prefer GlobalFeeSettings (singleton); fall back to
    Django settings during migrate / missing table.
    """
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if isinstance(cached, FeeRates):
            return cached

    try:
        from users.models import GlobalFeeSettings

        obj = GlobalFeeSettings.load()
        rates = FeeRates.from_percents(
            base_buyer_fee_percent=obj.base_buyer_fee_percent,
            base_seller_fee_percent=obj.base_seller_fee_percent,
            buyer_coupon_discount_percent=obj.buyer_coupon_discount_percent,
            affiliate_commission_percent=obj.affiliate_commission_percent,
        )
    except (LookupError, OperationalError, ProgrammingError):
        rates = _rates_from_django_settings()

    cache.set(CACHE_KEY, rates, CACHE_TTL_SECONDS)
    return rates


def checkout_split_rates_for_coupon(coupon: 'Coupon') -> tuple[Decimal, Decimal, Decimal]:
    """
    (buyer_discount_rate, affiliate_commission_rate, platform_net_rate) from global fees
    and coupon type. Live checkout ignores stale rates stored on the Coupon row.
    """
    from users.models import Coupon

    fees = get_fee_rates()
    discount = fees.buyer_coupon_discount_rate
    if getattr(coupon, 'coupon_type', None) == Coupon.TYPE_PLATFORM or getattr(coupon, 'is_platform', False):
        return discount, Decimal('0.0000'), fees.platform_coupon_platform_net_rate
    return discount, fees.affiliate_commission_rate, fees.affiliate_platform_net_rate
