"""
Seed VenueSection rows for Ramat Gan Stadium (Sell page + structured tickets).

Usage:
  cd backend
  python manage.py seed_ramat_gan_sections
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Venue, VenueSection

VENUE_PLACE_NAME = 'אצטדיון רמת גן'
VENUE_CITY = 'רמת גן'

# Matches frontend STADIUM_CONFIG / ramatGanMapConfig.js (excludes STAGE)
RAMAT_GAN_SECTION_NAMES = [
    '6A', '6C', 'B5', '13A', '13B', '13C', '6B', 'ACCESSIBLE',
    '16A', '16B', '16C', '11B', 'D12', 'A3', 'A2', 'A1', 'B4', '11A',
    'B6', 'C7', 'C8', 'C9', '9A', 'D14', 'D13', 'D11', 'D10', '9B',
    '4', '3', '2-3', '2', '1',
]


class Command(BaseCommand):
    help = 'Seed Ramat Gan Stadium venue sections for the Sell page dropdown.'

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
            for name in RAMAT_GAN_SECTION_NAMES:
                self.stdout.write(f'  - {name}')
            return

        with transaction.atomic():
            venue, created = Venue.objects.get_or_create(
                name=VENUE_PLACE_NAME,
                city=VENUE_CITY,
            )
            added = 0
            for name in RAMAT_GAN_SECTION_NAMES:
                _, was_created = VenueSection.objects.get_or_create(venue=venue, name=name)
                if was_created:
                    added += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Done. venue_id={venue.pk} venue_created={created} sections_added={added} '
                f'total={len(RAMAT_GAN_SECTION_NAMES)}'
            )
        )
