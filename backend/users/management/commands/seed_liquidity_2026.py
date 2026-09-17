"""
Seed high-demand Q3/Q4 2026 shows and Hysteria mega-event for marketplace liquidity.

Artists & shows (task flow):
1. Peer Tasi & Hanan Ben Ari (paired context)  — 24.09 אמפי MAX
2. Ishay Ribo                                   — 29.09 אמפי MAX
3. Azealia Banks (new artist)                   — 08.10 אמפי תל אביב (standing/seated)
4. Mor (existing)                               — 12.11 היכל מנורה
5. Itai Levi (existing)                         — 29.10 היכל מנורה
6. Noam Batan                                   — 28.09 היכל מנורה

Hysteria mega-event (two location cards):
- היסטריה - תל אביב (Menora): 3.12, 5.12, 7.12, 8.12, 9.12, 10.12, 12.12, 13.12, 15.12
- היסטריה - ירושלים (Pais Arena): 26.11, 28.11, 29.11, 30.11, 1.12

Image downloads: from seed_assets/liquidity_2026/*.png → Artists + Events

Usage:
  cd backend
  python manage.py seed_liquidity_2026
  python manage.py seed_liquidity_2026 --dry-run
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')
ASSET_DIR = Path(__file__).parent.parent.parent / 'seed_assets' / 'liquidity_2026'


@dataclass
class ArtistSpec:
    name: str
    slug: str = None
    genre: str = 'Pop'
    category: str = 'music'
    is_international: bool = False
    description: str = ''
    image_file: str = None

    def __post_init__(self):
        if not self.slug:
            self.slug = self.name.replace(' ', '-').lower()


@dataclass
class VenueSpec:
    name: str
    city: str


@dataclass
class EventSpec:
    artist_name: str
    date: datetime
    venue_choice: str
    venue_place: VenueSpec
    event_name: str = None
    category: str = 'concert'
    image_file: str = None
    high_demand: bool = True

    def __post_init__(self):
        if not self.event_name:
            self.event_name = f'{self.artist_name} — {self.venue_place.name}'


ARTISTS = {
    'פאר טסי וחנן בן ארי': ArtistSpec(
        name='פאר טסי וחנן בן ארי',
        slug='peer-tasi-hanan-ben-ari',
        description='פאר טסי וחנן בן ארי — הופעה משותפת',
        image_file='peer_hanan.png',
    ),
    'ישי ריבו': ArtistSpec(
        name='ישי ריבו',
        slug='ishay-ribo',
        description='ישי ריבו — זמר ישראלי',
        image_file='ishay_ribo.png',
    ),
    'אזיליה בנקס': ArtistSpec(
        name='אזיליה בנקס',
        slug='azealia-banks',
        is_international=True,
        description='Azealia Banks — American rapper & singer',
        image_file='azealia_banks.png',
    ),
    'מור': ArtistSpec(
        name='מור',
        slug='mor',
        description='מור — זמרת ישראלית',
        image_file='mor.png',
    ),
    'איתי לוי': ArtistSpec(
        name='איתי לוי',
        slug='itay-levi',
        description='איתי לוי — זמר מזרחי',
        image_file='itai_levi.png',
    ),
    'נועם בתן': ArtistSpec(
        name='נועם בתן',
        slug='noam-batan',
        description='נועם בתן — זמר ישראלי',
        image_file='noam_batan.png',
    ),
    'היסטריה': ArtistSpec(
        name='היסטריה',
        slug='hysteria',
        description='היסטריה — פסטיבל מוזיקה רב-תאריכי',
        image_file='hysteria.png',
    ),
}

VENUES = {
    ('אמפי MAX', 'ראשון לציון'): VenueSpec('אמפי MAX', 'ראשון לציון'),
    ('היכל מנורה מבטחים', 'תל אביב'): VenueSpec('היכל מנורה מבטחים', 'תל אביב'),
    ('אמפי תל אביב', 'תל אביב'): VenueSpec('אמפי תל אביב', 'תל אביב'),
    ('פיס ארנה ירושלים', 'ירושלים'): VenueSpec('פיס ארנה ירושלים', 'ירושלים'),
}

EVENTS = [
    EventSpec(
        artist_name='פאר טסי וחנן בן ארי',
        date=datetime(2026, 9, 24, 20, 0, tzinfo=TZ_IL),
        venue_choice='ישראל',
        venue_place=VENUES[('אמפי MAX', 'ראשון לציון')],
        event_name='פאר טסי וחנן בן ארי — אמפי MAX',
        image_file='peer_hanan.png',
    ),
    EventSpec(
        artist_name='ישי ריבו',
        date=datetime(2026, 9, 29, 20, 0, tzinfo=TZ_IL),
        venue_choice='ישראל',
        venue_place=VENUES[('אמפי MAX', 'ראשון לציון')],
        event_name='ישי ריבו — אמפי MAX',
        image_file='ishay_ribo.png',
    ),
    EventSpec(
        artist_name='אזיליה בנקס',
        date=datetime(2026, 10, 8, 20, 0, tzinfo=TZ_IL),
        venue_choice='אמפי תל אביב',
        venue_place=VENUES[('אמפי תל אביב', 'תל אביב')],
        event_name='Azealia Banks — אמפי תל אביב',
        image_file='azealia_banks.png',
    ),
    EventSpec(
        artist_name='נועם בתן',
        date=datetime(2026, 9, 28, 20, 0, tzinfo=TZ_IL),
        venue_choice='היכל מנורה מבטחים',
        venue_place=VENUES[('היכל מנורה מבטחים', 'תל אביב')],
        event_name='נועם בתן — היכל מנורה',
        image_file='noam_batan.png',
    ),
    EventSpec(
        artist_name='מור',
        date=datetime(2026, 11, 12, 20, 0, tzinfo=TZ_IL),
        venue_choice='היכל מנורה מבטחים',
        venue_place=VENUES[('היכל מנורה מבטחים', 'תל אביב')],
        event_name='מור — היכל מנורה',
        image_file='mor.png',
    ),
    EventSpec(
        artist_name='איתי לוי',
        date=datetime(2026, 10, 29, 20, 0, tzinfo=TZ_IL),
        venue_choice='היכל מנורה מבטחים',
        venue_place=VENUES[('היכל מנורה מבטחים', 'תל אביב')],
        event_name='איתי לוי — היכל מנורה',
        image_file='itai_levi.png',
    ),
]

# Hysteria: two location cards
HYSTERIA_DATES_TELAVIV = [
    datetime(2026, 12, 3, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 5, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 7, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 8, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 9, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 10, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 12, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 13, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 15, 20, 0, tzinfo=TZ_IL),
]

HYSTERIA_DATES_JERUSALEM = [
    datetime(2026, 11, 26, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 11, 28, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 11, 29, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 11, 30, 20, 0, tzinfo=TZ_IL),
    datetime(2026, 12, 1, 20, 0, tzinfo=TZ_IL),
]


def _load_image(filename: str):
    """Load image from seed_assets/liquidity_2026/ as ContentFile."""
    if not filename:
        return None
    path = ASSET_DIR / filename
    if not path.exists():
        return None
    with open(path, 'rb') as f:
        ext = path.suffix.lstrip('.')
        return ContentFile(f.read(), name=f'seed_{filename}')


class Command(BaseCommand):
    help = 'Seed high-demand Q3/Q4 2026 concerts and Hysteria mega-event (location split).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned rows without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] No database changes will be made.\n'))

        with transaction.atomic():
            # Artists
            if not dry_run:
                for spec in ARTISTS.values():
                    artist, created = Artist.objects.update_or_create(
                        name=spec.name,
                        defaults={
                            'slug': spec.slug,
                            'genre': spec.genre,
                            'category': spec.category,
                            'is_international': spec.is_international,
                            'description': spec.description,
                        },
                    )
                    if spec.image_file:
                        img = _load_image(spec.image_file)
                        if img:
                            artist.image = img
                            artist.save(update_fields=['image'])
            else:
                for spec in ARTISTS.values():
                    self.stdout.write(f'Would create: Artist {spec.name}')

            # Venues
            venues_cache = {}
            if not dry_run:
                for (name, city) in VENUES:
                    v, _ = Venue.objects.get_or_create(name=name, city=city)
                    venues_cache[(name, city)] = v
            else:
                for (name, city) in VENUES:
                    venues_cache[(name, city)] = type('obj', (object,), {'name': name, 'city': city})()

            # Regular events
            for spec in EVENTS:
                if dry_run:
                    self.stdout.write(f'Would create: {spec.event_name} @ {spec.date.isoformat()}')
                    continue

                artist = Artist.objects.get(name=spec.artist_name)
                venue_place = venues_cache[(spec.venue_place.name, spec.venue_place.city)]
                ev, created = Event.objects.update_or_create(
                    name=spec.event_name,
                    date=spec.date,
                    defaults={
                        'artist': artist,
                        'venue': spec.venue_choice,
                        'venue_place': venue_place,
                        'city': spec.venue_place.city,
                        'category': spec.category,
                        'status': 'פעיל',
                        'country': 'IL',
                        'high_demand': spec.high_demand,
                        'age_restriction': 'ללא הגבלה',
                    },
                )
                if spec.image_file:
                    img = _load_image(spec.image_file)
                    if img:
                        ev.image = img
                        ev.save(update_fields=['image'])
                status = '✅ Created' if created else '♻️  Updated'
                self.stdout.write(f'{status}: {ev.name}')

            # Hysteria events (location split)
            hysteria_artist = Artist.objects.get(name='היסטריה')
            menora_venue = venues_cache[('היכל מנורה מבטחים', 'תל אביב')]
            pais_venue = venues_cache[('פיס ארנה ירושלים', 'ירושלים')]

            for dt in HYSTERIA_DATES_TELAVIV:
                event_name = f'היסטריה - תל אביב ({dt.strftime("%d.%m")})'
                if dry_run:
                    self.stdout.write(f'Would create: {event_name} @ {dt.isoformat()}')
                    continue
                ev, created = Event.objects.update_or_create(
                    name=event_name,
                    date=dt,
                    defaults={
                        'artist': hysteria_artist,
                        'venue': 'היכל מנורה מבטחים',
                        'venue_place': menora_venue,
                        'city': 'תל אביב',
                        'category': 'festival',
                        'status': 'פעיל',
                        'country': 'IL',
                        'high_demand': True,
                        'age_restriction': 'ללא הגבלה',
                    },
                )
                if not ev.image_id and not dry_run:
                    img = _load_image('hysteria.png')
                    if img:
                        ev.image = img
                        ev.save(update_fields=['image'])
                status = '✅ Created' if created else '♻️  Updated'
                self.stdout.write(f'{status}: {ev.name}')

            for dt in HYSTERIA_DATES_JERUSALEM:
                event_name = f'היסטריה - ירושלים ({dt.strftime("%d.%m")})'
                if dry_run:
                    self.stdout.write(f'Would create: {event_name} @ {dt.isoformat()}')
                    continue
                ev, created = Event.objects.update_or_create(
                    name=event_name,
                    date=dt,
                    defaults={
                        'artist': hysteria_artist,
                        'venue': 'פיס ארנה ירושלים',
                        'venue_place': pais_venue,
                        'city': 'ירושלים',
                        'category': 'festival',
                        'status': 'פעיל',
                        'country': 'IL',
                        'high_demand': True,
                        'age_restriction': 'ללא הגבלה',
                    },
                )
                if not ev.image_id and not dry_run:
                    img = _load_image('hysteria.png')
                    if img:
                        ev.image = img
                        ev.save(update_fields=['image'])
                status = '[+] Created' if created else '[*] Updated'
                self.stdout.write(f'{status}: {ev.name}')

            if not dry_run:
                self.stdout.write('\n' + self.style.SUCCESS('=' * 60))
                self.stdout.write(self.style.SUCCESS('LIQUIDITY SEEDING COMPLETE'))
                self.stdout.write(self.style.SUCCESS('=' * 60))
                event_count = Event.objects.filter(name__contains='היסטריה').count()
                self.stdout.write(f'📊 Hysteria events: {event_count}')
                self.stdout.write(f'📊 Artists: {len(ARTISTS)}')
                self.stdout.write(f'📊 Regular shows: {len(EVENTS)}')
