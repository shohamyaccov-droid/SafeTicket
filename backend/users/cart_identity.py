"""Anonymous cart identity for locking tickets before a guest types an email."""
import re

from django.db.models import Q

CART_TOKEN_EMAIL_DOMAIN = 'cart.tradetix.invalid'
_CART_TOKEN_HEX_RE = re.compile(r'^[0-9a-f]{16,64}$')


def normalize_cart_token(raw) -> str:
    token = re.sub(r'[^0-9a-f]', '', str(raw or '').strip().lower())
    if not _CART_TOKEN_HEX_RE.match(token):
        return ''
    return token


def cart_token_email(cart_token: str) -> str:
    token = normalize_cart_token(cart_token)
    if not token:
        return ''
    return f'{token}@{CART_TOKEN_EMAIL_DOMAIN}'


def is_cart_token_email(email: str) -> bool:
    value = (email or '').strip().lower()
    return bool(value) and value.endswith(f'@{CART_TOKEN_EMAIL_DOMAIN}')


def anonymous_identity_emails(*, guest_email: str = '', cart_token: str = '') -> list[str]:
    emails = []
    ge = (guest_email or '').strip().lower()
    if ge:
        emails.append(ge)
    token_email = cart_token_email(cart_token)
    if token_email and token_email not in emails:
        emails.append(token_email)
    return emails


def stored_anonymous_reservation_email(*, guest_email: str = '', cart_token: str = '') -> str:
    """Prefer a real buyer email; fall back to the synthetic cart-token address."""
    ge = (guest_email or '').strip().lower()
    if ge and not is_cart_token_email(ge):
        return ge
    return cart_token_email(cart_token) or ge


def anonymous_reservation_matches(
    reservation_email: str,
    *,
    guest_email: str = '',
    cart_token: str = '',
) -> bool:
    held = (reservation_email or '').strip().lower()
    if not held:
        return False
    return held in set(anonymous_identity_emails(guest_email=guest_email, cart_token=cart_token))


def anonymous_reservation_email_q(*, guest_email: str = '', cart_token: str = '') -> Q:
    emails = anonymous_identity_emails(guest_email=guest_email, cart_token=cart_token)
    if not emails:
        return Q(pk__in=[])
    query = Q()
    for email in emails:
        query |= Q(reservation_email__iexact=email)
    return query
