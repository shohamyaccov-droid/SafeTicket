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

B) Dashboard → Web Service → Shell (Basic+ plans):
   cd backend && python seed_production.py
   Uses DATABASE_URL from the service — prunes legacy placeholder events, re-seeds artists,
   the 4 launch shows + inventory, and 2 high_demand waitlist events (no tickets).

C) One-off local run against production DB:
   DATABASE_URL='postgres://...' python seed_production.py
   (from backend/ with venv activated)

After a successful seed, remove seed_production.py from Start Command if you used (A).

Production refresh (Render, after deploy)
---------------------------------------
1. Open Render Dashboard → your **Web Service** (e.g. safeticket-api) → **Shell** (requires paid instance).
2. Run:
       cd backend
       python seed_production.py
   The process uses the service `DATABASE_URL`. It prunes legacy placeholder events (incl. Coldplay /
   Taylor Swift / Hamilton / Real Madrid style names and old Hebrew demo rows), re-syncs the four launch
   shows + QA inventory, and upserts two high_demand waitlist events (no tickets).
3. Optional: verify in Django admin → Events / Ticket alerts.

**Stadium geometry refresh (Bloomfield / Menora / Eyal Golan rows)** — one-off; does **not** run on every boot:

    cd backend && python manage.py prune_stadium_catalog --reseed

Deletes events whose artist is אייל גולן or whose name/venue mentions בלומפילד or מנורה, clears Django cache,
then runs the same catalog seed as below (`_seed_all(skip_prune=True)` + inventory assertions).

This does **not** delete user accounts or paid orders; it **does** delete Events (and cascaded tickets)
that match the prune rules — take a DB backup before running if you have custom events you need to keep.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')

import django
from django.conf import settings as django_settings

# Standalone script needs setup; `manage.py migrate` already configured Django before importing this module.
if not django_settings.configured:
    django.setup()


