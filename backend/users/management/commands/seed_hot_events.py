"""
Seed Q3/Q4 2026 high-demand Israeli concerts (homepage "הופעות סולד-אאוט מבוקשות").

Catalog rows use the product-brief Hebrew titles, dates, and venues.
Idempotent: update_or_create(artist, date). Sets Event.high_demand=True
(API also exposes is_hot). Keeps status='פעיל' so GET /users/events/?high_demand=1
returns them (sold-out status is excluded from the marketplace list).

Downloads Wikimedia artist photos onto Artist.image / cover_image and Event.image.
On production, pass --force-images so leftover Unsplash files are replaced.

Usage:
  cd backend
  python manage.py seed_hot_events
  python manage.py seed_hot_events --dry-run
  python manage.py seed_hot_events --force-images
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')

VENUE_MENORA = 'היכל מנורה מבטחים'
VENUE_GENERIC = 'ישראל'


def _console_safe(text: str) -> str:
    """Avoid UnicodeEncodeError on Windows consoles (cp1252) during management commands."""
    encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    return str(text).encode(encoding, errors='replace').decode(encoding, errors='replace')

# Wikimedia requires a descriptive User-Agent; HEAD-checked 31 Aug 2026 (HTTP 200).
WIKIMEDIA_UA = {
    'User-Agent': 'TradeTix-Seed/1.0 (https://tradetix.co.il; catalog-image-seed)',
}

def _commons(filename: str, width: int = 1200) -> str:
    return f'https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width={width}'


# Real artist photos (Wikimedia Commons / Hebrew Wikipedia infobox). Not Unsplash.
ARTIST_IMAGE_URLS: dict[str, str] = {
    'חנן בן ארי': _commons('%D7%97%D7%A0%D7%9F_%D7%91%D7%9F_%D7%90%D7%A8%D7%99.jpg'),
    'ישי ריבו': _commons('Yishai_Rivo6960.JPG'),
    'טונה': _commons('%D7%90%D7%99%D7%AA%D7%99_%D7%96%D7%91%D7%95%D7%9C%D7%95%D7%9F_%D7%98%D7%95%D7%A0%D7%94.jpg'),
    'שרית חדד': _commons('Sarit_Hadad.jpg'),
    'אגם בוחבוט': _commons('Agam_Buhbut_by_Pini_Siluk_%28cropped%29.jpg'),
    'נועם בתן': _commons('Noam_Bettan_2.jpg'),
    'פסטיגל': (
        'https://upload.wikimedia.org/wikipedia/he/4/42/'
        '%D7%9E%D7%99%D7%99_%D7%A4%D7%A1%D7%98%D7%99%D7%92%D7%9C.jpg'
    ),
    'הדג נחש': 'https://upload.wikimedia.org/wikipedia/he/f/fa/HaDagNahash.jpg',
}


def _image_ext_from_response(response) -> str:
    content_type = (response.headers.get('content-type') or '').lower()
    if 'html' in content_type:
        raise ValueError(f'got HTML instead of an image ({response.url})')
    if 'png' in content_type:
        return 'png'
    if 'webp' in content_type:
        return 'webp'
    if 'jpeg' in content_type or 'jpg' in content_type:
        return 'jpg'
    path = urlparse(response.url).path.lower()
    if path.endswith('.png'):
        return 'png'
    if path.endswith('.webp'):
        return 'webp'
    return 'jpg'


def download_image_bytes(cmd: BaseCommand, url: str) -> tuple[bytes, str] | None:
    """GET `url` once. Returns (bytes, extension) or None on failure."""
    try:
        response = requests.get(url, timeout=30, headers=WIKIMEDIA_UA, allow_redirects=True)
        response.raise_for_status()
        return response.content, _image_ext_from_response(response)
    except Exception as exc:
        cmd.stdout.write(cmd.style.WARNING(f'  skip image download ({url}): {exc}'))
        return None


def save_image_bytes(instance, field_name: str, content: bytes, ext: str, *, force: bool = False) -> bool:
    field = getattr(instance, field_name)
    if field and field.name and not force:
        return False
    slug = str(getattr(instance, 'pk', None) or 'new')
    fname = f'seed_{field_name}_{slug}.{ext}'
    field.save(fname, ContentFile(content), save=True)
    return True


def attach_image_from_url(
    cmd: BaseCommand,
    instance,
    field_name: str,
    url: str,
    *,
    force: bool = False,
) -> bool:
    """Download `url` onto an ImageField. Returns True if a file was saved."""
    payload = download_image_bytes(cmd, url)
    if not payload:
        return False
    content, ext = payload
    return save_image_bytes(instance, field_name, content, ext, force=force)


def apply_catalog_images(cmd: BaseCommand, artist, url: str, events, *, force: bool = False) -> int:
    """Set artist.image, artist.cover_image, and event.image from the same source URL."""
    payload = download_image_bytes(cmd, url)
    if not payload:
        return 0
    content, ext = payload
    saved = 0
    if save_image_bytes(artist, 'image', content, ext, force=force):
        saved += 1
    artist.refresh_from_db()
    if save_image_bytes(artist, 'cover_image', content, ext, force=force):
        saved += 1
    for event in events:
        if save_image_bytes(event, 'image', content, ext, force=force):
            saved += 1
    return saved



@dataclass(frozen=True)
class ShowSpec:
    artist_name: str
    event_name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    venue_place_name: str
    city: str
    venue_choice: str = VENUE_GENERIC
    category: str = 'concert'
    artist_genre: str = 'Pop'
    artist_description: str = ''


# Exact Hebrew titles / venues from the product brief (evening showtimes).
SHOWS: tuple[ShowSpec, ...] = (
    ShowSpec(
        'חנן בן ארי',
        'חנן בן ארי - הינדיקים',
        2026, 9, 19, 21, 30,
        'אקספו תל אביב', 'תל אביב',
        artist_genre='Pop',
        artist_description='חנן בן ארי — זמר-יוצר ישראלי',
    ),
    ShowSpec(
        'ישי ריבו',
        'ישי ריבו - מופע סימפוני',
        2026, 9, 16, 21, 0,
        'אקספו תל אביב', 'תל אביב',
        artist_genre='Jewish / Pop',
        artist_description='ישי ריבו — זמר ישראלי',
    ),
    ShowSpec(
        'טונה',
        'טונה - הופעת חיה',
        2026, 10, 17, 21, 0,
        'זאפה תל אביב', 'תל אביב',
        artist_genre='Hip-Hop / Rap',
        artist_description='טונה — ראפר ישראלי',
    ),
    ShowSpec(
        'פסטיגל',
        'פסטיגל 2026 - TOP SECRET',
        2026, 11, 28, 16, 0,
        'אקספו תל אביב, ביתן 2', 'תל אביב',
        category='festival',
        artist_genre='Family / Pop',
        artist_description='פסטיגל — מופע חנוכה משפחתי',
    ),
    ShowSpec(
        'הדג נחש',
        'הדג נחש - חוגגים 30 שנה',
        2026, 9, 30, 20, 30,
        'אמפי גבעת התחמושת, ירושלים', 'ירושלים',
        artist_genre='Hip-Hop',
        artist_description='הדג נחש — היפ-הופ ישראלי',
    ),
    ShowSpec(
        'נועם בתן',
        'נועם בתן - מופע בכורה',
        2026, 9, 28, 21, 0,
        'היכל מנורה מבטחים, תל אביב', 'תל אביב',
        venue_choice=VENUE_MENORA,
        artist_genre='Pop',
        artist_description='נועם בתן — זמר ישראלי',
    ),
    ShowSpec(
        'אגם בוחבוט',
        'אגם בוחבוט - אלבום 22',
        2026, 10, 1, 21, 0,
        'היכל מנורה מבטחים, תל אביב', 'תל אביב',
        venue_choice=VENUE_MENORA,
        artist_genre='Pop / Mizrahi',
        artist_description='אגם בוחבוט — זמרת ישראלית',
    ),
    ShowSpec(
        'אגם בוחבוט',
        'אגם בוחבוט - אלבום 22',
        2026, 10, 3, 21, 0,
        'היכל מנורה מבטחים, תל אביב', 'תל אביב',
        venue_choice=VENUE_MENORA,
        artist_genre='Pop / Mizrahi',
        artist_description='אגם בוחבוט — זמרת ישראלית',
    ),
    ShowSpec(
        'שרית חדד',
        'שרית חדד - 30 שנות מוזיקה',
        2026, 9, 16, 20, 0,
        'פארק הירקון, תל אביב', 'תל אביב',
        artist_genre='Mizrahi',
        artist_description='שרית חדד — זמרת ישראלית',
    ),
    ShowSpec(
        'שרית חדד',
        'שרית חדד - 30 שנות מוזיקה',
        2026, 9, 17, 20, 0,
        'פארק הירקון, תל אביב', 'תל אביב',
        artist_genre='Mizrahi',
        artist_description='שרית חדד — זמרת ישראלית',
    ),
)


def _dt(spec: ShowSpec) -> datetime:
    return datetime(spec.year, spec.month, spec.day, spec.hour, spec.minute, 0, tzinfo=TZ_IL)


class Command(BaseCommand):
    help = 'Create or update Q3/Q4 2026 high-demand Israeli concerts (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned rows without writing to the database.',
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='Do not download artist photos (used by unit tests).',
        )
        parser.add_argument(
            '--force-images',
            action='store_true',
            help='Re-download and replace existing artist photos.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        skip_images = options['skip_images']
        force_images = options['force_images']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no database changes.'))
            for spec in SHOWS:
                when = _dt(spec)
                self.stdout.write(
                    _console_safe(
                        f'  - {spec.event_name} | {spec.artist_name} @ {when.isoformat()} '
                        f'{spec.venue_place_name}, {spec.city}'
                    )
                )
            self.stdout.write(f'Total shows: {len(SHOWS)}')
            return

        created = 0
        updated = 0
        artist_cache: dict[str, Artist] = {}
        venue_cache: dict[tuple[str, str], Venue] = {}
        seeded_events: list[Event] = []

        with transaction.atomic():
            for spec in SHOWS:
                artist = artist_cache.get(spec.artist_name)
                if artist is None:
                    artist, artist_created = Artist.objects.update_or_create(
                        name=spec.artist_name,
                        defaults={
                            'genre': spec.artist_genre,
                            'description': spec.artist_description,
                            'category': 'music',
                            'is_international': False,
                        },
                    )
                    artist_cache[spec.artist_name] = artist
                    label = 'Created' if artist_created else 'Updated'
                    self.stdout.write(
                        self.style.SUCCESS(
                            _console_safe(f'{label} artist: {spec.artist_name} (id={artist.pk})')
                        )
                    )

                vkey = (spec.venue_place_name, spec.city)
                venue_place = venue_cache.get(vkey)
                if venue_place is None:
                    venue_place, _ = Venue.objects.get_or_create(
                        name=spec.venue_place_name,
                        city=spec.city,
                    )
                    venue_cache[vkey] = venue_place

                when = _dt(spec)
                ev, was_created = Event.objects.update_or_create(
                    artist=artist,
                    date=when,
                    defaults={
                        'name': spec.event_name,
                        'venue': spec.venue_choice,
                        'venue_place': venue_place,
                        'city': spec.city,
                        'category': spec.category,
                        'status': 'פעיל',
                        'country': 'IL',
                        'high_demand': True,
                    },
                )
                if was_created:
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            _console_safe(f'Created: {ev.name} @ {when.date()} (id={ev.pk})')
                        )
                    )
                else:
                    updated += 1
                    self.stdout.write(
                        self.style.NOTICE(
                            _console_safe(f'Updated: {ev.name} @ {when.date()} (id={ev.pk})')
                        )
                    )
                seeded_events.append(ev)

        if not skip_images:
            events_by_artist: dict[int, list[Event]] = {}
            for ev in seeded_events:
                events_by_artist.setdefault(ev.artist_id, []).append(ev)
            for name, artist in artist_cache.items():
                url = ARTIST_IMAGE_URLS.get(name)
                if not url:
                    continue
                saved = apply_catalog_images(
                    self,
                    artist,
                    url,
                    events_by_artist.get(artist.pk, []),
                    force=force_images,
                )
                if saved:
                    self.stdout.write(
                        self.style.SUCCESS(_console_safe(f'  images: {name} ({saved} files)'))
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. artists={len(artist_cache)}, events_created={created}, '
                f'events_updated={updated}, total_shows={len(SHOWS)}'
            )
        )
