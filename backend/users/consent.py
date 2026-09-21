"""Explicit marketing consent helpers (Israeli Communications Law / spam amendment)."""

from django.contrib.auth import get_user_model
from django.utils import timezone


def is_explicit_marketing_opt_in(value) -> bool:
    """Only an affirmative, user-given value counts. Missing / unchecked => False."""
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'on')
    return False


def request_client_ip(request):
    """Best-effort client IP for consent audit. Invalid values return None."""
    if request is None:
        return None
    meta = getattr(request, 'META', None) or {}
    forwarded = (meta.get('HTTP_X_FORWARDED_FOR') or '').strip()
    raw = forwarded.split(',')[0].strip() if forwarded else (meta.get('REMOTE_ADDR') or '').strip()
    if not raw:
        return None
    try:
        import ipaddress

        ipaddress.ip_address(raw)
        return raw
    except ValueError:
        return None


def persist_user_marketing_opt_in(*, user=None, email=None, request=None):
    """Set agreed_to_marketing=True when the user explicitly opted in. Never clears True.

    First opt-in also stamps marketing_opt_in_at / marketing_opt_in_ip (legal proof).
    Existing timestamps are not overwritten.
    """
    User = get_user_model()
    now = timezone.now()
    ip = request_client_ip(request)

    if user is not None:
        updates = []
        if not getattr(user, 'agreed_to_marketing', False):
            user.agreed_to_marketing = True
            updates.append('agreed_to_marketing')
        if getattr(user, 'marketing_opt_in_at', None) is None:
            user.marketing_opt_in_at = now
            updates.append('marketing_opt_in_at')
        if ip and not getattr(user, 'marketing_opt_in_ip', None):
            user.marketing_opt_in_ip = ip
            updates.append('marketing_opt_in_ip')
        if updates:
            if 'updated_at' not in updates:
                updates.append('updated_at')
            user.save(update_fields=updates)
        return

    cleaned = (email or '').strip()
    if not cleaned:
        return
    qs = User.objects.filter(email__iexact=cleaned)
    for row in qs:
        persist_user_marketing_opt_in(user=row, request=request)
