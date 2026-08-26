"""Idempotent catalog seed for מאירים בסליחות at Sultan's Pool, Jerusalem."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.files import File
from django.db import transaction

TZ_IL = ZoneInfo('Asia/Jerusalem')

ARTIST_NAME = 'מאירים בסליחות'
ARTIST_SLUG = 'meirim-bslichot'
EVENT_NAME = 'מאירים בסליחות'
VENUE_CHOICE = 'ישראל'
VENUE_PLACE_NAME = 'בריכת הסולטן'
VENUE_CITY = 'ירושלים'
LINEUP = 'ששון שאולוב, לירן דנינו, בן צור ומתן חסן'
ARTIST_DESCRIPTION = (
    f'{ARTIST_NAME} — {LINEUP}. ארבעה ערבי סליחות בבריכת הסולטן, ירושלים.'
)
ARTIST_BOTTOM_SEO = (
    f'{ARTIST_NAME} בבריכת הסולטן בירושלים מביאים יחד את {LINEUP} '
    'לארבעה ערבי סליחות באלול. מחפשים כרטיסים למאירים בסליחות? ב-TradeTix קונים ומוכרים '
    'כרטיסים יד שנייה עם תשלום בנאמנות והגנה מלאה על הכסף עד אחרי האירוע.'
)

# Israel local time — poster lists dates only; evening start matches other concert seeds.
SHOW_DATES = (
    datetime(2026, 9, 6, 21, 0, tzinfo=TZ_IL),
    datetime(2026, 9, 7, 21, 0, tzinfo=TZ_IL),
    datetime(2026, 9, 8, 21, 0, tzinfo=TZ_IL),
    datetime(2026, 9, 9, 21, 0, tzinfo=TZ_IL),
)

POSTER_PATH = Path(__file__).resolve().parent / 'seed_assets' / 'meirim_bslichot.png'


def expected_event_slug(when: datetime) -> str:
    return f'{ARTIST_SLUG}-{when.astimezone(TZ_IL).strftime("%Y-%m-%d")}'


def _attach_poster_if_missing(artist, events) -> bool:
    if not POSTER_PATH.is_file():
        return False
    attached = False
    if not (getattr(artist, 'cover_image', None) and artist.cover_image.name):
        with POSTER_PATH.open('rb') as fh:
            artist.cover_image.save('meirim_bslichot.png', File(fh), save=False)
        attached = True
    if not (getattr(artist, 'image', None) and artist.image.name):
        with POSTER_PATH.open('rb') as fh:
            artist.image.save('meirim_bslichot.png', File(fh), save=False)
        attached = True
    if attached:
        artist.save()
    for event in events:
        if getattr(event, 'image', None) and event.image.name:
            continue
        with POSTER_PATH.open('rb') as fh:
            event.image.save('meirim_bslichot.png', File(fh), save=True)
        attached = True
    return attached


def seed_meirim_bslichot(*, attach_poster: bool = True) -> dict:
    """
    Create/update the show hub artist and four Sultan's Pool dates.

    Returns a summary dict for management commands / tests.
    """
    from users.models import Artist, Event, Venue

    with transaction.atomic():
        venue_place, venue_created = Venue.objects.get_or_create(
            name=VENUE_PLACE_NAME,
            city=VENUE_CITY,
        )
        artist, artist_created = Artist.objects.update_or_create(
            name=ARTIST_NAME,
            defaults={
                'genre': 'Mizrahi',
                'description': ARTIST_DESCRIPTION,
                'category': 'music',
                'is_international': False,
                'bottom_seo_text': ARTIST_BOTTOM_SEO,
            },
        )
        if (artist.slug or '').strip() != ARTIST_SLUG:
            clash = Artist.objects.filter(slug=ARTIST_SLUG).exclude(pk=artist.pk).exists()
            artist.slug = ARTIST_SLUG if not clash else artist.slug
            if not artist.slug:
                artist.slug = ARTIST_SLUG
            artist.save(update_fields=['slug', 'updated_at'])

        created = 0
        updated = 0
        events = []
        for when in SHOW_DATES:
            ev, was_created = Event.objects.update_or_create(
                artist=artist,
                date=when,
                defaults={
                    'name': EVENT_NAME,
                    'venue': VENUE_CHOICE,
                    'venue_place': venue_place,
                    'city': VENUE_CITY,
                    'category': 'concert',
                    'status': 'פעיל',
                    'country': 'IL',
                    'high_demand': True,
                },
            )
            events.append(ev)
            if was_created:
                created += 1
            else:
                updated += 1

        if attach_poster:
            _attach_poster_if_missing(artist, events)

        artist.refresh_from_db()
        for ev in events:
            ev.refresh_from_db()

    return {
        'artist': artist,
        'artist_created': artist_created,
        'venue_place': venue_place,
        'venue_created': venue_created,
        'events': events,
        'created': created,
        'updated': updated,
    }
