"""
Seed August 2026 concert artists and events (Mor Ravia, Itay Levi, Pe'er Tasi, Eden Ben Zaken, Ben Tzur).

Idempotent: safe to run multiple times (uses update_or_create).
Sets category/is_international on artists and high_demand on events for homepage discovery.

Usage:
  cd backend
  python manage.py seed_august_2026_concerts

  python manage.py seed_august_2026_concerts --dry-run
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
VENUE_ISRAEL = 'ישראל'

VENUE_MENORA_PLACE = ('היכל מנורה מבטחים', 'תל אביב')
VENUE_CAESAREA_PLACE = ('אמפי קיסריה', 'קיסריה')

ARTIST_DEFAULTS = {
    'מור רביעי': {'genre': 'Pop', 'description': 'Mor Ravia — Israeli artist'},
    'פאר טסי': {'genre': 'Hip-Hop / Rap', 'description': "Pe'er Tasi — Israeli rapper"},
    'איתי לוי': {'genre': 'Mizrahi', 'description': 'Itay Levi — Israeli singer'},
    'עדן בן זקן': {'genre': 'Pop', 'description': 'Eden Ben Zaken — Israeli singer'},
    'בן צור': {'genre': 'Pop', 'description': 'Ben Tzur — Israeli singer'},
}

EDEN_MENORA_DATES = (
    (2026, 8, 17, 21, 0),
    (2026, 8, 18, 21, 0),
    (2026, 8, 20, 21, 0),
)

BEN_TZUR_CAESAREA_DATES = (
    (2026, 7, 26, 21, 0),
    (2026, 7, 27, 21, 0),
)

ITAY_LEVI_CAESAREA_DATES = (
    (2026, 8, 29, 21, 0),
    (2026, 9, 1, 20, 45),
)

REMOVED_ARTIST_NAMES = ('עומר אדם',)


@dataclass(frozen=True)
class ShowSpec:
    artist_name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    venue_label: str
    venue_place_key: tuple[str, str]
    city: str


SHOWS: tuple[ShowSpec, ...] = (
    ShowSpec('מור רביעי', 2026, 8, 13, 21, 0, VENUE_MENORA, VENUE_MENORA_PLACE, 'תל אביב'),
    ShowSpec('איתי לוי', 2026, 8, 15, 21, 30, VENUE_MENORA, VENUE_MENORA_PLACE, 'תל אביב'),
    *(
        ShowSpec('פאר טסי', 2026, 8, day, 20, 30, VENUE_ISRAEL, VENUE_CAESAREA_PLACE, 'קיסריה')
        for day in (13, 15, 18, 20, 22, 25)
    ),
    *(
        ShowSpec('עדן בן זקן', y, m, d, h, minute, VENUE_MENORA, VENUE_MENORA_PLACE, 'תל אביב')
        for y, m, d, h, minute in EDEN_MENORA_DATES
    ),
    *(
        ShowSpec('בן צור', y, m, d, h, minute, VENUE_ISRAEL, VENUE_CAESAREA_PLACE, 'קיסריה')
        for y, m, d, h, minute in BEN_TZUR_CAESAREA_DATES
    ),
    *(
        ShowSpec('איתי לוי', y, m, d, h, minute, VENUE_ISRAEL, VENUE_CAESAREA_PLACE, 'קיסריה')
        for y, m, d, h, minute in ITAY_LEVI_CAESAREA_DATES
    ),
)


def _dt(y: int, m: int, d: int, h: int, minute: int) -> datetime:
    return datetime(y, m, d, h, minute, 0, tzinfo=TZ_IL)


def _event_title(spec: ShowSpec, when: datetime) -> str:
    place = spec.venue_place_key[0]
    return f'{spec.artist_name} - {place} — {when.strftime("%d.%m.%Y")}'


class Command(BaseCommand):
    help = 'Create or update August 2026 concert artists and events (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned rows without writing to the database.',
        )

    def _cancel_removed_artists_events(self) -> None:
        Event.objects.filter(
            artist__name__in=REMOVED_ARTIST_NAMES,
            status='פעיל',
        ).update(status='בוטל')

    def _normalize_eden_menora_schedule(self) -> None:
        eden = Artist.objects.filter(name='עדן בן זקן').first()
        if not eden:
            return

        target_dates = {_dt(y, m, d, h, minute).date() for y, m, d, h, minute in EDEN_MENORA_DATES}
        menora_qs = Event.objects.filter(artist=eden, venue=VENUE_MENORA, status='פעיל')
        for ev in menora_qs:
            d = ev.date.astimezone(TZ_IL).date()
            if d not in target_dates:
                ev.status = 'בוטל'
                ev.save(update_fields=['status'])

        for y, m, d, h, minute in EDEN_MENORA_DATES:
            day = _dt(y, m, d, h, minute).date()
            active_on_day = list(
                Event.objects.filter(artist=eden, venue=VENUE_MENORA, status='פעיל', date__date=day).order_by('id')
            )
            if len(active_on_day) > 1:
                for extra in active_on_day[1:]:
                    extra.status = 'בוטל'
                    extra.save(update_fields=['status'])

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        venue_cache: dict[tuple[str, str], Venue] = {}
        for key in {s.venue_place_key for s in SHOWS}:
            if dry_run:
                venue_cache[key] = None  # type: ignore[assignment]
            else:
                venue_cache[key], _ = Venue.objects.get_or_create(name=key[0], city=key[1])

        artist_cache: dict[str, Artist] = {}
        for name, defaults in ARTIST_DEFAULTS.items():
            if dry_run:
                artist_cache[name] = None  # type: ignore[assignment]
                continue
            artist, created = Artist.objects.update_or_create(
                name=name,
                defaults={
                    **defaults,
                    'category': 'music',
                    'is_international': False,
                },
            )
            artist_cache[name] = artist
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created artist: {name} (id={artist.pk})'))
            else:
                self.stdout.write(self.style.NOTICE(f'Updated artist: {name} (id={artist.pk})'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no database changes.'))
            for spec in SHOWS:
                when = _dt(spec.year, spec.month, spec.day, spec.hour, spec.minute)
                vp_name, vp_city = spec.venue_place_key
                self.stdout.write(
                    f'  - {_event_title(spec, when)} @ {when.isoformat()} '
                    f'venue={spec.venue_label!r} place={vp_name}, {vp_city}'
                )
            return

        created = 0
        updated = 0

        with transaction.atomic():
            for spec in SHOWS:
                when = _dt(spec.year, spec.month, spec.day, spec.hour, spec.minute)
                artist = artist_cache[spec.artist_name]
                venue_place = venue_cache[spec.venue_place_key]
                title = _event_title(spec, when)

                ev, was_created = Event.objects.update_or_create(
                    artist=artist,
                    date=when,
                    defaults={
                        'name': title,
                        'venue': spec.venue_label,
                        'venue_place': venue_place,
                        'city': spec.city,
                        'category': 'concert',
                        'status': 'פעיל',
                        'country': 'IL',
                        'high_demand': True,
                    },
                )
                if was_created:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f'Created: {ev.name} (id={ev.pk})'))
                else:
                    updated += 1
                    self.stdout.write(self.style.NOTICE(f'Updated: {ev.name} (id={ev.pk})'))

            self._cancel_removed_artists_events()
            self._normalize_eden_menora_schedule()

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. artists={len(ARTIST_DEFAULTS)}, '
                f'events_created={created}, events_updated={updated}, total_shows={len(SHOWS)}'
            )
        )
