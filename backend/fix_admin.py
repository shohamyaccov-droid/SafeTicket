#!/usr/bin/env python
"""
One-off admin bootstrap for production (no shell on Render free tier).
Finds user by email and grants staff, superuser, and seller role.
Remove from startCommand after first successful deploy.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')

import django

django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
TARGET_EMAIL = 'shohamyaccov@gmail.com'


def main() -> int:
    qs = User.objects.filter(email__iexact=TARGET_EMAIL)
    if not qs.exists():
        print(
            f'[fix_admin] WARNING: no user with email {TARGET_EMAIL!r} — create account first, then redeploy.',
            flush=True,
        )
        return 0

    user = qs.first()
    user.is_superuser = True
    user.is_staff = True
    user.role = 'seller'
    user.save(update_fields=['is_superuser', 'is_staff', 'role'])
    print(
        f'[fix_admin] OK: {user.username} ({user.email}) -> is_superuser=True, is_staff=True, role=seller',
        flush=True,
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
