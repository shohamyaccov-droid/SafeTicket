"""
Event.country → ISO 4217 currency for listings, offers, orders (no mixed-currency negotiation).
Fee math: buyer pays base + 10%; seller net is base − 5% (platform total 15% on the bundle).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
QUANT_MAJOR = Decimal('0.01')
QUANT_ILS = Decimal('1')


def iso4217_for_country(country_code: str | None) -> str:
    """Map Event.country (alpha-2) to ISO 4217."""
    c = (country_code or 'IL').strip().upper()
    if not c:
        c = 'IL'
    if c == 'IL':
        return 'ILS'
    if c == 'US':
        return 'USD'
    if c == 'GB':
        return 'GBP'
    if c in ('DE', 'FR', 'ES', 'IT', 'GR', 'CY'):
        return 'EUR'
    if c == 'AE':
        return 'USD'
    return 'ILS'


def currency_symbol(iso: str) -> str:
    return {
        'ILS': '₪',
        'USD': '$',
        'GBP': '£',
        'EUR': '€',
    }.get((iso or 'ILS').upper(), iso)


def currency_label_meta(country_code: str | None) -> dict:
    code = iso4217_for_country(country_code)
    return {'currency': code, 'currency_symbol': currency_symbol(code)}


def quantize_money_decimal(value, iso4217: str) -> Decimal:
    """Offer/listing amounts: whole units for ILS, cents for others."""
    d = Decimal(str(value))
    if (iso4217 or 'ILS').upper() == 'ILS':
        return d.quantize(QUANT_ILS, rounding=ROUND_HALF_UP)
    return d.quantize(QUANT_MAJOR, rounding=ROUND_HALF_UP)


def money_amount_for_api(amount, iso4217: str):
    """JSON number: int shekels vs float with 2dp for other currencies."""
    d = quantize_money_decimal(amount, iso4217)
    if iso4217.upper() == 'ILS':
        return int(d)
    return float(d)


def iso4217_for_ticket_listing(ticket) -> str:
    ev = getattr(ticket, 'event', None)
    if ev is not None:
        return iso4217_for_country(getattr(ev, 'country', None))
    return 'ILS'
