#!/usr/bin/env python3
"""
Promote a Django user to staff + superuser (TradeTix admin dashboard + Django admin).

Usage (from the backend directory, with DB configured):
    python make_admin.py YOUR_USERNAME

Equivalent:
    python manage.py promote_user YOUR_USERNAME

Requires DATABASE_URL (production) or local DB settings in safeticket.settings.
"""
from __future__ import annotations

import os
import sys

# backend/ as cwd — project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: python make_admin.py <username>')
        print('Also: python manage.py promote_user <username>')
        return 1
    username = sys.argv[1].strip()
    user = User.objects.filter(username=username).first()
    if not user:
        print(f'[ERROR] No user with username={username!r}')
        return 1
    user.is_staff = True
    user.is_superuser = True
    user.save(update_fields=['is_staff', 'is_superuser'])
    print(f'[OK] {username} is now is_staff=True and is_superuser=True.')
    print('Log in again (or refresh profile) to see /admin-panel and ניהול in the navbar.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
