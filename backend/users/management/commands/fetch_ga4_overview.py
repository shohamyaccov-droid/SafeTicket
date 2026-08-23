from django.core.management.base import BaseCommand, CommandError

from users.ga4_service import Ga4ApiError, Ga4AuthError, Ga4ConfigError, fetch_ga4_last_7_days


class Command(BaseCommand):
    help = (
        'Fetch GA4 sessions, active users, and page views for the last 7 days '
        'using Application Default Credentials (no JSON key file).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--property-id',
            dest='property_id',
            default='',
            help='Numeric GA4 property ID (overrides GA4_PROPERTY_ID). Not the G- measurement ID.',
        )

    def handle(self, *args, **options):
        property_id = (options.get('property_id') or '').strip() or None
        self.stdout.write('Requesting GA4 last-7-days overview via ADC...')
        try:
            summary = fetch_ga4_last_7_days(property_id=property_id)
        except Ga4ConfigError as exc:
            raise CommandError(str(exc)) from exc
        except Ga4AuthError as exc:
            raise CommandError(str(exc)) from exc
        except Ga4ApiError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Property: {summary['property_id']}")
        self.stdout.write(
            f"Range: {summary['date_range']['start_date']} -> {summary['date_range']['end_date']}"
        )
        self.stdout.write(f"Sessions:     {summary['sessions']}")
        self.stdout.write(f"Active users: {summary['active_users']}")
        self.stdout.write(f"Page views:   {summary['page_views']}")
        self.stdout.write(self.style.SUCCESS('GA4 overview fetched successfully.'))
