"""
Seed verified real-world events for 2026 including:
- פאר טסי (Sept 24)
- פסטיבל התמר 2026 (Sept 28 - Oct 2, multi-day)
- NEXT 2026 (Ramat Gan & Jerusalem)
- פסטיבל הג'אז בים האדום 2026 (November)

Usage:
  python manage.py seed_2026_real_events                    # Seed events
  python manage.py seed_2026_real_events --dry-run         # Show what would be seeded
  python manage.py seed_2026_real_events --wipe            # Wipe and reseed

Prevents duplicates via update_or_create on (name, date)
Handles timezone-aware datetime objects (Asia/Jerusalem)
"""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Artist, Event, Venue, VenueSection

User = get_user_model()

TZ_IL = ZoneInfo("Asia/Jerusalem")


class Command(BaseCommand):
    help = "Seed real 2026 events to TradeTix database with deduplication"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be seeded without making changes',
        )
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Delete all existing events before seeding (CAREFUL!)',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        wipe = options.get('wipe', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] No database changes will be made.'))
            self.stdout.write('')

        if wipe:
            if dry_run:
                self.stdout.write(self.style.WARNING('[DRY-RUN] Would delete all events'))
            else:
                event_count = Event.objects.count()
                Event.objects.all().delete()
                self.stdout.write(
                    self.style.WARNING(f'🗑️  Wiped {event_count} existing events')
                )

        # Define events
        events_data = [
            {
                'name': 'פאר טסי | חנן בן ארי',
                'date': datetime(2026, 9, 24, 20, 45, tzinfo=TZ_IL),
                'venue': 'אמפי MAX',
                'city': 'תל אביב',
                'artists': ['פאר טסי', 'חנן בן ארי'],
                'category': 'concert',
                'country': 'IL',
            },
            {
                'name': 'פסטיבל התמר 2026 - ערב 1: חגיגת פתיחה',
                'date': datetime(2026, 9, 28, 19, 0, tzinfo=TZ_IL),
                'venue': 'היכל התרבות של הטבע - מצדה',
                'city': 'מצדה',
                'artists': ['מארינה מקסימיליאן', 'מירי מסיקה', 'קרן פלס', 'אברהם טל', 'מוש בן ארי', 'אתניקס'],
                'category': 'festival',
                'country': 'IL',
            },
            {
                'name': 'פסטיבל התמר 2026 - ערב 2: פנטזיה מדברית',
                'date': datetime(2026, 9, 29, 19, 0, tzinfo=TZ_IL),
                'venue': 'היכל התרבות של הטבע - מצדה',
                'city': 'מצדה',
                'artists': ['פול טראנק', 'דודו טסה', 'שרית חדד', 'רביד פלוטניק', 'פטרה'],
                'category': 'festival',
                'country': 'IL',
                'status': 'סולד אאוט',
            },
            {
                'name': 'פסטיבל התמר 2026 - מופע זריחה: שרים החלונות הגבוהים',
                'date': datetime(2026, 9, 29, 6, 30, tzinfo=TZ_IL),
                'venue': 'פסגת המצדה',
                'city': 'מצדה',
                'artists': ['אסף אמדורסקי', 'שלומי שבן', 'יעל קראוס'],
                'category': 'festival',
                'country': 'IL',
            },
            {
                'name': 'פסטיבל התמר 2026 - ערב 3: מסע בין כוכבים',
                'date': datetime(2026, 9, 30, 19, 0, tzinfo=TZ_IL),
                'venue': 'היכל התרבות של הטבע - מצדה',
                'city': 'מצדה',
                'artists': ['ברי סחרוף', 'נגה ארז', 'אודיה', 'טונה'],
                'category': 'festival',
                'country': 'IL',
            },
            {
                'name': 'פסטיבל התמר 2026 - מופע זריחה: Mita Gami B2B Adam Ten',
                'date': datetime(2026, 9, 30, 6, 30, tzinfo=TZ_IL),
                'venue': 'פסגת המצדה',
                'city': 'מצדה',
                'artists': ['מיטה גאמי', 'אדם טן'],
                'category': 'festival',
                'country': 'IL',
                'status': 'סולד אאוט',
            },
            {
                'name': 'פסטיבל התמר 2026 - ערב 4: מרעידים את המדבר',
                'date': datetime(2026, 10, 1, 19, 0, tzinfo=TZ_IL),
                'venue': 'היכל התרבות של הטבע - מצדה',
                'city': 'מצדה',
                'artists': ['ג\'ימבו ג\'יי', 'לירן דנינו', 'היהודים', 'בן צור', 'עדן בן זקן'],
                'category': 'festival',
                'country': 'IL',
            },
            {
                'name': 'פסטיבל התמר 2026 - מופע זריחה: התקווה 6',
                'date': datetime(2026, 10, 2, 6, 30, tzinfo=TZ_IL),
                'venue': 'פסגת המצדה',
                'city': 'מצדה',
                'artists': ['התקווה 6', 'יוני ויצמן', 'דרוויש'],
                'category': 'festival',
                'country': 'IL',
            },
            {
                'name': 'NEXT 2026 - אצטדיון רמת גן',
                'date': datetime(2026, 10, 22, 20, 0, tzinfo=TZ_IL),
                'venue': 'אצטדיון ר"ג',
                'city': 'רמת גן',
                'artists': ['אודיה', 'אושר כהן', 'בן צור', 'עומר אדם', 'עידן עמדי', 'ריטה'],
                'category': 'concert',
                'country': 'IL',
            },
            {
                'name': 'NEXT 2026 - פיס ארנה ירושלים',
                'date': datetime(2026, 12, 7, 20, 0, tzinfo=TZ_IL),
                'venue': 'פיס ארנה י-ם',
                'city': 'ירושלים',
                'artists': ['אודיה', 'אושר כהן', 'בן צור', 'עומר אדם', 'עידן עמדי', 'ריטה'],
                'category': 'concert',
                'country': 'IL',
            },
            {
                'name': 'פסטיבל הג\'אז בים האדום 2026',
                'date': datetime(2026, 11, 11, 18, 0, tzinfo=TZ_IL),
                'ends_at': datetime(2026, 11, 14, 23, 59, tzinfo=TZ_IL),
                'venue': 'אילת',
                'city': 'אילת',
                'artists': [],  # Jazz festival - multiple artists, not primary focus
                'category': 'festival',
                'country': 'IL',
            },
        ]

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

            # Use update_or_create to prevent duplicates
            artists = event_data.pop('artists', [])
            ends_at = event_data.pop('ends_at', None)

            try:
                event, created = Event.objects.update_or_create(
                    name=event_name,
                    date=event_date,
                    defaults={
                        'venue': event_data['venue'],
                        'city': event_data['city'],
                        'category': event_data.get('category', 'concert'),
                        'country': event_data.get('country', 'IL'),
                        'status': event_data.get('status', 'פעיל'),
                        'age_restriction': 'ללא הגבלה',
                        'ends_at': ends_at,
                    }
                )

                if created:
                    created_count += 1
                    status_msg = self.style.SUCCESS(f'✅ Created')
                else:
                    updated_count += 1
                    status_msg = self.style.WARNING(f'♻️  Updated')

                self.stdout.write(f"{status_msg}: {event_name} ({event_date.strftime('%Y-%m-%d %H:%M')})")

                # Optionally link primary artist if provided
                if artists:
                    # Get or create artists
                    for artist_name in artists[:1]:  # Link first artist as primary
                        artist, _ = Artist.objects.get_or_create(name=artist_name)
                        event.artist = artist
                        event.save(update_fields=['artist'])

            except Exception as e:
                skipped_count += 1
                self.stderr.write(
                    self.style.ERROR(f'❌ Failed: {event_name} - {str(e)}')
                )

        # Query database to verify final count
        if not dry_run:
            final_event_count = Event.objects.count()
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(self.style.SUCCESS('✨ SEEDING COMPLETE ✨'))
            self.stdout.write(self.style.SUCCESS('=' * 60))
            self.stdout.write(f'📊 Created:     {created_count} new events')
            self.stdout.write(f'♻️  Updated:     {updated_count} existing events')
            self.stdout.write(f'⏭️  Skipped:     {skipped_count} with errors')
            self.stdout.write(f'📈 Total in DB: {final_event_count} events')
            self.stdout.write(self.style.SUCCESS('=' * 60))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'[DRY-RUN SUMMARY]'))
            self.stdout.write(f'Would create {created_count} events (no DB changes made)')
