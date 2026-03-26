#!/usr/bin/env python
"""
Bootstrap for production (no shell on Render free tier): grant staff/superuser/seller
to known accounts. Idempotent — safe on every boot.

- Primary admin by email (TARGET_EMAIL)
- QA bot (qa_bot@safeticket.com) if present — fixes buyer-only self-registration before seed
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')

import django

django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
TARGET_EMAIL = 'shohamyaccov@gmail.com'
QA_BOT_EMAIL = 'qa_bot@safeticket.com'


def _promote(user, label: str) -> None:
    user.is_superuser = True
    user.is_staff = True
    user.role = 'seller'
    user.save(update_fields=['is_superuser', 'is_staff', 'role'])
    print(
        f'[fix_admin] OK {label}: {user.username} ({user.email}) -> staff, superuser, seller',
        flush=True,
    )


def main() -> int:
    qs = User.objects.filter(email__iexact=TARGET_EMAIL)
    if not qs.exists():
        print(
            f'[fix_admin] WARNING: no user with email {TARGET_EMAIL!r} — create account first, then redeploy.',
            flush=True,
        )
    else:
        _promote(qs.first(), 'primary admin')

    qa = User.objects.filter(email__iexact=QA_BOT_EMAIL).first()
    if qa:
        _promote(qa, 'qa_bot')
    else:
        print(f'[fix_admin] INFO: no user {QA_BOT_EMAIL!r} yet (seed_production will create it).', flush=True)

    return 0


if __name__ == '__main__':
    sys.exit(main())
