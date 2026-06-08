"""
PayMe (paid.co.il) standard generate-sale integration.

Docs: https://docs.payme.io/
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

QUANT = Decimal('0.01')
DEFAULT_TIMEOUT_SECONDS = 45


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
) -> dict[str, Any]:
    """Build PayMe standard sale payload (no marketplace split)."""
    cfg = PayMeSettings.from_django()
    api_origin = getattr(settings, 'API_PUBLIC_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
    frontend = getattr(settings, 'FRONTEND_ORIGIN', 'http://localhost:5173').rstrip('/')
    order_id_str = str(order_id)

    body: dict[str, Any] = {
        'seller_payme_id': cfg.seller_id,
        'sale_price': money_to_agorot(amount),
        'currency': currency.upper(),
        'product_name': ticket_name[:255],
        'buyer_email': customer_email,
        'merchant_order_id': order_id_str,
        'sale_return_url': success_url or f'{frontend}/checkout/success?order_id={order_id_str}',
        'sale_cancel_url': failure_url or f'{frontend}/checkout/failure?order_id={order_id_str}',
        'sale_callback_url': callback_url or f'{api_origin}/api/payments/webhook/payme/',
    }

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

    body = build_standard_generate_sale_body(
        amount=amount,
        ticket_name=ticket_name,
        customer_email=customer_email,
        order_id=order_id,
        currency=currency,
        success_url=success_url,
        failure_url=failure_url,
        callback_url=callback_url,
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
) -> dict[str, Any]:
    """Create a PayMe hosted checkout session for a pending TradeTix order."""
    total = order.total_paid_by_buyer if order.total_paid_by_buyer is not None else order.total_amount
    if total is None:
        raise PayMeError('Order has no payable total')

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
    )
