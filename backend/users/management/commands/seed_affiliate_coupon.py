from django.core.management.base import BaseCommand

from users.coupons import seed_demo_affiliate_coupon


class Command(BaseCommand):
    help = 'Create/update demo affiliate partner + AFFILIATE5 coupon (5/5/5 fee split).'

    def handle(self, *args, **options):
        coupon = seed_demo_affiliate_coupon()
        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded coupon {coupon.code} for affiliate {coupon.affiliate.name} '
                f'(buyer_discount={coupon.buyer_discount_rate}, '
                f'affiliate={coupon.affiliate_commission_rate}, platform={coupon.platform_net_rate})'
            )
        )
