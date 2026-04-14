"""
Time-limited signed tokens for ticket file download (email links).
Anonymous users must present a valid `dl=` token; raw `?email=` is not accepted.
"""
from __future__ import annotations

from django.core import signing

_DOWNLOAD_SALT = 'safeticket.ticket_pdf_dl.v1'
_MAX_AGE_SECONDS = 60 * 60 * 24 * 90  # 90 days


def build_ticket_download_token(ticket_id: int, order_id: int) -> str:
    payload = {'t': int(ticket_id), 'o': int(order_id)}
    return signing.dumps(payload, salt=_DOWNLOAD_SALT)


def verify_ticket_download_token(token: str) -> dict | None:
    if not token or not str(token).strip():
        return None
    try:
        data = signing.loads(
            str(token).strip(),
            salt=_DOWNLOAD_SALT,
            max_age=_MAX_AGE_SECONDS,
        )
        if not isinstance(data, dict):
            return None
        if 't' not in data or 'o' not in data:
            return None
        return {'t': int(data['t']), 'o': int(data['o'])}
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
        return None
