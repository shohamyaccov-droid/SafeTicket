"""
Seed מאירים בסליחות at Sultan's Pool, Jerusalem (6–9 Sep 2026).

Creates the show hub artist `/artist/meirim-bslichot` and four event dates
with ASCII slugs `/event/meirim-bslichot-2026-09-06` … `-2026-09-09`.

Usage:
  cd backend
  python manage.py seed_meirim_bslichot
  python manage.py seed_meirim_bslichot --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from users.meirim_bslichot import (
    ARTIST_NAME,
    ARTIST_SLUG,
    SHOW_DATES,
    VENUE_CITY,
    VENUE_PLACE_NAME,
    expected_event_slug,
    seed_meirim_bslichot,
)


class Command(BaseCommand):
    help = 'Create or update מאירים בסליחות (Sultan\'s Pool, 6–9 Sep 2026). Idempotent.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned rows without writing to the database.',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN — no database changes.'))
            self.stdout.write(f'Artist: {ARTIST_NAME} slug={ARTIST_SLUG}')
            self.stdout.write(f'Venue: {VENUE_PLACE_NAME}, {VENUE_CITY}')
            for when in SHOW_DATES:
                self.stdout.write(
                    f'  - {when.isoformat()} -> /event/{expected_event_slug(when)}'
                )
            return

        result = seed_meirim_bslichot()
        artist = result['artist']
        if result['artist_created']:
            self.stdout.write(self.style.SUCCESS(f'Created artist id={artist.pk} slug={artist.slug}'))
        else:
            self.stdout.write(self.style.NOTICE(f'Updated artist id={artist.pk} slug={artist.slug}'))
        if result['venue_created']:
            self.stdout.write(self.style.SUCCESS(f'Created venue {VENUE_PLACE_NAME}, {VENUE_CITY}'))

        for ev in result['events']:
            local = ev.date.astimezone(SHOW_DATES[0].tzinfo)
            self.stdout.write(
                f'  event id={ev.pk} slug={ev.slug} date={local.isoformat()}'
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. created={result["created"]} updated={result["updated"]} '
                f'hub=/artist/{artist.slug}'
            )
        )
