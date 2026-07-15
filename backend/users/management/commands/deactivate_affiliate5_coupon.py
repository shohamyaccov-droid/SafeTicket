"""
One-off / idempotent: deactivate (or delete) the demo AFFILIATE5 coupon.

Safe to run on every deploy — if the coupon is already gone/inactive, exits cleanly.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Coupon


class Command(BaseCommand):
    help = 'Deactivate demo coupon AFFILIATE5 so it cannot be redeemed.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Hard-delete the coupon row instead of setting is_active=False.',
        )
        parser.add_argument(
            '--code',
            default='AFFILIATE5',
            help='Coupon code to deactivate (default: AFFILIATE5).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        code = (options['code'] or 'AFFILIATE5').strip().upper()
        qs = Coupon.objects.filter(code__iexact=code)
        if not qs.exists():
            self.stdout.write(self.style.WARNING(f'Coupon {code} not found — nothing to do.'))
            return

        if options['delete']:
            count, _ = qs.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted coupon {code} ({count} row(s)).'))
            return

        updated = qs.update(is_active=False)
        self.stdout.write(
            self.style.SUCCESS(f'Deactivated coupon {code} (is_active=False, rows={updated}).')
        )
