from django.core.management.base import BaseCommand

from users.order_cleanup import cancel_abandoned_pending_payment_orders


class Command(BaseCommand):
    help = 'Cancel abandoned pending_payment orders and release held ticket inventory.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=15,
            help='Cancel pending_payment orders older than this many minutes. Default: 15.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be cancelled without changing the database.',
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        dry_run = options['dry_run']
        if minutes < 1:
            raise SystemExit('--minutes must be at least 1')

        result = cancel_abandoned_pending_payment_orders(
            older_than_minutes=minutes,
            dry_run=dry_run,
        )

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f'{prefix}inspected={result.inspected} '
                    f'cancelled={result.cancelled} '
                    f'restored_quantity={result.restored_quantity} '
                    f'released_tickets={result.released_tickets} '
                    f'skipped_payme_completed={result.skipped_payme_completed}'
                )
            )
        )
