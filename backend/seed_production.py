#!/usr/bin/env python
"""
Master seed for production: artists (remote images), events, venues/cities, admin user, QA superuser.

Also resets ADMIN_EMAIL password to ADMIN_TEMP_PASSWORD (see constant below) — change it after login;
the value is not printed to logs.

Dedicated QA user (QA_USER_EMAIL / QA_USER_PASSWORD): staff + superuser for /admin and E2E; password is not printed.

Uses get_or_create / update_or_create — safe to re-run (idempotent).

Images: Artist.image / cover_image are ImageFields; remote URLs are downloaded once via HTTP
(Unsplash CDN — allowed for hotlinking; we store a copy in MEDIA for Django).

How to run on Render (pick one)
--------------------------------
A) One-time start command (then revert to gunicorn-only):
   python seed_production.py && gunicorn safeticket.wsgi --bind 0.0.0.0:$PORT ...

B) Dashboard → service → Shell (if available on your plan):
   cd backend && python seed_production.py

C) One-off local run against production DB:
   DATABASE_URL='postgres://...' python seed_production.py
   (from backend/ with venv activated)

After a successful seed, remove seed_production.py from Start Command if you used (A).
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')

import django

django.setup()

from datetime import datetime, timezone as dt_timezone

import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from django.contrib.auth import get_user_model

from users.models import Artist, Event

User = get_user_model()

ADMIN_EMAIL = 'shohamyaccov@gmail.com'
# Temporary login for /admin after seed — rotate after first sign-in.
ADMIN_TEMP_PASSWORD = 'Shoham2026!'

# Dedicated QA account for automated E2E (Django admin + API); idempotent — password reset each run.
QA_USER_EMAIL = 'qa_bot@safeticket.com'
QA_USER_USERNAME = 'qa_bot'
QA_USER_PASSWORD = 'SafeTicketQA2026!'

# Unsplash CDN (license: https://unsplash.com/license) — distinct music/live photos per artist.
SEED_ARTISTS: list[dict] = [
    {
        'name': 'עומר אדם',
        'genre': 'פופ / מזרחית',
        'description': 'אמן ישראלי מוביל.',
        'image': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&fit=crop&w=1600&q=80',
    },
    {
        'name': 'אייל גולן',
        'genre': 'מזרחית',
        'description': 'זמר ואמן ישראלי.',
        'image': 'https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?w=1600&q=80',
    },
    {
        'name': 'עדן בן זקן',
        'genre': 'פופ / מזרחית',
        'description': 'זמרת ויוצרת ישראלית.',
        'image': 'https://images.unsplash.com/photo-1493225457124-a3eb161ffa5f?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=1600&q=80',
    },
    {
        'name': 'עדן חסון',
        'genre': 'פופ',
        'description': 'זמרת ישראלית.',
        'image': 'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1600&q=80',
    },
    {
        'name': 'אודייה אזולאי',
        'genre': 'פופ',
        'description': 'זמרת ישראלית.',
        'image': 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1501612780327-45045589102c?w=1600&q=80',
    },
    {
        'name': 'טונה',
        'genre': 'היפ הופ',
        'description': 'ראפר ויוצר ישראלי.',
        'image': 'https://images.unsplash.com/photo-1571266028243-e978f754a31a?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=1600&q=80',
    },
    {
        'name': 'רביד פלוטניק',
        'genre': 'אינדי / רוק',
        'description': 'זמר ויוצר ישראלי.',
        'image': 'https://images.unsplash.com/photo-1501612780327-45045589102c?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1522158637959-30385a09e0da?auto=format&fit=crop&w=1600&q=80',
    },
]

# Mirrors local sqlite events (ids 4–8) + samples for every Event.category choice.
# Dates preserved in UTC to match local DB timestamps.
UTC = dt_timezone.utc

SEED_EVENTS: list[dict] = [
    {
        'name': 'מכבי תל אביב VS הפועל תל אביב',
        'date': datetime(2026, 1, 1, 19, 0, tzinfo=UTC),
        'venue': 'בלומפילד',
        'city': 'תל אביב-יפו',
        'category': 'sport',
        'artist_name': None,
        'home_team': 'מכבי תל אביב',
        'away_team': 'הפועל תל אביב',
        'tournament': 'ליגת העל',
    },
    {
        'name': 'עומר אדם - היכל מנורה מבטחים',
        'date': datetime(2026, 3, 6, 18, 0, tzinfo=UTC),
        'venue': 'מנורה מבטחים',
        'city': 'תל אביב-יפו',
        'category': 'concert',
        'artist_name': 'עומר אדם',
    },
    {
        'name': 'עומר אדם',
        'date': datetime(2026, 3, 9, 12, 49, 32, tzinfo=UTC),
        'venue': 'מנורה מבטחים',
        'city': 'תל אביב-יפו',
        'category': 'concert',
        'artist_name': 'עומר אדם',
    },
    {
        'name': 'עומר אדם - היכל מנורה מבטחים',
        'date': datetime(2026, 4, 1, 18, 0, tzinfo=UTC),
        'venue': 'מנורה מבטחים',
        'city': 'תל אביב-יפו',
        'category': 'concert',
        'artist_name': 'עומר אדם',
    },
    {
        'name': 'עומר אדם - היכל מנורה מבטחים',
        'date': datetime(2026, 4, 8, 18, 0, tzinfo=UTC),
        'venue': 'מנורה מבטחים',
        'city': 'תל אביב-יפו',
        'category': 'concert',
        'artist_name': 'עומר אדם',
    },
    # Category coverage (theatre / festival / standup) — same cities & venues as local patterns
    {
        'name': 'הצגה: שומרי הסף — תיאטרון הבימה',
        'date': datetime(2026, 5, 10, 17, 0, tzinfo=UTC),
        'venue': 'סמי עופר',
        'city': 'חיפה',
        'category': 'theater',
        'artist_name': 'רביד פלוטניק',
    },
    {
        'name': 'פסטיבל קיץ תל אביב — ליין אמנים',
        'date': datetime(2026, 6, 20, 16, 0, tzinfo=UTC),
        'venue': 'בארבי תל אביב',
        'city': 'תל אביב-יפו',
        'category': 'festival',
        'artist_name': 'טונה',
    },
    {
        'name': 'סטנדאפ: לילה של צחוק',
        'date': datetime(2026, 7, 5, 19, 30, tzinfo=UTC),
        'venue': 'מנורה מבטחים',
        'city': 'תל אביב-יפו',
        'category': 'standup',
        'artist_name': 'אייל גולן',
    },
]


def _download_to_imagefield(instance, field_name: str, url: str) -> None:
    field = getattr(instance, field_name)
    if field and field.name:
        return
    try:
        r = requests.get(
            url,
            timeout=25,
            headers={'User-Agent': 'SafeTrade-Seed/1.0 (+https://safeticket.local)'},
        )
        r.raise_for_status()
        ext = 'jpg'
        ct = (r.headers.get('content-type') or '').lower()
        if 'png' in ct:
            ext = 'png'
        elif 'webp' in ct:
            ext = 'webp'
        fname = f'seed_{field_name}_{instance.pk or "new"}.{ext}'
        field.save(fname, ContentFile(r.content), save=True)
    except Exception as ex:
        print(f'  [seed] skip {field_name} for {instance}: {ex}', flush=True)
        err = str(ex).lower()
        if 'signature' in err or 'invalid' in err or 'cloudinary' in err:
            print(
                '  [seed] Cloudinary/media hint: verify CLOUDINARY_URL (or CLOUDINARY_* env) matches '
                'the dashboard; see safeticket.settings CLOUDINARY_STORAGE.',
                flush=True,
            )


def seed_admin() -> None:
    qs = User.objects.filter(email__iexact=ADMIN_EMAIL)
    if not qs.exists():
        print(f'[seed] WARNING: no user {ADMIN_EMAIL!r} — register first, then re-run seed.', flush=True)
        return
    u = qs.first()
    u.set_password(ADMIN_TEMP_PASSWORD)
    u.is_superuser = True
    u.is_staff = True
    u.role = 'seller'
    u.save()
    print(
        f'[seed] admin OK: {u.username} (password reset, staff, superuser, seller)',
        flush=True,
    )


def seed_qa_user() -> None:
    """
    Ensure QA bot user exists with staff/superuser; password set to QA_USER_PASSWORD (not logged).
    Role seller so ticket upload E2E works without role changes.
    """
    u, created = User.objects.update_or_create(
        username=QA_USER_USERNAME,
        defaults={
            'email': QA_USER_EMAIL,
            'is_staff': True,
            'is_superuser': True,
            'role': 'seller',
            'is_email_verified': True,
        },
    )
    u.set_password(QA_USER_PASSWORD)
    u.save()
    action = 'created' if created else 'updated'
    print(
        f'[seed] QA user {action}: {QA_USER_USERNAME} <{QA_USER_EMAIL}> (staff, superuser, seller; password not printed)',
        flush=True,
    )


def seed_artists() -> None:
    for row in SEED_ARTISTS:
        name = row['name']
        artist, created = Artist.objects.get_or_create(
            name=name,
            defaults={
                'description': row.get('description') or '',
                'genre': row.get('genre') or '',
            },
        )
        if not created:
            artist.description = row.get('description') or artist.description
            artist.genre = row.get('genre') or artist.genre
            artist.save(update_fields=['description', 'genre'])
        _download_to_imagefield(artist, 'image', row['image'])
        if row.get('cover_image'):
            _download_to_imagefield(artist, 'cover_image', row['cover_image'])
        status = 'created' if created else 'updated'
        print(f'[seed] artist {status}: {name}', flush=True)


def seed_events() -> None:
    artists_by_name = {a.name: a for a in Artist.objects.all()}
    for row in SEED_EVENTS:
        an = row.get('artist_name')
        artist = artists_by_name.get(an) if an else None
        defaults = {
            'venue': row['venue'],
            'city': row['city'],
            'category': row['category'],
            'status': 'פעיל',
            'artist': artist,
            'home_team': row.get('home_team') or None,
            'away_team': row.get('away_team') or None,
            'tournament': row.get('tournament') or None,
        }
        ev, created = Event.objects.update_or_create(
            name=row['name'],
            date=row['date'],
            defaults=defaults,
        )
        action = 'created' if created else 'updated'
        print(f'[seed] event {action}: {ev.name} @ {ev.date}', flush=True)


@transaction.atomic
def main() -> int:
    print('[seed] starting seed_production.py', flush=True)
    seed_admin()
    seed_qa_user()
    seed_artists()
    seed_events()
    print(
        f'[seed] done: {Artist.objects.count()} artists, {Event.objects.count()} events total in DB',
        flush=True,
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
