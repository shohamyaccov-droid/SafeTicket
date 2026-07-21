from decimal import Decimal

from django.db import migrations, models


def provision_launch_promo(apps, schema_editor):
    Coupon = apps.get_model('users', 'Coupon')
    SellerBonusCampaign = apps.get_model('users', 'SellerBonusCampaign')

    SellerBonusCampaign.objects.update_or_create(
        pk=1,
        defaults={
            'is_active': True,
            'bonus_amount': Decimal('20.00'),
            'max_sales': 100,
            'claimed_sales_count': 0,
        },
    )

    Coupon.objects.update_or_create(
        code='TIX15',
        defaults={
            'coupon_type': 'platform',
            'affiliate_id': None,
            'is_active': True,
            'discount_amount': Decimal('15.00'),
            'starts_at': None,
            'ends_at': None,
            'max_redemptions_total': None,
            'buyer_discount_rate': Decimal('0.0000'),
            'affiliate_commission_rate': Decimal('0.0000'),
            'platform_net_rate': Decimal('0.0000'),
        },
    )


def deactivate_launch_promo(apps, schema_editor):
    Coupon = apps.get_model('users', 'Coupon')
    SellerBonusCampaign = apps.get_model('users', 'SellerBonusCampaign')
    Coupon.objects.filter(code='TIX15').update(is_active=False)
    SellerBonusCampaign.objects.filter(pk=1).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0071_coupon_discount_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerpayout',
            name='seller_bonus_amount',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text=(
                    'Platform-funded promotional bonus, separate from ticket-price economics.'
                ),
                max_digits=10,
            ),
        ),
        migrations.CreateModel(
            name='SellerBonusCampaign',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('is_active', models.BooleanField(default=True)),
                (
                    'bonus_amount',
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal('20.00'),
                        max_digits=10,
                    ),
                ),
                ('max_sales', models.PositiveIntegerField(default=100)),
                ('claimed_sales_count', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Seller bonus campaign',
                'verbose_name_plural': 'Seller bonus campaign',
            },
        ),
        migrations.RunPython(provision_launch_promo, deactivate_launch_promo),
    ]
