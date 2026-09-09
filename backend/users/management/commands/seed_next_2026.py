"""
Seed NEXT 2026 festival events to TradeTix database.

NEXT 2026 is a multi-venue, multi-date music festival across Israel.

Venues:
- אצטדיון ר"ג (Ramat Gan Stadium) - Oct 8-18
- פיס ארנה י-ם (Jerusalem Arena) - Dec 3-10

Usage:
  python manage.py seed_next_2026                    # Seed events
  python manage.py seed_next_2026 --dry-run         # Show what would be seeded
  python manage.py seed_next_2026 --wipe            # Wipe and reseed

Deduplication: Uses update_or_create on (name, date) to prevent duplicates.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event

TZ_IL = ZoneInfo("Asia/Jerusalem")


class Command(BaseCommand):
    help = "Seed NEXT 2026 festival events (Ramat Gan + Jerusalem)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be seeded without making changes',
        )
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Delete all NEXT events before seeding (CAREFUL!)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        wipe = options.get('wipe', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] No database changes will be made.'))
            self.stdout.write('')

        # Wipe existing NEXT events if requested
        if wipe:
            if dry_run:
                self.stdout.write(self.style.WARNING('[DRY-RUN] Would delete all NEXT events'))
            else:
                next_events = Event.objects.filter(name__contains='NEXT 2026')
                count = next_events.count()
                next_events.delete()
                self.stdout.write(self.style.WARNING(f'🗑️  Wiped {count} existing NEXT events'))

        # Ensure NEXT artist exists
        if not dry_run:
            artist, created = Artist.objects.get_or_create(name='NEXT')
            if created:
                self.stdout.write(self.style.SUCCESS('✅ Created artist: NEXT'))
            else:
                self.stdout.write(self.style.WARNING('♻️  Artist NEXT already exists'))
        else:
            artist = None

        # Define NEXT 2026 events
        # Ramat Gan Stadium (אצטדיון ר"ג)
        ramat_gan_dates = [
            8, 10, 11, 12, 13, 14, 15, 17, 18, 22,  # October dates
        ]

        # Jerusalem Arena (פיס ארנה י-ם)
        jerusalem_dates = [
            (12, 3),   # December 3
            (12, 5),   # December 5
            (12, 6),   # December 6
            (12, 7),   # December 7
            (12, 9),   # December 9
            (12, 10),  # December 10
        ]

        events_data = []

        # Ramat Gan Stadium events
        for day in ramat_gan_dates:
            events_data.append({
                'name': f'NEXT 2026 - אצטדיון ר"ג ({day}.10)',
                'date': datetime(2026, 10, day, 20, 0, tzinfo=TZ_IL),
                'venue': 'אצטדיון ר"ג',
                'city': 'רמת גן',
                'category': 'festival',
                'country': 'IL',
                'artist': artist,
            })

        # Jerusalem Arena events
        for month, day in jerusalem_dates:
            events_data.append({
                'name': f'NEXT 2026 - פיס ארנה י-ם ({day}.{month})',
                'date': datetime(2026, month, day, 20, 0, tzinfo=TZ_IL),
                'venue': 'פיס ארנה י-ם',
                'city': 'ירושלים',
                'category': 'festival',
                'country': 'IL',
                'artist': artist,
            })

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for event_data in events_data:
            event_name = event_data['name']
            event_date = event_data['date']

            if dry_run:
                self.stdout.write(f"Would create: {event_name} ({event_date.strftime('%Y-%m-%d %H:%M')})")
                created_count += 1
                continue

            try:
                event, created = Event.objects.update_or_create(
                    name=event_name,
                    date=event_date,
                    defaults={
                        'venue': event_data['venue'],
                        'city': event_data['city'],
                        'category': event_data['category'],
                        'country': event_data['country'],
                        'status': 'פעיל',
                        'age_restriction': 'ללא הגבלה',
                        'artist': event_data['artist'],
                    }
                )

                if created:
                    created_count += 1
                    status_msg = self.style.SUCCESS(f'✅ Created')
                else:
                    updated_count += 1
                    status_msg = self.style.WARNING(f'♻️  Updated')

                self.stdout.write(f"{status_msg}: {event_name}")

            except Exception as e:
                skipped_count += 1
                self.stderr.write(
                    self.style.ERROR(f'❌ Failed: {event_name} - {str(e)}')
                )

        # Summary
        if not dry_run:
            final_event_count = Event.objects.filter(name__contains='NEXT 2026').count()
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('✨ NEXT 2026 SEEDING COMPLETE ✨'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(f'📊 Created:     {created_count} new events')
            self.stdout.write(f'♻️  Updated:     {updated_count} existing events')
            self.stdout.write(f'⏭️  Skipped:     {skipped_count} with errors')
            self.stdout.write(f'📍 Ramat Gan:   10 dates (Oct 8-22)')
            self.stdout.write(f'📍 Jerusalem:   6 dates (Dec 3-10)')
            self.stdout.write(f'📈 Total NEXT events: {final_event_count}')
            self.stdout.write(self.style.SUCCESS('=' * 60))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'[DRY-RUN SUMMARY]'))
            self.stdout.write(f'Would create {created_count} NEXT 2026 events (no DB changes made)')
