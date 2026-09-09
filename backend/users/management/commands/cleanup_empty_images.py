"""
Cleanup command: Delete all Event and Artist records with null or empty image fields.

CRITICAL: Runs during deployment to remove broken records that lack images.

Usage:
  python manage.py cleanup_empty_images                    # Delete records
  python manage.py cleanup_empty_images --dry-run         # Show what would be deleted
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event


class Command(BaseCommand):
    help = "Delete Event and Artist records with null or empty image fields (cleanup broken seed data)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without making changes',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] No database changes will be made.'))
            self.stdout.write('')

        # Find events with null or empty images
        events_to_delete = Event.objects.filter(image__isnull=True) | Event.objects.filter(image='')
        event_count = events_to_delete.count()

        # Find artists with null or empty images
        artists_to_delete = Artist.objects.filter(image__isnull=True) | Artist.objects.filter(image='')
        artist_count = artists_to_delete.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'[DRY-RUN] Would delete {event_count} events with empty images')
            )
            self.stdout.write(
                self.style.WARNING(f'[DRY-RUN] Would delete {artist_count} artists with empty images')
            )
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('[DRY-RUN SUMMARY]'))
            self.stdout.write(f'Total records: {event_count + artist_count} (no DB changes made)')
        else:
            # Delete events
            if event_count > 0:
                events_to_delete.delete()
                self.stdout.write(self.style.SUCCESS(f'🗑️  Deleted {event_count} events with empty images'))

            # Delete artists
            if artist_count > 0:
                artists_to_delete.delete()
                self.stdout.write(self.style.SUCCESS(f'🗑️  Deleted {artist_count} artists with empty images'))

            # Final count
            final_event_count = Event.objects.count()
            final_artist_count = Artist.objects.count()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('✨ CLEANUP COMPLETE ✨'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(f'🗑️  Deleted {event_count} events')
            self.stdout.write(f'🗑️  Deleted {artist_count} artists')
            self.stdout.write(f'📈 Remaining events: {final_event_count}')
            self.stdout.write(f'📈 Remaining artists: {final_artist_count}')
            self.stdout.write(self.style.SUCCESS('=' * 60))
