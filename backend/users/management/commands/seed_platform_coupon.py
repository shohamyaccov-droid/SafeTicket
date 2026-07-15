from django.core.management.base import BaseCommand

from users.coupons import seed_platform_coupon


class Command(BaseCommand):
    help = (
        'Create/update platform-owned TRADETIX5 coupon '
        '(buyer 10% fee / affiliate 0% / platform 10% net).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--code',
            default='TRADETIX5',
            help='Coupon code to seed (default: TRADETIX5)',
        )

    def handle(self, *args, **options):
        coupon = seed_platform_coupon(code=options['code'])
        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded platform coupon {coupon.code} '
                f'(type={coupon.coupon_type}, affiliate={coupon.affiliate_id}, '
                f'buyer_discount={coupon.buyer_discount_rate}, '
                f'affiliate={coupon.affiliate_commission_rate}, '
                f'platform={coupon.platform_net_rate})'
            )
        )
