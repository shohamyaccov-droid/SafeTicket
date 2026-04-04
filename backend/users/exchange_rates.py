"""
Convert order amounts to ILS for admin dashboard rollups.

Rates are indicative defaults; override with FX_*_ILS environment variables (see settings.FX_RATES_TO_ILS).
"""
from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

_QUANT = Decimal('0.01')


def fx_rate_to_ils(currency_iso: str | None) -> Decimal:
    cur = (currency_iso or 'ILS').strip().upper()
    rates: dict = getattr(settings, 'FX_RATES_TO_ILS', None) or {}
    raw = rates.get(cur)
    if raw is not None:
        return Decimal(str(raw)).quantize(_QUANT, rounding=ROUND_HALF_UP)
    logger.warning('exchange_rates: missing FX for %s; using USD fallback', cur)
    raw_fb = rates.get('USD', Decimal('3.65'))
    return Decimal(str(raw_fb)).quantize(_QUANT, rounding=ROUND_HALF_UP)


def amount_to_ils(amount: Any, currency_iso: str | None) -> Decimal:
    a = Decimal(str(amount or 0))
    return (a * fx_rate_to_ils(currency_iso)).quantize(_QUANT, rounding=ROUND_HALF_UP)


def platform_fx_rates_for_api() -> dict[str, str]:
    """String snapshot for admin JSON (no secrets)."""
    rates: dict = getattr(settings, 'FX_RATES_TO_ILS', None) or {}
    return {k: str(v) for k, v in sorted(rates.items())}


def rollup_fees_and_revenue_ils(by_currency: dict[str, dict]) -> dict[str, str]:
    """
    Sum platform_fees and revenue across currencies into approximate ILS using FX_RATES_TO_ILS.

    by_currency values must include 'platform_fees' and 'revenue' as numeric strings.
    """
    total_fees = Decimal('0')
    total_rev = Decimal('0')
    for cur, bucket in by_currency.items():
        code = (cur or 'ILS').strip().upper()
        fees = Decimal(str(bucket.get('platform_fees') or 0))
        rev = Decimal(str(bucket.get('revenue') or 0))
        total_fees += amount_to_ils(fees, code)
        total_rev += amount_to_ils(rev, code)
    return {
        'platform_fees_ils': str(total_fees.quantize(_QUANT, rounding=ROUND_HALF_UP)),
        'gross_revenue_ils': str(total_rev.quantize(_QUANT, rounding=ROUND_HALF_UP)),
    }
