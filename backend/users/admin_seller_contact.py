"""Admin-only seller contact helpers for pending-ticket review."""
from __future__ import annotations


def seller_contact_payload(seller) -> dict:
    """
    Build a safe contact dict for staff review UIs.

    Prefer profile phone_number; fall back to Bit payout phone when profile phone is empty.
    """
    if seller is None:
        return {
            'full_name': '',
            'email': '',
            'phone_number': '',
            'username': '',
            'id': None,
        }

    first = (getattr(seller, 'first_name', None) or '').strip()
    last = (getattr(seller, 'last_name', None) or '').strip()
    full_name = f'{first} {last}'.strip()
    username = (getattr(seller, 'username', None) or '').strip()
    if not full_name:
        full_name = username

    phone = (getattr(seller, 'phone_number', None) or '').strip()
    if not phone:
        phone = (getattr(seller, 'bit_phone_number', None) or '').strip()

    return {
        'id': getattr(seller, 'id', None),
        'full_name': full_name,
        'email': (getattr(seller, 'email', None) or '').strip(),
        'phone_number': phone,
        'username': username,
    }
