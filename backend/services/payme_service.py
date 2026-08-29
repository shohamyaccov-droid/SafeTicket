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
from urllib.parse import urlsplit, urlunsplit

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
            or getattr(settings, 'PAYME_API_KEY', '')
            or ''
        ).strip()
        api_key = (
            getattr(settings, 'PAYME_API_KEY', '')
            or seller_id
            or ''
        ).strip()
        api_url = (getattr(settings, 'PAYME_API_URL', '') or '').strip().rstrip('/')
        generate_sale_url = (
            getattr(settings, 'PAYME_GENERATE_SALE_URL', '') or ''
        ).strip().rstrip('/')
        if not generate_sale_url and api_url:
            generate_sale_url = f'{api_url}/generate-sale'
        if not api_url and generate_sale_url.endswith('/generate-sale'):
            api_url = generate_sale_url[: -len('/generate-sale')].rstrip('/')
        if not api_url:
            api_url = 'https://testpay.payme.io/api' if getattr(settings, 'DEBUG', False) else ''
        return cls(
            seller_id=seller_id,
            api_url=api_url,
            generate_sale_url=generate_sale_url,
            webhook_secret=(getattr(settings, 'PAYME_WEBHOOK_SECRET', '') or '').strip(),
            api_key=api_key,
            api_secret=(
                getattr(settings, 'PAYME_API_PASSWORD', '')
                or getattr(settings, 'PAYME_API_SECRET', '')
                or ''
            ).strip(),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.seller_id or self.api_key)

    @property
    def lookup_api_url(self) -> str:
        """API root for get-transactions (same host as generate-sale)."""
        if self.api_url:
            return self.api_url.rstrip('/')
        gen = (self.generate_sale_url or '').rstrip('/')
        if gen.endswith('/generate-sale'):
            return gen[: -len('/generate-sale')].rstrip('/')
        return ''

    def lookup_endpoint_url(self, endpoint: str) -> str:
        """
        Absolute URL for PayMe ``get-transactions``.

        Rewrites ``PAYME_GENERATE_SALE_URL`` (…/generate-sale → …/get-transactions)
        when set; otherwise uses ``PAYME_API_URL``.
        """
        return build_payme_query_url(
            endpoint,
            api_url=self.api_url,
            generate_sale_url=self.generate_sale_url,
        )


def build_payme_query_url(
    endpoint: str,
    *,
    api_url: str = '',
    generate_sale_url: str = '',
) -> str:
    """
    Build ``…/api/get-transactions`` from env URLs.

    Prefer rewriting generate-sale so preprod/live hosts match checkout::

      https://preprod.paymeservice.com/api/generate-sale
      → https://preprod.paymeservice.com/api/get-transactions
    """
    name = (endpoint or '').strip().lstrip('/')
    if not name:
        raise ValueError('PayMe query endpoint name is required')

    # Prefer GENERATE_SALE_URL (PayMe support / checkout host), then API root.
    for candidate in ((generate_sale_url or '').strip(), (api_url or '').strip()):
        if not candidate:
            continue
        parts = urlsplit(candidate)
        if not parts.scheme or not parts.netloc:
            continue
        path = (parts.path or '').rstrip('/')
        segments = [seg for seg in path.split('/') if seg]
        if segments and segments[-1] in (
            'generate-sale',
            'get-sales',
            'get-transactions',
            'generate-request',
        ):
            segments = segments[:-1]
        segments.append(name)
        new_path = '/' + '/'.join(segments)
        return urlunsplit((parts.scheme, parts.netloc, new_path, '', ''))

    return f'/{name}'


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


def fallback_buyer_name_from_email(email: str) -> str:
    """PayMe still wants a buyer_name; use the email local-part when legal name is optional."""
    local = (email or '').split('@')[0].strip()
    return local[:100] if local else ''


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
                uname = (getattr(user, 'username', None) or '').strip()
                if uname and not _looks_like_email(uname):
                    full = uname
                    first, last = split_buyer_name(full)
                else:
                    full = fallback_buyer_name_from_email(getattr(user, 'email', None) or uname)
                    if full and not first:
                        first = full
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
    if not full:
        full = fallback_buyer_name_from_email(getattr(order, 'guest_email', None) or '')
        if full and not first:
            first = full
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


