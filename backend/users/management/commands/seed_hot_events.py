"""
Seed Q3/Q4 2026 high-demand Israeli concerts (homepage "הופעות סולד-אאוט מבוקשות").

Dates and venues were checked against official/artist/Tickchak/news listings
(31 Aug 2026). Unverified rows from the original brief are omitted or corrected.

Idempotent: update_or_create(artist, date). Sets Event.high_demand=True.
Keeps status='פעיל' so the marketplace list still returns them (sold-out
status is excluded from GET /users/events/).

Usage:
  cd backend
  python manage.py seed_hot_events
  python manage.py seed_hot_events --dry-run
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')

VENUE_MENORA = 'היכל מנורה מבטחים'
VENUE_BARBY = 'בארבי תל אביב'
VENUE_PAIS = 'פיס ארנה ירושלים'
VENUE_GENERIC = 'ישראל'


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


# Hebrew titles follow the product brief; venues/times follow verified listings.
SHOWS: tuple[ShowSpec, ...] = (
    # Tickchak listed "הינדיקים" at Expo on 30.7.2026 (past). Upcoming Expo
    # residency date 19.9.2026 21:30 appears on secondary ticket sites.
    ShowSpec(
        'חנן בן ארי',
        'חנן בן ארי - הינדיקים',
        2026, 9, 19, 21, 30,
        'אקספו תל אביב', 'תל אביב',
        artist_genre='Pop',
        artist_description='חנן בן ארי — זמר-יוצר ישראלי',
    ),
    # Official ishayribo.com: 16.9.2026 21:00, אמפי MAX ראשון לציון (not Expo TLV).
    ShowSpec(
        'ישי ריבו',
        'ישי ריבו - מופע סימפוני',
        2026, 9, 16, 21, 0,
        'אמפי MAX', 'ראשון לציון',
        artist_genre='Jewish / Pop',
        artist_description='ישי ריבו — זמר ישראלי',
    ),
    # Oct 17 is listed at זאפה אמפי שוני (Binyamina), not Zappa Tel Aviv.
    ShowSpec(
        'טונה',
        'טונה - הופעת חיה',
        2026, 10, 17, 21, 0,
        'זאפה אמפי שוני', 'בנימינה',
        artist_genre='Hip-Hop / Rap',
        artist_description='טונה — ראפר ישראלי',
    ),
    # Tickchak: Tuna Barbie Tel Aviv 28.10.2026 (sold out). Extra verified date.
    ShowSpec(
        'טונה',
        'טונה - הופעת חיה',
        2026, 10, 28, 21, 0,
        'מועדון הבארבי', 'תל אביב',
        venue_choice=VENUE_BARBY,
        artist_genre='Hip-Hop / Rap',
        artist_description='טונה — ראפר ישראלי',
    ),
    # i24 / Srugim: Festigal 2026 TOP SECRET premiere 28.11.2026, Tel Aviv Expo.
    ShowSpec(
        'פסטיגל',
        'פסטיגל 2026 - TOP SECRET',
        2026, 11, 28, 16, 0,
        'אקספו תל אביב, ביתן 2', 'תל אביב',
        category='festival',
        artist_genre='Family / Pop',
        artist_description='פסטיגל — מופע חנוכה משפחתי',
    ),
    # Official hadagnahash.com — not Givat Hatachmoshet 30.9.
    ShowSpec(
        'הדג נחש',
        'הדג נחש - חוגגים 30 שנה',
        2026, 9, 5, 19, 30,
        'אמפי קיסריה', 'קיסריה',
        artist_genre='Hip-Hop',
        artist_description='הדג נחש — היפ-הופ ישראלי',
    ),
    ShowSpec(
        'הדג נחש',
        'הדג נחש - חוגגים 30 שנה',
        2026, 9, 29, 21, 0,
        'זאפה אמפי שוני', 'בנימינה',
        artist_genre='Hip-Hop',
        artist_description='הדג נחש — היפ-הופ ישראלי',
    ),
    # ICE: Menora debut 28.9.2026.
    ShowSpec(
        'נועם בתן',
        'נועם בתן - מופע בכורה',
        2026, 9, 28, 21, 0,
        'היכל מנורה מבטחים', 'תל אביב',
        venue_choice=VENUE_MENORA,
        artist_genre='Pop',
        artist_description='נועם בתן — זמר ישראלי, נציג אירוויזיון 2026',
    ),
    # ICE / mako: Menora 1.10.2026 only (3.10 not announced).
    ShowSpec(
        'אגם בוחבוט',
        'אגם בוחבוט - אלבום 22',
        2026, 10, 1, 21, 0,
        'היכל מנורה מבטחים', 'תל אביב',
        venue_choice=VENUE_MENORA,
        artist_genre='Pop / Mizrahi',
        artist_description='אגם בוחבוט — זמרת ישראלית',
    ),
    # ynet / El Al Flystore: Yarkon 16.9 and 17.9 at 20:00. Sold out on first sale.
    ShowSpec(
        'שרית חדד',
        'שרית חדד - 30 שנות מוזיקה',
        2026, 9, 16, 20, 0,
        'פארק הירקון', 'תל אביב',
        artist_genre='Mizrahi',
        artist_description='שרית חדד — זמרת ישראלית',
    ),
    ShowSpec(
        'שרית חדד',
        'שרית חדד - 30 שנות מוזיקה',
        2026, 9, 17, 20, 0,
        'פארק הירקון', 'תל אביב',
        artist_genre='Mizrahi',
        artist_description='שרית חדד — זמרת ישראלית',
    ),
    # El Al Flystore extra date: Live Park Rishon 20.10.2026 21:00.
    ShowSpec(
        'שרית חדד',
        'שרית חדד - 30 שנות מוזיקה',
        2026, 10, 20, 21, 0,
        'אמפי MAX', 'ראשון לציון',
        artist_genre='Mizrahi',
        artist_description='שרית חדד — זמרת ישראלית',
    ),
    # mako / Tickchak: NEXT 2026 sold-out series, Ramat Gan from 8.10, Pais from 3.12.
    ShowSpec(
        'NEXT',
        'NEXT 2026',
        2026, 10, 8, 21, 0,
        'האצטדיון הלאומי רמת גן', 'רמת גן',
        artist_genre='Pop',
        artist_description='NEXT — עומר אדם, ריטה, עידן עמדי, אושר כהן, אודיה, בן צור',
    ),
    ShowSpec(
        'NEXT',
        'NEXT 2026',
        2026, 12, 3, 21, 0,
        'פיס ארנה ירושלים', 'ירושלים',
        venue_choice=VENUE_PAIS,
        artist_genre='Pop',
        artist_description='NEXT — עומר אדם, ריטה, עידן עמדי, אושר כהן, אודיה, בן צור',
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

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no database changes.'))
            for spec in SHOWS:
                when = _dt(spec)
                self.stdout.write(
                    f'  - {spec.event_name} | {spec.artist_name} @ {when.isoformat()} '
                    f'{spec.venue_place_name}, {spec.city}'
                )
            self.stdout.write(f'Total shows: {len(SHOWS)}')
            return

        created = 0
        updated = 0
        artist_cache: dict[str, Artist] = {}
        venue_cache: dict[tuple[str, str], Venue] = {}

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
                    self.stdout.write(self.style.SUCCESS(f'{label} artist: {spec.artist_name} (id={artist.pk})'))

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
                    self.stdout.write(self.style.SUCCESS(f'Created: {ev.name} @ {when.date()} (id={ev.pk})'))
                else:
                    updated += 1
                    self.stdout.write(self.style.NOTICE(f'Updated: {ev.name} @ {when.date()} (id={ev.pk})'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. artists={len(artist_cache)}, events_created={created}, '
                f'events_updated={updated}, total_shows={len(SHOWS)}'
            )
        )
