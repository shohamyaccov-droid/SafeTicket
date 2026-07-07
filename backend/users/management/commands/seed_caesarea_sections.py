"""
Seed VenueSection rows for Caesarea Amphitheater (Sell page + structured tickets).

Usage:
  cd backend
  python manage.py seed_caesarea_sections
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Venue, VenueSection

VENUE_PLACE_NAME = 'אמפי קיסריה'
VENUE_CITY = 'קיסריה'

# Matches frontend CAESAREA_SECTION_IDS / CaesareaMap (19 selectable sections)
CAESAREA_SECTION_NAMES = [
    'אורקסטרה',
    *[f'{n} תחתון' for n in range(1, 7)],
    *[f'{n} אמצע' for n in range(1, 7)],
    *[f'{n} עליון' for n in range(1, 7)],
]


class Command(BaseCommand):
    help = 'Seed Caesarea Amphitheater venue sections for the Sell page dropdown.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print planned sections without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no database changes.'))
            self.stdout.write(f'Venue: {VENUE_PLACE_NAME}, {VENUE_CITY}')
            for name in CAESAREA_SECTION_NAMES:
                self.stdout.write(f'  - {name}')
            return

        with transaction.atomic():
            venue, created = Venue.objects.get_or_create(
                name=VENUE_PLACE_NAME,
                city=VENUE_CITY,
            )
            added = 0
            for name in CAESAREA_SECTION_NAMES:
                _, was_created = VenueSection.objects.get_or_create(venue=venue, name=name)
                if was_created:
                    added += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. venue_id={venue.pk} venue_created={created} sections_added={added} '
                f'total={len(CAESAREA_SECTION_NAMES)}'
            )
        )