def _json_headers() -> dict[str, str]:
    return {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def _request_headers(cfg: PayMeSettings) -> dict[str, str]:
    headers = _json_headers()
    if cfg.seller_id:
        headers['X-Payme-Merchant-Id'] = cfg.seller_id
    if cfg.api_key:
        headers['X-Api-Key'] = cfg.api_key
        headers['Authorization'] = f'Bearer {cfg.api_key}'
    return headers


def _lookup_headers() -> dict[str, str]:
    """PayMe query docs authenticate via JSON body, not Bearer."""
    return _json_headers()


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


CONFIRM_TIMEOUT_SECONDS = 30
_LOOKUP_BODY_LOG_MAX = 1800


def _empty_confirm_result(*, error: str, raw: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'ok': False,
        'found': False,
        'status': None,
        'raw': raw,
        'error': error,
        'http_status': None,
        'url': None,
        'response_text': None,
    }


def confirm_payme_sale_status(
    *,
    payme_sale_id: str | None = None,
    payme_transaction_id: str | None = None,
) -> dict[str, Any]:
    """
    Authoritative PayMe status lookup for a standard Seller account.

    Empirically verified against live PayMe (Aug 2026):

    - Auth must be ``seller_payme_id`` = MPL seller id only.
    - Sending the MPL as ``payme_client_key`` returns HTTP 500
      ``שירות לא נמצא`` (status_additional_info=payme_client_key).
    - Primary: ``POST …/api/get-sales`` with ``sale_payme_id`` (webhook payme_sale_id).
    - Fallback: ``POST …/api/get-transactions`` with ``payme_transaction_id``.
    """
    cfg = PayMeSettings.from_django()
    seller_id = (cfg.seller_id or cfg.api_key or '').strip()
    if not seller_id:
        logger.critical(
            'PayMe webhook verification aborted: PAYME_API_KEY / PAYME_SELLER_ID is not loaded'
        )
        return _empty_confirm_result(error='missing_api_key')

    sale_id = (payme_sale_id or '').strip()
    txn_id = (payme_transaction_id or '').strip()
    if not sale_id and not txn_id:
        return _empty_confirm_result(error='missing_ids')

    probe_url = cfg.lookup_endpoint_url('get-sales')
    if not probe_url.startswith('http'):
        logger.critical(
            'PayMe webhook verification aborted: cannot build lookup URL '
            '(set PAYME_GENERATE_SALE_URL or PAYME_API_URL to live.payme.io)'
        )
        return _empty_confirm_result(error='missing_api_url')

    wanted = {value for value in (sale_id, txn_id) if value}
    attempts: list[dict[str, Any]] = []

    def _try(result: dict[str, Any]) -> dict[str, Any] | None:
        attempts.append(
            {
                'ok': result.get('ok'),
                'found': result.get('found'),
                'error': result.get('error'),
                'http_status': result.get('http_status'),
                'url': result.get('url'),
                'response_text': (result.get('response_text') or '')[:400],
            }
        )
        if result.get('found'):
            return result
        return None

    if sale_id:
        hit = _try(
            _query_payme_endpoint(
                cfg,
                path='get-sales',
                api_key=seller_id,
                payme_sale_id=sale_id,
                wanted=wanted,
            )
        )
        if hit:
            return hit

    if txn_id:
        hit = _try(
            _query_payme_endpoint(
                cfg,
                path='get-transactions',
                api_key=seller_id,
                payme_transaction_id=txn_id,
                wanted=wanted,
            )
        )
        if hit:
            return hit

    last = attempts[-1] if attempts else {}
    transport_failed = all(not a.get('ok') for a in attempts) if attempts else True
    logger.error(
        'PayMe lookup failed sale_id=%s txn_id=%s attempts=%s',
        sale_id,
        txn_id,
        attempts,
    )
    if transport_failed:
        return {
            'ok': False,
            'found': False,
            'status': None,
            'raw': None,
            'error': last.get('error') or 'payme_lookup_failed',
            'http_status': last.get('http_status'),
            'url': last.get('url'),
            'response_text': last.get('response_text'),
            'attempts': attempts,
        }
    return {
        'ok': True,
        'found': False,
        'status': None,
        'raw': None,
        'error': 'payme_sale_not_found',
        'http_status': last.get('http_status'),
        'url': last.get('url'),
        'response_text': last.get('response_text'),
        'attempts': attempts,
    }


def _payme_lookup_body(
    api_key: str,
    *,
    payme_sale_id: str | None = None,
    payme_transaction_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Seller-account lookup body.

    Never send ``payme_client_key`` with the MPL seller id — PayMe treats that as a
    Partner key and returns ``שירות לא נמצא``. Use ``seller_payme_id`` only.
    Filter fields must be exact: ``sale_payme_id`` / ``payme_transaction_id``.
    """
    body: dict[str, Any] = {
        'seller_payme_id': api_key,
    }
    sale = (payme_sale_id or '').strip()
    txn = (payme_transaction_id or '').strip()
    if sale:
        # Official get-sales filter name. Do NOT send payme_sale_id here — PayMe
        # ignores it and may return an unfiltered list.
        body['sale_payme_id'] = sale
    if txn:
        body['payme_transaction_id'] = txn
    if extra:
        for key, value in extra.items():
            if value not in (None, ''):
                body[key] = value
    return body


def _post_payme_lookup(cfg: PayMeSettings, path: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST get-sales or get-transactions. Always logs HTTP status and response text."""
    endpoint = path.lstrip('/')
    if endpoint not in ('get-sales', 'get-transactions'):
        logger.error('PayMe refused unknown lookup path=%s', endpoint)
        return {
            'ok': False,
            'data': None,
            'error': f'unsupported_lookup_path:{endpoint}',
            'http_status': None,
            'url': None,
            'response_text': None,
        }
    url = cfg.lookup_endpoint_url(endpoint)
    safe_keys = sorted(k for k in body.keys() if k not in ('payme_client_key', 'seller_payme_id'))
    try:
        response = requests.post(
            url,
            json=body,
            headers=_lookup_headers(),
            timeout=CONFIRM_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        logger.error('PayMe %s timeout url=%s keys=%s error=%s', path, url, safe_keys, exc)
        return {
            'ok': False,
            'data': None,
            'error': 'timeout',
            'http_status': None,
            'url': url,
            'response_text': str(exc),
        }
    except requests.RequestException as exc:
        logger.error('PayMe %s network error url=%s keys=%s error=%s', path, url, safe_keys, exc)
        return {
            'ok': False,
            'data': None,
            'error': f'network:{exc}',
            'http_status': None,
            'url': url,
            'response_text': str(exc),
        }

    raw_text = str(getattr(response, 'text', None) or '')[:_LOOKUP_BODY_LOG_MAX]
    logger.info(
        'PayMe %s response url=%s http=%s keys=%s body=%s',
        path,
        url,
        response.status_code,
        safe_keys,
        raw_text,
    )

    data: Any = None
    try:
        data = response.json()
    except ValueError:
        logger.error(
            'PayMe %s non-JSON url=%s http=%s body=%s',
            path,
            url,
            response.status_code,
            raw_text,
        )
        return {
            'ok': False,
            'data': None,
            'error': f'invalid_json_http_{response.status_code}',
            'http_status': response.status_code,
            'url': url,
            'response_text': raw_text,
        }

    if response.status_code >= 400:
        err = None
        if isinstance(data, dict):
            err = (
                data.get('status_error_details')
                or data.get('status_error_code')
                or data.get('error')
                or data.get('message')
            )
        logger.error(
            'PayMe %s HTTP %s url=%s error=%s body=%s',
            path,
            response.status_code,
            url,
            err or response.status_code,
            raw_text,
        )
        return {
            'ok': False,
            'data': data if isinstance(data, dict) else None,
            'error': str(err or f'http_{response.status_code}'),
            'http_status': response.status_code,
            'url': url,
            'response_text': raw_text,
        }

    if not isinstance(data, dict):
        return {
            'ok': False,
            'data': None,
            'error': 'invalid_response',
            'http_status': response.status_code,
            'url': url,
            'response_text': raw_text,
        }

    return {
        'ok': True,
        'data': data,
        'error': None,
        'http_status': response.status_code,
        'url': url,
        'response_text': raw_text,
    }


def _extract_payme_lookup_items(data: dict[str, Any]) -> list[Any]:
    items = data.get('items')
    if isinstance(items, list):
        return items
    nested = data.get('data') or data.get('result') or data.get('sale')
    if isinstance(nested, list):
        return nested
    if isinstance(nested, dict):
        nested_items = nested.get('items')
        if isinstance(nested_items, list):
            return nested_items
        if _looks_like_payme_sale(nested):
            return [nested]
    if _looks_like_payme_sale(data):
        return [data]
    return []


def _looks_like_payme_sale(item: dict[str, Any]) -> bool:
    return any(
        item.get(key)
        for key in (
            'sale_payme_id',
            'payme_sale_id',
            'sale_status',
            'payme_sale_status',
            'transaction_id',
            'payme_transaction_id',
            'transaction_status',
        )
    )


def _payme_item_ids(item: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in (
        'sale_payme_id',
        'payme_sale_id',
        'transaction_id',
        'payme_transaction_id',
        'id',
    ):
        value = str(item.get(key) or '').strip()
        if value:
            ids.add(value)
    return ids


def _find_matching_payme_item(items: list[Any], wanted: set[str]) -> dict[str, Any] | None:
    if not wanted:
        return None
    for item in items:
        if isinstance(item, dict) and (_payme_item_ids(item) & wanted):
            return item
    if len(items) == 1 and isinstance(items[0], dict) and _looks_like_payme_sale(items[0]):
        return items[0]
    return None


def _status_from_payme_item(item: dict[str, Any]) -> str | None:
    raw_status = (
        item.get('sale_status')
        or item.get('payme_sale_status')
        or item.get('transaction_status')
        or item.get('payme_transaction_status')
        or item.get('status')
        or ''
    )
    return _normalize_payme_api_status(raw_status)


def _meta_from_post(posted: dict[str, Any]) -> dict[str, Any]:
    return {
        'http_status': posted.get('http_status'),
        'url': posted.get('url'),
        'response_text': posted.get('response_text'),
    }


def _query_payme_endpoint(
    cfg: PayMeSettings,
    *,
    path: str,
    api_key: str,
    wanted: set[str],
    payme_sale_id: str | None = None,
    payme_transaction_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = _payme_lookup_body(
        api_key,
        payme_sale_id=payme_sale_id,
        payme_transaction_id=payme_transaction_id,
        extra=extra,
    )
    posted = _post_payme_lookup(cfg, path, body)
    meta = _meta_from_post(posted)
    if not posted['ok']:
        return {
            'ok': False,
            'found': False,
            'status': None,
            'raw': posted.get('data'),
            'error': posted.get('error'),
            **meta,
        }
    data = posted['data'] or {}
    if data.get('status_code') not in (None, 0):
        details = data.get('status_error_details') or data.get('error') or data.get('status_code')
        logger.error(
            'PayMe %s status_code=%s sale_id=%s details=%s body=%s',
            path,
            data.get('status_code'),
            payme_sale_id,
            details,
            meta.get('response_text'),
        )
        return {
            'ok': False,
            'found': False,
            'status': None,
            'raw': data,
            'error': str(details or 'payme_status_code'),
            **meta,
        }
    match = _find_matching_payme_item(_extract_payme_lookup_items(data), wanted)
    if match is None:
        return {
            'ok': True,
            'found': False,
            'status': None,
            'raw': data,
            'error': None,
            **meta,
        }
    return {
        'ok': True,
        'found': True,
        'status': _status_from_payme_item(match),
        'raw': match,
        'error': None,
        **meta,
    }


def _normalize_payme_api_status(raw: Any) -> str | None:
    """Lightweight status normalize for get-transactions responses."""
    s = str(raw or '').strip().lower().replace('_', '').replace('-', '').replace(' ', '')
    if not s:
        return None
    if s in (
        '0',
        '00',
        'success',
        'succeeded',
        'completed',
        'complete',
        'paid',
        'captured',
        'validated',
        'sale',
        'sold',
        'ok',
        'מכירה',
    ):
        return 'success'
    if s in (
        'authorized',
        'authorised',
        'authorization',
        'authorisation',
        'auth',
        'preauth',
        'hold',
        'תפיסתמסגרת',
    ):
        return 'authorized'
    if any(tok in s for tok in ('fail', 'declin', 'error', 'cancel', 'void', 'reject')):
        return 'failed'
    return 'pending'


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
