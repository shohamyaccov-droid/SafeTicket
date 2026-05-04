"""
One-off seed: add four high-profile upcoming sports matches to the database.

Usage:
    python manage.py seed_sports_matches
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from users.models import Event, Venue, VenueSection

TZ_IL = ZoneInfo("Asia/Jerusalem")

VENUE_BLOOMFIELD = "אצטדיון בלומפילד"
VENUE_MENORA = "היכל מנורה מבטחים"
CITY_TLV = "תל אביב"

# Bloomfield sections (as already seeded in seed_real_events)
BLOOMFIELD_SECTIONS = [
    *[str(n) for n in range(201, 210)],
    *[str(n) for n in range(214, 217)],
    *[str(n) for n in range(221, 230)],
    *[str(n) for n in range(234, 237)],
    *[str(n) for n in range(301, 339)],
    *[str(n) for n in range(404, 407)],
    *[str(n) for n in range(419, 432)],
]

# Menora sections (תחתון / עליון per real map)
MENORA_SECTIONS = [
    *[f"{n} תחתון" for n in range(1, 13)],
    *[f"{n} עליון" for n in range(1, 13)],
]


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Return a timezone-aware datetime in Israel time."""
    return datetime(year, month, day, hour, minute, 0, tzinfo=TZ_IL)


def _ensure_venue(name: str, city: str, sections: list[str]) -> Venue:
    """Get or create the structured Venue and its sections."""
    venue, created = Venue.objects.get_or_create(name=name, city=city)
    if created:
        label = name.encode("ascii", errors="replace").decode("ascii")
        print(f"  [venue] created: {label}, {city}")
    for section_name in sections:
        VenueSection.objects.get_or_create(venue=venue, name=section_name)
    return venue


EVENTS = [
    # ── Football (Bloomfield) ─────────────────────────────────────────────────
    {
        "name": "מכבי תל אביב נגד מכבי חיפה - מחזור 33",
        "date": _dt(2026, 5, 13, 20, 30),
        "venue": VENUE_BLOOMFIELD,
        "venue_city": CITY_TLV,
        "venue_sections": BLOOMFIELD_SECTIONS,
        "home_team": "מכבי תל אביב",
        "away_team": "מכבי חיפה",
        "tournament": "ליגת העל בכדורגל",
    },
    {
        "name": 'מכבי תל אביב נגד בית"ר ירושלים - מחזור 34',
        "date": _dt(2026, 5, 16, 20, 30),
        "venue": VENUE_BLOOMFIELD,
        "venue_city": CITY_TLV,
        "venue_sections": BLOOMFIELD_SECTIONS,
        "home_team": "מכבי תל אביב",
        "away_team": 'בית"ר ירושלים',
        "tournament": "ליגת העל בכדורגל",
    },
    # ── Basketball (Menora) ───────────────────────────────────────────────────
    {
        "name": 'מכבי תל אביב נגד הפועל ב"ש',
        "date": _dt(2026, 5, 6, 19, 0),
        "venue": VENUE_MENORA,
        "venue_city": CITY_TLV,
        "venue_sections": MENORA_SECTIONS,
        "home_team": "מכבי תל אביב",
        "away_team": 'הפועל באר שבע',
        "tournament": "ליגת העל בכדורסל",
    },
    {
        "name": "מכבי תל אביב נגד עירוני קרית אתא",
        "date": _dt(2026, 5, 11, 21, 5),
        "venue": VENUE_MENORA,
        "venue_city": CITY_TLV,
        "venue_sections": MENORA_SECTIONS,
        "home_team": "מכבי תל אביב",
        "away_team": "עירוני קרית אתא",
        "tournament": "ליגת העל בכדורסל",
    },
]


class Command(BaseCommand):
    help = "Seed four high-profile sports matches (Bloomfield + Menora) using get_or_create."

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0

        for spec in EVENTS:
            venue_obj = _ensure_venue(
                spec["venue"], spec["venue_city"], spec["venue_sections"]
            )

            event, created = Event.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "date": spec["date"],
                    "venue": spec["venue"],
                    "venue_place": venue_obj,
                    "city": spec["venue_city"],
                    "category": "sport",
                    "status": "פעיל",
                    "country": "IL",
                    "home_team": spec["home_team"],
                    "away_team": spec["away_team"],
                    "tournament": spec["tournament"],
                    "high_demand": True,
                },
            )

            label = event.name.encode("ascii", errors="replace").decode("ascii")
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [created] pk={event.pk} | {event.date:%Y-%m-%d %H:%M} | {label}"
                    )
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [exists]  pk={event.pk} | {label} (skipped, already in DB)"
                    )
                )
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. created={created_count}, already_existed={existing_count}."
            )
        )
