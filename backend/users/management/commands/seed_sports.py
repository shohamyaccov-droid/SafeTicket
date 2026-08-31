"""
Seed Q3/Q4 2026 high-demand Israeli football and basketball matches.

Fixtures were checked on 31 Aug 2026 against:
- Ligat Ha'Al 2026/27: maccabi-tlv.co.il, Wikipedia, Sport5 / Walla / iSport draw
- Euroleague 2026/27 home games: maccabi.co.il, Walla
- Winner basketball 2026/27 derby windows: Ynet / C14 / Sport1 / maccabi.co.il

Idempotent: update_or_create(artist=home team, date).
Sets Event.high_demand=True (API alias: is_hot). Status stays 'פעיל'
so GET /users/events/ still returns them.

Euroleague *away* games are omitted (no Israeli-stadium inventory).

Usage:
  cd backend
  python manage.py seed_sports
  python manage.py seed_sports --dry-run
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Venue

TZ_IL = ZoneInfo('Asia/Jerusalem')

# Exact Hebrew artist / team names requested for the marketplace.
TEAM_MACCABI_HAIFA = 'מכבי חיפה'
TEAM_MACCABI_TA = 'מכבי תל אביב'
TEAM_BEITAR = 'בית"ר ירושלים'
TEAM_HAPOEL_BS = 'הפועל באר שבע'
TEAM_HAPOEL_TA = 'הפועל תל אביב'
TEAM_HAPOEL_JLM = 'הפועל ירושלים'

VENUE_BLOOMFIELD = 'אצטדיון בלומפילד'
VENUE_SAMMY = 'סמי עופר'
VENUE_MENORA = 'היכל מנורה מבטחים'
VENUE_PAIS = 'פיס ארנה ירושלים'
VENUE_GENERIC = 'ישראל'

TOURNAMENT_FOOTBALL = 'ליגת העל'
TOURNAMENT_EUROLEAGUE = 'יורוליג'
TOURNAMENT_BSL = 'ליגת העל בכדורסל'
TOURNAMENT_SUPER_CUP = 'סופרקאפ'


@dataclass(frozen=True)
class MatchSpec:
    home: str
    away: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    venue_place_name: str
    city: str
    category: str
    tournament: str
    venue_choice: str = VENUE_GENERIC


# High-profile upcoming Q3/Q4 2026 matchups among the listed clubs.
# Kickoff 20:30 is the Israeli Saturday-night TV slot when the clock is TBD.
MATCHES: tuple[MatchSpec, ...] = (
    # ── Football — Ligat Winner / Ligat Ha'Al 2026/27 ─────────────────────
    # Wikipedia fixture grid: Hapoel TA vs Beitar 3.9 (postponed from round 1).
    MatchSpec(
        TEAM_HAPOEL_TA, TEAM_BEITAR,
        2026, 9, 3, 20, 30,
        VENUE_BLOOMFIELD, 'תל אביב',
        'football', TOURNAMENT_FOOTBALL,
        venue_choice=VENUE_BLOOMFIELD,
    ),
    # maccabi-tlv.co.il: round 3, 7.9.2026 20:30 Turner.
    MatchSpec(
        TEAM_HAPOEL_BS, TEAM_MACCABI_TA,
        2026, 9, 7, 20, 30,
        'אצטדיון טוטו טרנר', 'באר שבע',
        'football', TOURNAMENT_FOOTBALL,
    ),
    # Official MTA + league draw: Tel Aviv derby, round 4, 14.9 Bloomfield.
    MatchSpec(
        TEAM_MACCABI_TA, TEAM_HAPOEL_TA,
        2026, 9, 14, 20, 30,
        VENUE_BLOOMFIELD, 'תל אביב',
        'football', TOURNAMENT_FOOTBALL,
        venue_choice=VENUE_BLOOMFIELD,
    ),
    # maccabi-tlv.co.il: round 7, 17.10 Teddy (MTA away).
    MatchSpec(
        TEAM_BEITAR, TEAM_MACCABI_TA,
        2026, 10, 17, 20, 30,
        'אצטדיון טדי', 'ירושלים',
        'football', TOURNAMENT_FOOTBALL,
    ),
    # Sport5 / Walla / iSport draw: round 8, 24.10 Haifa vs Beer Sheva.
    MatchSpec(
        TEAM_MACCABI_HAIFA, TEAM_HAPOEL_BS,
        2026, 10, 24, 20, 30,
        'אצטדיון סמי עופר', 'חיפה',
        'football', TOURNAMENT_FOOTBALL,
        venue_choice=VENUE_SAMMY,
    ),
    # Draw: round 9, 31.10 Hapoel TA vs Maccabi Haifa (Bloomfield).
    MatchSpec(
        TEAM_HAPOEL_TA, TEAM_MACCABI_HAIFA,
        2026, 10, 31, 20, 30,
        VENUE_BLOOMFIELD, 'תל אביב',
        'football', TOURNAMENT_FOOTBALL,
        venue_choice=VENUE_BLOOMFIELD,
    ),
    # Draw: round 10, 7.11 Hapoel BS vs Hapoel TA.
    MatchSpec(
        TEAM_HAPOEL_BS, TEAM_HAPOEL_TA,
        2026, 11, 7, 20, 30,
        'אצטדיון טוטו טרנר', 'באר שבע',
        'football', TOURNAMENT_FOOTBALL,
    ),
    # Draw: round 12, 1.12 Haifa vs Beitar.
    MatchSpec(
        TEAM_MACCABI_HAIFA, TEAM_BEITAR,
        2026, 12, 1, 20, 30,
        'אצטדיון סמי עופר', 'חיפה',
        'football', TOURNAMENT_FOOTBALL,
        venue_choice=VENUE_SAMMY,
    ),
    # Draw: round 13, 5.12 Beitar vs Hapoel BS.
    MatchSpec(
        TEAM_BEITAR, TEAM_HAPOEL_BS,
        2026, 12, 5, 20, 30,
        'אצטדיון טדי', 'ירושלים',
        'football', TOURNAMENT_FOOTBALL,
    ),
    # maccabi-tlv.co.il: round 14, 12.12 MTA vs Hapoel Jerusalem, Bloomfield.
    MatchSpec(
        TEAM_MACCABI_TA, TEAM_HAPOEL_JLM,
        2026, 12, 12, 20, 30,
        VENUE_BLOOMFIELD, 'תל אביב',
        'football', TOURNAMENT_FOOTBALL,
        venue_choice=VENUE_BLOOMFIELD,
    ),
    # maccabi-tlv.co.il: round 15, 19.12 Haifa vs MTA, Sammy Ofer.
    MatchSpec(
        TEAM_MACCABI_HAIFA, TEAM_MACCABI_TA,
        2026, 12, 19, 20, 30,
        'אצטדיון סמי עופר', 'חיפה',
        'football', TOURNAMENT_FOOTBALL,
        venue_choice=VENUE_SAMMY,
    ),
    # maccabi-tlv.co.il: round 16, 29.12 MTA vs Hapoel BS, Bloomfield.
    MatchSpec(
        TEAM_MACCABI_TA, TEAM_HAPOEL_BS,
        2026, 12, 29, 20, 30,
        VENUE_BLOOMFIELD, 'תל אביב',
        'football', TOURNAMENT_FOOTBALL,
        venue_choice=VENUE_BLOOMFIELD,
    ),
    # ── Basketball — Super Cup + Euroleague HOME + Ligat Winner derbies ──
    # maccabi.co.il: Super Cup 17.9.2026 20:55 Menora, Tel Aviv derby.
    MatchSpec(
        TEAM_MACCABI_TA, TEAM_HAPOEL_TA,
        2026, 9, 17, 20, 55,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_SUPER_CUP,
        venue_choice=VENUE_MENORA,
    ),
    # Euroleague home (maccabi.co.il / Walla). 21:05 = typical IL TV tip-off.
    MatchSpec(
        TEAM_MACCABI_TA, 'בשיקטאש',
        2026, 9, 30, 21, 5,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_EUROLEAGUE,
        venue_choice=VENUE_MENORA,
    ),
    MatchSpec(
        TEAM_MACCABI_TA, 'אולימפיה מילאנו',
        2026, 10, 8, 21, 5,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_EUROLEAGUE,
        venue_choice=VENUE_MENORA,
    ),
    MatchSpec(
        TEAM_MACCABI_TA, 'ריאל מדריד',
        2026, 10, 22, 21, 5,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_EUROLEAGUE,
        venue_choice=VENUE_MENORA,
    ),
    MatchSpec(
        TEAM_MACCABI_TA, 'פריז',
        2026, 10, 29, 21, 5,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_EUROLEAGUE,
        venue_choice=VENUE_MENORA,
    ),
    # Euroleague Tel Aviv derby, 12.11 Menora (maccabi.co.il).
    MatchSpec(
        TEAM_MACCABI_TA, TEAM_HAPOEL_TA,
        2026, 11, 12, 21, 5,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_EUROLEAGUE,
        venue_choice=VENUE_MENORA,
    ),
    MatchSpec(
        TEAM_MACCABI_TA, 'אולימפיאקוס',
        2026, 11, 17, 21, 5,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_EUROLEAGUE,
        venue_choice=VENUE_MENORA,
    ),
    MatchSpec(
        TEAM_MACCABI_TA, 'אנאדולו אפס',
        2026, 12, 23, 21, 5,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_EUROLEAGUE,
        venue_choice=VENUE_MENORA,
    ),
    # Euroleague derby 29.12: Hapoel hosts Maccabi (Walla / maccabi.co.il).
    MatchSpec(
        TEAM_HAPOEL_TA, TEAM_MACCABI_TA,
        2026, 12, 29, 21, 5,
        'היכל קבוצת שלמה', 'תל אביב',
        'basketball', TOURNAMENT_EUROLEAGUE,
    ),
    # Winner league windows (C14 / Ynet / Sport1) — Saturday 21:00 in-window.
    # Round 3, 23–26.10: Hapoel TA hosts Hapoel Jerusalem.
    MatchSpec(
        TEAM_HAPOEL_TA, TEAM_HAPOEL_JLM,
        2026, 10, 24, 21, 0,
        'היכל קבוצת שלמה', 'תל אביב',
        'basketball', TOURNAMENT_BSL,
    ),
    # Round 4, 30.10–2.11: Maccabi TA hosts Hapoel TA (Menora derby).
    MatchSpec(
        TEAM_MACCABI_TA, TEAM_HAPOEL_TA,
        2026, 10, 31, 21, 0,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_BSL,
        venue_choice=VENUE_MENORA,
    ),
    # Round 6, 13–16.11: Maccabi TA vs Hapoel Jerusalem classico.
    MatchSpec(
        TEAM_MACCABI_TA, TEAM_HAPOEL_JLM,
        2026, 11, 14, 21, 0,
        VENUE_MENORA, 'תל אביב',
        'basketball', TOURNAMENT_BSL,
        venue_choice=VENUE_MENORA,
    ),
)

TEAM_NAMES = (
    TEAM_MACCABI_HAIFA,
    TEAM_MACCABI_TA,
    TEAM_BEITAR,
    TEAM_HAPOEL_BS,
    TEAM_HAPOEL_TA,
    TEAM_HAPOEL_JLM,
)


def _dt(spec: MatchSpec) -> datetime:
    return datetime(spec.year, spec.month, spec.day, spec.hour, spec.minute, 0, tzinfo=TZ_IL)


def _event_name(spec: MatchSpec) -> str:
    return f'{spec.home} נגד {spec.away}'


class Command(BaseCommand):
    help = 'Create or update Q3/Q4 2026 high-demand Israeli football and basketball matches (idempotent).'

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
            for spec in MATCHES:
                when = _dt(spec)
                self.stdout.write(
                    f'  - [{spec.category}] {_event_name(spec)} | {when.isoformat()} '
                    f'{spec.venue_place_name}, {spec.city} ({spec.tournament})'
                )
            self.stdout.write(f'Total matches: {len(MATCHES)}')
            return

        created = 0
        updated = 0
        artist_cache: dict[str, Artist] = {}
        venue_cache: dict[tuple[str, str], Venue] = {}

        with transaction.atomic():
            for team_name in TEAM_NAMES:
                artist, artist_created = Artist.objects.update_or_create(
                    name=team_name,
                    defaults={
                        'genre': 'Sports',
                        'description': f'{team_name} — מועדון ספורט ישראלי',
                        'category': 'sports',
                        'is_international': False,
                    },
                )
                artist_cache[team_name] = artist
                label = 'Created' if artist_created else 'Updated'
                self.stdout.write(
                    self.style.SUCCESS(f'{label} artist: {team_name} (id={artist.pk})')
                )

            for spec in MATCHES:
                artist = artist_cache[spec.home]
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
                        'name': _event_name(spec),
                        'venue': spec.venue_choice,
                        'venue_place': venue_place,
                        'city': spec.city,
                        'category': spec.category,
                        'status': 'פעיל',
                        'country': 'IL',
                        'home_team': spec.home,
                        'away_team': spec.away,
                        'tournament': spec.tournament,
                        'high_demand': True,
                    },
                )
                if was_created:
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created: {ev.name} @ {when.date()} (id={ev.pk})')
                    )
                else:
                    updated += 1
                    self.stdout.write(
                        self.style.NOTICE(f'Updated: {ev.name} @ {when.date()} (id={ev.pk})')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. artists={len(artist_cache)}, events_created={created}, '
                f'events_updated={updated}, total_matches={len(MATCHES)}'
            )
        )
