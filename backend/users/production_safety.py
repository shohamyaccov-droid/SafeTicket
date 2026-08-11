"""
Production safety rails: block catalog/order wipe operations outside local DEBUG.

Locked when RENDER=true, or when DEBUG=False outside the test runner.
There is no env override — production must never run destructive flush/prune/wipe paths.
"""
from __future__ import annotations

import os
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _running_tests() -> bool:
    if getattr(settings, 'TESTING', False):
        return True
    # manage.py test / pytest without an explicit TESTING setting
    argv0 = ' '.join(sys.argv).lower()
    return ('manage.py' in argv0 and ' test' in f' {argv0}') or 'pytest' in argv0


def is_production_locked() -> bool:
    """
    Return True when destructive DB ops (wipe/prune/flush/mass-delete) must not run.

    - RENDER=true → always locked (Render web / workers / shell against prod).
    - DEBUG=False → locked (any non-debug deploy), except the Django/pytest test runner
      (tests force DEBUG=False but must still exercise wipe helpers locally).
    """
    if (os.environ.get('RENDER') or '').strip().lower() == 'true':
        return True
    if _running_tests():
        return False
    return not bool(getattr(settings, 'DEBUG', False))


def refuse_destructive(operation: str) -> None:
    """Raise if destructive ops are locked. Call at the top of every wipe/prune path."""
    if not is_production_locked():
        return
    raise ImproperlyConfigured(
        f'Refused destructive operation {operation!r}: production safety lock is active '
        f'(RENDER={os.environ.get("RENDER")!r}, DEBUG={getattr(settings, "DEBUG", None)!r}). '
        'These commands can only run locally with DEBUG=True and RENDER unset.'
    )


def destructive_ops_allowed() -> bool:
    """Inverse of is_production_locked — for callers that prefer a boolean."""
    return not is_production_locked()
