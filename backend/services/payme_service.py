"""
PayMe (paid.co.il) standard generate-sale integration.

Docs: https://docs.payme.io/
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

QUANT = Decimal('0.01')
DEFAULT_TIMEOUT_SECONDS = 45
_PAYME_SANDBOX_HOSTS = ('testpay.payme.io', 'preprod.paymeservice.com', 'sandbox.payme.io')


class PayMeError(Exception):
    """Raised when PayMe API configuration, transport, or response is invalid."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        payload: Any = None,
    ):
        super().__init__(message)
        self.http_status = http_status
        self.payload = payload


@dataclass(frozen=True)
class PayMeSettings:
    seller_id: str
    api_url: str
    generate_sale_url: str
    webhook_secret: str
    api_key: str
    api_secret: str

    @classmethod
    def from_django(cls) -> PayMeSettings:
        seller_id = (
            getattr(settings, 'PAYME_SELLER_ID', '')
            or getattr(settings, 'PAYME_MERCHANT_ID', '')
            or ''
        ).strip()
        api_url = getattr(settings, 'PAYME_API_URL', 'https://testpay.payme.io/api').strip().rstrip('/')
        generate_sale_url = (
            getattr(settings, 'PAYME_GENERATE_SALE_URL', '') or f'{api_url}/generate-sale'
        ).strip()
        return cls(
            seller_id=seller_id,
            api_url=api_url,
            generate_sale_url=generate_sale_url,
            webhook_secret=(getattr(settings, 'PAYME_WEBHOOK_SECRET', '') or '').strip(),
            api_key=(getattr(settings, 'PAYME_API_KEY', '') or '').strip(),
            api_secret=(getattr(settings, 'PAYME_API_SECRET', '') or '').strip(),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.seller_id or self.api_key)


def money_to_agorot(amount: Decimal | str | float | int) -> int:
    """PayMe expects minor currency units (agorot for ILS)."""
    value = Decimal(str(amount)).quantize(QUANT, rounding=ROUND_HALF_UP)
    return int(value * 100)


def is_payme_sandbox() -> bool:
    """True when PayMe is in sandbox/preprod mode (settings flag or API host)."""
    if getattr(settings, 'PAYME_IS_SANDBOX', False):
        return True
    api_url = (getattr(settings, 'PAYME_API_URL', '') or '').lower()
    return any(host in api_url for host in _PAYME_SANDBOX_HOSTS)


def get_payme_sandbox_account_email() -> str:
    """PayMe sandbox merchant dashboard account (distinct from production)."""
    return (getattr(settings, 'PAYME_SANDBOX_ACCOUNT_EMAIL', '') or 'tradetix.support+1@gmail.com').strip().lower()


def resolve_payme_customer_email(customer_email: str) -> str:
    """
    Map buyer email for PayMe generate-sale.

    In sandbox, always use PAYME_SANDBOX_ACCOUNT_EMAIL so dev/test checkouts never
    collide with the production PayMe merchant identity.
    """
    if is_payme_sandbox():
        sandbox_email = get_payme_sandbox_account_email()
        if sandbox_email:
            return sandbox_email
    return (customer_email or '').strip()


def extract_payme_sale_url(response_data: Any) -> str | None:
    """Extract hosted checkout URL from PayMe generate-sale response."""
    if not isinstance(response_data, dict):
        return None
    for key in (
        'payme_sale_url',
        'sale_url',
        'redirect_url',
        'payment_url',
        'payme_url',
        'checkout_url',
        'hosted_page_url',
        'url',
    ):
        value = response_data.get(key)
        if isinstance(value, str) and value.startswith('http'):
            return value
    nested = response_data.get('data') or response_data.get('result')
    if isinstance(nested, dict):
        return extract_payme_sale_url(nested)
    return None


def extract_transaction_id(response_data: Any) -> str | None:
    if not isinstance(response_data, dict):
        return None
    for key in (
        'transaction_id',
        'transactionId',
        'payme_transaction_id',
        'payme_sale_id',
        'sale_id',
        'id',
    ):
        value = response_data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    nested = response_data.get('data') or response_data.get('result')
    if isinstance(nested, dict):
        return extract_transaction_id(nested)
    return None