def _seed_log(msg: str) -> None:
    """Windows consoles often use cp1252 — migrations must not crash on Hebrew log output."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((msg + os.linesep).encode('utf-8', errors='replace'))
        sys.stdout.buffer.flush()


from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import uuid

import requests
from django.core.files.base import ContentFile
from django.db import OperationalError, transaction
from django.utils import timezone

from django.contrib.auth import get_user_model

from users.models import Artist, Event, Ticket, Venue

User = get_user_model()

ADMIN_EMAIL = 'shohamyaccov@gmail.com'
# Temporary login for /admin after seed — rotate after first sign-in.
ADMIN_TEMP_PASSWORD = 'Shoham2026!'

# Dedicated QA account for automated E2E (Django admin + API); idempotent — password reset each run.
QA_USER_EMAIL = 'qa_bot@safeticket.com'
QA_USER_USERNAME = 'qa_bot'
QA_USER_PASSWORD = 'SafeTicketQA2026!'

IL_TZ = ZoneInfo('Asia/Jerusalem')


def _il_dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=IL_TZ)


def _launch_pdf_file(name: str) -> ContentFile:
    body = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
    return ContentFile(body, name=name)


# Headliner artists only (launch inventory + waitlist lead magnets).
SEED_ARTISTS: list[dict] = [
    {
        'name': 'בן צור',
        'genre': 'מזרחית',
        'description': 'אמן ישראלי.',
        'image': 'https://images.unsplash.com/photo-1540039155633-ebb4a7940fd9?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1600&q=80',
    },
    {
        'name': 'איתי לוי',
        'genre': 'מזרחית',
        'description': 'זמר ישראלי.',
        'image': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1501612780327-45045589102c?auto=format&fit=crop&w=1600&q=80',
    },
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
        'image': 'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1501281668745-f7f57925c3b4?auto=format&fit=crop&w=1600&q=80',
    },
    {
        'name': 'עדן חסון',
        'genre': 'פופ',
        'description': 'זמרת ישראלית.',
        'image': 'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=800&q=80',
        'cover_image': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1600&q=80',
    },
]

# Official launch headliners (inventory required for homepage marketplace feed).
SEED_LAUNCH_EVENTS: list[dict] = [
    {
        'name': 'בן צור - ארנה ירושלים',
        'date': _il_dt(2026, 5, 28, 21, 0),
        'venue': 'אחר',
        'venue_struct': ('היכל הפיס ארנה', 'ירושלים'),
        'city': 'ירושלים',
        'category': 'concert',
        'artist_name': 'בן צור',
        'prices': [169, 219, 319],
        'event_image': 'https://images.unsplash.com/photo-1540039155633-ebb4a7940fd9?auto=format&fit=crop&w=1400&q=85',
    },
    {
        'name': 'אייל גולן - בלומפילד',
        'date': _il_dt(2026, 6, 18, 20, 0),
        'venue': 'בלומפילד',
        'venue_struct': ('אצטדיון בלומפילד', 'תל אביב'),
        'city': 'תל אביב',
        'category': 'concert',
        'artist_name': 'אייל גולן',
        'prices': [229, 269, 299],
        'event_image': 'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&fit=crop&w=1400&q=85',
    },
    {
        'name': 'איתי לוי - אמפי MAX',
        'date': _il_dt(2026, 5, 28, 20, 45),
        'venue': 'אחר',
        'venue_struct': ('אמפי MAX (לייב פארק)', 'ראשון לציון'),
        'city': 'ראשון לציון',
        'category': 'concert',
        'artist_name': 'איתי לוי',
        'prices': [229, 269],
        'event_image': 'https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=1400&q=85',
    },
    {
        'name': 'עדן חסון - היכל מנורה',
        'date': _il_dt(2026, 6, 25, 20, 45),
        'venue': 'מנורה מבטחים',
        'venue_struct': ('היכל מנורה מבטחים', 'תל אביב'),
        'city': 'תל אביב',
        'category': 'concert',
        'artist_name': 'עדן חסון',
        'prices': [199, 299, 399],
        'event_image': 'https://images.unsplash.com/photo-1459749411175-04bf5292ceea?auto=format&fit=crop&w=1400&q=85',
    },
]

# High-demand “coming soon” rows — no tickets; drives homepage waitlist CTA.
SEED_WAITLIST_EVENTS: list[dict] = [
    {
        'name': 'גמר גביע המדינה בכדורגל',
        'date': _il_dt(2026, 5, 25, 20, 0),
        'venue': 'סמי עופר',
        'venue_struct': ('אצטדיון סמי עופר', 'חיפה'),
        'city': 'חיפה',
        'category': 'sport',
        'artist_name': None,
        'home_team': None,
        'away_team': None,
        'tournament': 'גביע המדינה',
        'event_image': 'https://images.unsplash.com/photo-1574629810360-7efbbe195018?auto=format&fit=crop&w=1400&q=85',
    },
    {
        'name': 'עומר אדם - מופע פארק',
        'date': _il_dt(2026, 6, 10, 19, 30),
        'venue': 'אחר',
        'venue_struct': ('פארק הירקון', 'תל אביב'),
        'city': 'תל אביב',
        'category': 'concert',
        'artist_name': 'עומר אדם',
        'home_team': None,
        'away_team': None,
        'tournament': None,
        'event_image': 'https://images.unsplash.com/photo-1470229722913-7c0e2dbbafd3?auto=format&fit=crop&w=1400&q=85',
    },
]

_LEGACY_EVENT_NAME_SUBSTRINGS = (
    'coldplay',
    'taylor swift',
    'hamilton',
    'real madrid',
    'eras tour',
    'music of the spheres',
    'the eras',
)

_LEGACY_EVENT_NAMES_EXACT = {
    'מכבי תל אביב VS הפועל תל אביב',
    'עומר אדם - היכל מנורה מבטחים',
    'עומר אדם',
    'הצגה: שומרי הסף — תיאטרון הבימה',
    'פסטיבל קיץ תל אביב — ליין אמנים',
    'סטנדאפ: לילה של צחוק',
}


def prune_stadium_catalog_refresh_targets(*, dry_run: bool = False) -> list[dict]:
    """
    One-off catalog reset: remove events tied to Eyal Golan, Bloomfield, or Menora so the next
    seed_production / launch seed recreates rows with fresh ticket listing_group_ids and UI mapping.

    Does NOT run automatically on every seed — use management command `prune_stadium_catalog` on Render shell.

    Tickets and TicketAlerts CASCADE with Event. Clears Django cache after delete (LocMem in default settings).
    """
    from django.core.cache import cache

    matches: list[dict] = []
    for ev in Event.objects.select_related('artist', 'venue_place').all().iterator():
        artist = (ev.artist.name if ev.artist else '') or ''
        name = (ev.name or '') or ''
        venue = (ev.venue or '') or ''
        vp_name = (ev.venue_place.name if ev.venue_place else '') or ''
        blob_lower = f'{artist} {name} {venue} {vp_name}'.lower()
        hay_he = f'{artist} {name} {venue} {vp_name}'
        hit = False
        reasons: list[str] = []
        if 'אייל גולן' in artist or 'eyal golan' in blob_lower:
            hit = True
            reasons.append('artist_eyal_golan')
        if 'בלומפילד' in hay_he or 'bloomfield' in blob_lower:
            hit = True
            reasons.append('venue_bloomfield')
        if 'מנורה' in hay_he or 'menora' in blob_lower or 'מבטחים' in hay_he:
            hit = True
            reasons.append('venue_menora')
        if hit:
            matches.append(
                {
                    'id': ev.pk,
                    'name': name,
                    'date': ev.date,
                    'reasons': reasons,
                }
            )

    if dry_run:
        _seed_log(f'[seed] stadium prune (dry-run): would delete {len(matches)} events: {[m["id"] for m in matches]}')
        return matches

    deleted_ids = [m['id'] for m in matches]
    if deleted_ids:
        Event.objects.filter(pk__in=deleted_ids).delete()
        _seed_log(f'[seed] stadium prune: deleted {len(deleted_ids)} events (ids={deleted_ids})')
    else:
        _seed_log('[seed] stadium prune: no matching events')

    try:
        cache.clear()
        _seed_log('[seed] Django cache cleared after stadium prune')
    except Exception as ex:
        _seed_log(f'[seed] cache.clear() skipped: {ex!r}')

    return matches


def prune_legacy_placeholder_events() -> None:
    """Remove old demo / duplicate catalog rows before re-seeding (production-safe names only)."""
    deleted = 0
    for ev in Event.objects.all().iterator():
        name = (ev.name or '').strip()
        low = name.lower()
        if any(s in low for s in _LEGACY_EVENT_NAME_SUBSTRINGS):
            ev.delete()
            deleted += 1
            continue
        if name in _LEGACY_EVENT_NAMES_EXACT:
            ev.delete()
            deleted += 1
    if deleted:
        _seed_log(f'[seed] pruned {deleted} legacy / placeholder events')


def _download_to_imagefield(instance, field_name: str, url: str) -> None:
    field = getattr(instance, field_name)
    if field and field.name:
        return
    try:
        r = requests.get(
            url,
            timeout=25,
            headers={'User-Agent': 'TradeTix-Seed/1.0 (+https://tradetix.local)'},
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
        # Avoid UnicodeEncodeError on Windows consoles when `instance` repr contains Hebrew.
        _seed_log(
            f'  [seed] skip {field_name} pk={getattr(instance, "pk", None)} model={instance.__class__.__name__}: {ex!r}'
        )
        err = str(ex).lower()
        if 'signature' in err or 'invalid' in err or 'cloudinary' in err:
            _seed_log(
                '  [seed] Cloudinary/media hint: verify CLOUDINARY_URL (or CLOUDINARY_* env) matches '
                'the dashboard; see safeticket.settings CLOUDINARY_STORAGE.'
            )


def seed_admin() -> None:
    qs = User.objects.filter(email__iexact=ADMIN_EMAIL)
    if not qs.exists():
        _seed_log(f'[seed] WARNING: no user {ADMIN_EMAIL!r} — register first, then re-run seed.')
        return
    u = qs.first()
    u.set_password(ADMIN_TEMP_PASSWORD)
    u.is_superuser = True
    u.is_staff = True
    u.role = 'seller'
    u.save()
    _seed_log(f'[seed] admin OK: {u.username} (password reset, staff, superuser, seller)')


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
    _seed_log(
        f'[seed] QA user {action}: {QA_USER_USERNAME} <{QA_USER_EMAIL}> (staff, superuser, seller; password not printed)'
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
        _seed_log(f'[seed] artist {status}: {name}')


def seed_launch_events_and_tickets() -> None:
    """Four official launch shows + verified listing inventory (feed requires active tickets)."""
    seller = User.objects.filter(username=QA_USER_USERNAME).first()
    if not seller:
        _seed_log('[seed] launch inventory skipped — QA user missing')
        return

    artists_by_name = {a.name: a for a in Artist.objects.all()}

    for row in SEED_LAUNCH_EVENTS:
        vname, vcity = row['venue_struct']
        venue_obj, _ = Venue.objects.get_or_create(name=vname, city=vcity)
        artist = artists_by_name.get(row['artist_name'])
        if not artist:
            _seed_log(f'[seed] launch event skipped (no artist): {row["name"]}')
            continue
        defaults = {
            'venue': row['venue'],
            'city': row['city'],
            'category': row['category'],
            'status': 'פעיל',
            'artist': artist,
            'home_team': None,
            'away_team': None,
            'tournament': None,
            'country': 'IL',
            'venue_place': venue_obj,
            'high_demand': True,
        }
        ev, created = Event.objects.update_or_create(
            name=row['name'],
            date=row['date'],
            defaults=defaults,
        )
        _download_to_imagefield(ev, 'image', row['event_image'])
        action = 'created' if created else 'updated'
        _seed_log(f'[seed] launch event {action}: {ev.name} @ {ev.date}')

        for price in row['prices']:
            dec_price = Decimal(price)
            row_key = f'launch-tier-{price}'
            existing = Ticket.objects.filter(event=ev, seller=seller, seat_row=row_key).first()
            if existing:
                if existing.original_price != dec_price:
                    existing.original_price = dec_price
                    existing.asking_price = dec_price
                    existing.save(update_fields=['original_price', 'asking_price', 'updated_at'])
                continue
            t = Ticket(
                seller=seller,
                event=ev,
                event_name=ev.name,
                event_date=ev.date,
                venue=ev.venue,
                original_price=dec_price,
                asking_price=dec_price,
                available_quantity=2,
                verification_status='מאומת',
                status='active',
                seat_row=row_key,
                listing_group_id=str(uuid.uuid4()),
                pdf_file=_launch_pdf_file(f'launch_e{ev.id}_{price}.pdf'),
            )
            t.save()
            _seed_log(f'[seed] launch ticket: event={ev.id} price={price} NIS')


def seed_waitlist_events() -> None:
    """High-demand upcoming events with intentionally no listings — waitlist / lead capture."""
    artists_by_name = {a.name: a for a in Artist.objects.all()}
    for row in SEED_WAITLIST_EVENTS:
        an = row.get('artist_name')
        artist = artists_by_name.get(an) if an else None
        vname, vcity = row['venue_struct']
        venue_obj, _ = Venue.objects.get_or_create(name=vname, city=vcity)
        defaults = {
            'venue': row['venue'],
            'city': row['city'],
            'category': row['category'],
            'status': 'פעיל',
            'artist': artist,
            'home_team': row.get('home_team') or None,
            'away_team': row.get('away_team') or None,
            'tournament': row.get('tournament') or None,
            'country': 'IL',
            'venue_place': venue_obj,
            'high_demand': True,
        }
        ev, created = Event.objects.update_or_create(
            name=row['name'],
            date=row['date'],
            defaults=defaults,
        )
        if row.get('event_image'):
            _download_to_imagefield(ev, 'image', row['event_image'])
        action = 'created' if created else 'updated'
        _seed_log(f'[seed] waitlist event {action}: {ev.name} @ {ev.date} (no tickets)')


def _expected_catalog_event_names() -> frozenset:
    return frozenset(r['name'] for r in SEED_LAUNCH_EVENTS) | frozenset(r['name'] for r in SEED_WAITLIST_EVENTS)


def assert_catalog_event_inventory() -> None:
    """
    Post-condition for production catalog: exactly 4 launch + N waitlist events,
    launch rows have active ticket stock, waitlist rows have zero tickets and high_demand.
    """
    from django.db.models import Sum

    expected = _expected_catalog_event_names()
    n_expected = len(expected)
    n_ev = Event.objects.count()
    if n_ev != n_expected:
        raise RuntimeError(f'Catalog seed: expected exactly {n_expected} events, found {n_ev}')
    got_names = frozenset(Event.objects.values_list('name', flat=True))
    if got_names != expected:
        raise RuntimeError(
            f'Catalog seed: event name set mismatch.\nExpected: {sorted(expected)}\nGot: {sorted(got_names)}'
        )

    for row in SEED_LAUNCH_EVENTS:
        ev = Event.objects.filter(name=row['name'], date=row['date']).first()
        if not ev:
            raise RuntimeError(f'Catalog seed: missing launch event {row["name"]!r}')
        listed = (
            Ticket.objects.filter(event=ev, status='active').aggregate(s=Sum('available_quantity'))['s'] or 0
        )
        if listed < 1:
            raise RuntimeError(f'Catalog seed: launch event {row["name"]!r} has no active ticket quantity')

    for row in SEED_WAITLIST_EVENTS:
        ev = Event.objects.filter(name=row['name'], date=row['date']).first()
        if not ev:
            raise RuntimeError(f'Catalog seed: missing waitlist event {row["name"]!r}')
        if not ev.high_demand:
            raise RuntimeError(f'Catalog seed: waitlist event {row["name"]!r} must have high_demand=True')
        if Ticket.objects.filter(event=ev).exists():
            raise RuntimeError(f'Catalog seed: waitlist event {row["name"]!r} must have zero tickets')


@transaction.atomic
def _seed_all(*, skip_prune: bool = False) -> None:
    if not skip_prune:
        prune_legacy_placeholder_events()
    seed_admin()
    seed_qa_user()
    seed_artists()
    seed_launch_events_and_tickets()
    seed_waitlist_events()
    _seed_log(f'[seed] done: {Artist.objects.count()} artists, {Event.objects.count()} events total in DB')


def run_after_total_wipe() -> None:
    """
    Rebuild catalog after all Event/Ticket rows were removed (e.g. data migration).
    Skips prune — DB is already clean.
    """
    _seed_all(skip_prune=True)
    assert_catalog_event_inventory()


def main() -> int:
    _seed_log('[seed] starting seed_production.py')
    try:
        _seed_all(skip_prune=False)
    except OperationalError as e:
        # Render: transient DNS / DB cold-start must NOT prevent Gunicorn from booting (502 for all traffic).
        _seed_log(f'[seed] WARNING: seed skipped — DB unavailable: {e}')
        return 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
