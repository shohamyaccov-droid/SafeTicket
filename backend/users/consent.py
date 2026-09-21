"""Explicit marketing consent helpers (Israeli Communications Law / spam amendment)."""

from django.contrib.auth import get_user_model


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


def persist_user_marketing_opt_in(*, user=None, email=None):
    """Set agreed_to_marketing=True when the user explicitly opted in. Never clears True."""
    User = get_user_model()
    if user is not None and not getattr(user, 'agreed_to_marketing', False):
        user.agreed_to_marketing = True
        user.save(update_fields=['agreed_to_marketing', 'updated_at'])
        return
    cleaned = (email or '').strip()
    if cleaned:
        User.objects.filter(email__iexact=cleaned, agreed_to_marketing=False).update(
            agreed_to_marketing=True
        )