def normalize_payme_buyer_phone(raw: str | None) -> str:
    """
    PayMe docs / Bit hosted checkout expect Israeli local mobiles (05xxxxxxxx).
    International 972… is accepted as input and converted to local form.
    """
    digits = re.sub(r'\D', '', str(raw or ''))
    if not digits:
        return ''
    if digits.startswith('972'):
        national = digits[3:]
        if not national:
            return ''
        return national if national.startswith('0') else f'0{national}'
    if digits.startswith('0'):
        return digits
    # Bare 9-digit Israeli mobile (5xxxxxxxx)
    if len(digits) == 9 and digits.startswith('5'):
        return f'0{digits}'
    return digits


def split_buyer_name(full_name: str | None) -> tuple[str, str]:
    """Split a full name into (first_name, last_name) for PayMe prefill."""
    parts = (full_name or '').strip().split(None, 1)
    if not parts:
        return '', ''
    if len(parts) == 1:
        return parts[0][:100], ''
    return parts[0][:100], parts[1][:100]


def append_payme_sale_url_prefill(
    sale_url: str,
    *,
    first_name: str = '',
    last_name: str = '',
    phone: str = '',
    email: str = '',
) -> str:
    """
    PayMe hosted payment page prefill is done via query params on sale_url:
    first_name, last_name, phone, email (Apiary / Payment Page docs).
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    url = (sale_url or '').strip()
    if not url:
        return url

    params: dict[str, str] = {}
    fn = (first_name or '').strip()
    ln = (last_name or '').strip()
    ph = normalize_payme_buyer_phone(phone)
    em = (email or '').strip()
    if fn:
        params['first_name'] = fn[:100]
    if ln:
        params['last_name'] = ln[:100]
    if ph:
        params['phone'] = ph
    if em:
        params['email'] = em[:255]
    if not params:
        return url

    parts = urlsplit(url)
    existing = dict(parse_qsl(parts.query, keep_blank_values=True))
    # Prefill keys should win over any empty placeholders already on the URL.
    existing.update(params)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(existing), parts.fragment)
    )


def _looks_like_email(value: str) -> bool:
    return '@' in (value or '')


def resolve_buyer_details_for_order(order) -> dict[str, str]:
    """Buyer identity for PayMe generate-sale + hosted page prefill (Bit / cards)."""
    if getattr(order, 'user_id', None):
        user = getattr(order, 'user', None)
        if user is None:
            from django.contrib.auth import get_user_model

            user = get_user_model().objects.filter(pk=order.user_id).first()
        if user is not None:
            # Always re-read identity fields so dashboard checkout sees latest profile edits.
            try:
                user.refresh_from_db(
                    fields=['first_name', 'last_name', 'email', 'phone_number', 'bit_phone_number', 'username']
                )
            except Exception:
                pass
            first = (getattr(user, 'first_name', None) or '').strip()
            last = (getattr(user, 'last_name', None) or '').strip()
            full = f'{first} {last}'.strip()
            if not full:
                # Do not treat email-like usernames as a legal buyer name for PayMe.
                uname = (getattr(user, 'username', None) or '').strip()
                if uname and not _looks_like_email(uname):
                    full = uname
                    first, last = split_buyer_name(full)
            phone_raw = (
                getattr(user, 'phone_number', None)
                or getattr(user, 'bit_phone_number', None)
                or ''
            )
            phone = normalize_payme_buyer_phone(phone_raw)
            return {
                'buyer_first_name': first,
                'buyer_last_name': last,
                'buyer_name': full,
                'buyer_full_name': full,
                'buyer_email': (getattr(user, 'email', None) or '').strip(),
                'buyer_phone': phone,
                'buyer_phone_number': phone,
            }
    first = (getattr(order, 'guest_first_name', None) or '').strip()
    last = (getattr(order, 'guest_last_name', None) or '').strip()
    full = f'{first} {last}'.strip()
    phone = normalize_payme_buyer_phone(getattr(order, 'guest_phone', None))
    return {
        'buyer_first_name': first,
        'buyer_last_name': last,
        'buyer_name': full,
        'buyer_full_name': full,
        'buyer_email': (getattr(order, 'guest_email', None) or '').strip(),
        'buyer_phone': phone,
        'buyer_phone_number': phone,
    }


def build_standard_generate_sale_body(
    *,
    amount: Decimal | str | float | int,
    ticket_name: str,
    customer_email: str,
    order_id: str,
    currency: str = 'ILS',
    success_url: str | None = None,
    failure_url: str | None = None,
    callback_url: str | None = None,
    buyer_name: str | None = None,
    buyer_phone: str | None = None,
    buyer_first_name: str | None = None,
    buyer_last_name: str | None = None,
) -> dict[str, Any]:
    """Build PayMe standard sale payload (no marketplace split)."""
    cfg = PayMeSettings.from_django()
    api_origin = getattr(settings, 'API_PUBLIC_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
    frontend = getattr(settings, 'FRONTEND_ORIGIN', 'http://localhost:5173').rstrip('/')
    order_id_str = str(order_id)

    payme_buyer_email = resolve_payme_customer_email(customer_email)

    body: dict[str, Any] = {
        'seller_payme_id': cfg.seller_id,
        'sale_price': money_to_agorot(amount),
        'currency': currency.upper(),
        'product_name': ticket_name[:255],
        'buyer_email': payme_buyer_email,
        'merchant_order_id': order_id_str,
        'sale_return_url': success_url or f'{frontend}/checkout/success?order_id={order_id_str}',
        'sale_cancel_url': failure_url or f'{frontend}/checkout/failure?order_id={order_id_str}',
        'sale_callback_url': callback_url or f'{api_origin}/api/payments/webhook/payme/',
        # multi = cards + Bit (+ other APMs enabled on the merchant account)
        'sale_payment_method': 'multi',
        # ILS required for Bit; keep explicit for APM routing.
        'language': 'he',
    }

    payme_buyer_name = (buyer_name or '').strip()
    first = (buyer_first_name or '').strip()
    last = (buyer_last_name or '').strip()
    if not first and not last and payme_buyer_name:
        first, last = split_buyer_name(payme_buyer_name)
    if not payme_buyer_name and (first or last):
        payme_buyer_name = f'{first} {last}'.strip()

    payme_buyer_phone = normalize_payme_buyer_phone(buyer_phone)
    if payme_buyer_name:
        # Canonical PayMe keys + aliases used by some hosted/Bit payloads.
        body['buyer_name'] = payme_buyer_name[:255]
        body['buyer_full_name'] = payme_buyer_name[:255]
    if first:
        body['buyer_first_name'] = first[:100]
        body['first_name'] = first[:100]
    if last:
        body['buyer_last_name'] = last[:100]
        body['last_name'] = last[:100]
    if payme_buyer_phone:
        # Local IL format (05…) — Bit rejects / fails (e.g. 420) with bare international in some flows.
        body['buyer_phone'] = payme_buyer_phone
        body['buyer_phone_number'] = payme_buyer_phone
        body['phone'] = payme_buyer_phone

    extra = getattr(settings, 'PAYME_EXTRA_BODY_JSON', None) or {}
    if isinstance(extra, dict) and extra:
        body = {**body, **extra}
    return body


def _request_headers(cfg: PayMeSettings) -> dict[str, str]:
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if cfg.seller_id:
        headers['X-Payme-Merchant-Id'] = cfg.seller_id
    if cfg.api_key:
        headers['X-Api-Key'] = cfg.api_key
        headers['Authorization'] = f'Bearer {cfg.api_key}'
    return headers


def generate_payme_sale(
    amount: float | Decimal | str | int,
    ticket_name: str,
    customer_email: str,
    order_id: str,
    *,
    currency: str = 'ILS',
    success_url: str | None = None,
    failure_url: str | None = None,
    callback_url: str | None = None,
    buyer_name: str | None = None,
    buyer_phone: str | None = None,
    buyer_first_name: str | None = None,
    buyer_last_name: str | None = None,
) -> dict[str, Any]:
    """
    Call PayMe POST /generate-sale (standard sale flow).

    Returns:
        {
            "payme_sale_url": str,
            "transaction_id": str | None,
            "payme_sale_id": str | None,
            "raw": dict,
        }

    Raises:
        PayMeError: configuration, network, or API-level failure.
    """
    cfg = PayMeSettings.from_django()
    if not cfg.seller_id:
        raise PayMeError('PAYME_SELLER_ID is not configured')

    first = (buyer_first_name or '').strip()
    last = (buyer_last_name or '').strip()
    if not first and not last:
        first, last = split_buyer_name(buyer_name)

    body = build_standard_generate_sale_body(
        amount=amount,
        ticket_name=ticket_name,
        customer_email=customer_email,
        order_id=order_id,
        currency=currency,
        success_url=success_url,
        failure_url=failure_url,
        callback_url=callback_url,
        buyer_name=buyer_name,
        buyer_phone=buyer_phone,
        buyer_first_name=first,
        buyer_last_name=last,
    )

    logger.info(
        'PayMe generate-sale request order_id=%s amount=%s currency=%s',
        order_id,
        amount,
        currency,
    )

    try:
        response = requests.post(
            cfg.generate_sale_url,
            json=body,
            headers=_request_headers(cfg),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        logger.exception('PayMe generate-sale timeout order_id=%s', order_id)
        raise PayMeError('PayMe request timed out') from exc
    except requests.RequestException as exc:
        logger.exception('PayMe generate-sale network error order_id=%s', order_id)
        raise PayMeError(f'PayMe network error: {exc}') from exc

    try:
        data = response.json()
    except ValueError:
        raise PayMeError(
            'PayMe returned non-JSON response',
            http_status=response.status_code,
            payload={'raw': response.text[:500]},
        )

    status_code = data.get('status_code')
    logger.info(
        'PayMe generate-sale response order_id=%s http=%s status_code=%s',
        order_id,
        response.status_code,
        status_code,
    )

    if response.status_code >= 400:
        raise PayMeError(
            data.get('status_error_details') or data.get('error') or 'PayMe HTTP error',
            http_status=response.status_code,
            payload=data,
        )

    if status_code is not None and status_code != 0:
        raise PayMeError(
            data.get('status_error_details') or data.get('error') or 'PayMe generate-sale failed',
            http_status=response.status_code,
            payload=data,
        )

    payme_sale_url = extract_payme_sale_url(data)
    if not payme_sale_url:
        raise PayMeError(
            'PayMe response missing payme_sale_url',
            http_status=response.status_code,
            payload=data,
        )

    payme_sale_url = append_payme_sale_url_prefill(
        payme_sale_url,
        first_name=first or body.get('first_name', ''),
        last_name=last or body.get('last_name', ''),
        phone=body.get('buyer_phone') or buyer_phone or '',
        email=body.get('buyer_email') or customer_email or '',
    )

    transaction_id = extract_transaction_id(data)
    return {
        'payme_sale_url': payme_sale_url,
        'transaction_id': transaction_id,
        'payme_sale_id': data.get('payme_sale_id') or data.get('sale_id'),
        'raw': data,
    }


def generate_payme_sale_for_order(
    order,
    *,
    buyer_email: str,
    success_url: str,
    failure_url: str,
    buyer_name: str | None = None,
    buyer_phone: str | None = None,
    buyer_first_name: str | None = None,
    buyer_last_name: str | None = None,
) -> dict[str, Any]:
    """Create a PayMe hosted checkout session for a pending TradeTix order."""
    total = order.total_paid_by_buyer if order.total_paid_by_buyer is not None else order.total_amount
    if total is None:
        raise PayMeError('Order has no payable total')

    resolved = resolve_buyer_details_for_order(order)
    if not buyer_name or not buyer_phone or not buyer_first_name:
        buyer_name = buyer_name or resolved.get('buyer_name') or None
        buyer_phone = buyer_phone or resolved.get('buyer_phone') or None
        buyer_first_name = buyer_first_name or resolved.get('buyer_first_name') or None
        buyer_last_name = buyer_last_name or resolved.get('buyer_last_name') or None
    if not buyer_first_name and not buyer_last_name and buyer_name:
        buyer_first_name, buyer_last_name = split_buyer_name(buyer_name)

    ticket_name = f'TradeTix — {order.event_name or "Ticket"}'
    if order.quantity and int(order.quantity) > 1:
        ticket_name = f'{ticket_name} (×{order.quantity})'

    return generate_payme_sale(
        amount=total,
        ticket_name=ticket_name,
        customer_email=buyer_email,
        order_id=str(order.id),
        currency=order.currency or 'ILS',
        success_url=success_url,
        failure_url=failure_url,
        buyer_name=buyer_name,
        buyer_phone=buyer_phone,
        buyer_first_name=buyer_first_name,
        buyer_last_name=buyer_last_name,
    )


# Alias for docs / external integrations
create_payme_sale = generate_payme_sale
