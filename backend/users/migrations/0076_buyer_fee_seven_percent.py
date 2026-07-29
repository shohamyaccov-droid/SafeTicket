from decimal import Decimal

from django.db import migrations, models


def forwards(apps, schema_editor):
    GlobalFeeSettings = apps.get_model('users', 'GlobalFeeSettings')
    obj = GlobalFeeSettings.objects.filter(pk=1).first()
    if not obj:
        return
    discount = obj.buyer_coupon_discount_percent or Decimal('0.00')
    affiliate = obj.affiliate_commission_percent or Decimal('0.00')
    base = Decimal('7.00')
    if discount > base:
        discount = Decimal('0.00')
    if discount + affiliate > base:
        affiliate = max(Decimal('0.00'), base - discount)
    GlobalFeeSettings.objects.filter(pk=1).update(
        base_buyer_fee_percent=base,
        buyer_coupon_discount_percent=discount,
        affiliate_commission_percent=affiliate,
    )


def backwards(apps, schema_editor):
    GlobalFeeSettings = apps.get_model('users', 'GlobalFeeSettings')
    obj = GlobalFeeSettings.objects.filter(pk=1).first()
    if not obj:
        return
    GlobalFeeSettings.objects.filter(pk=1).update(
        base_buyer_fee_percent=Decimal('12.00'),
        affiliate_commission_percent=Decimal('5.00'),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0075_offer_completed_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='globalfeesettings',
            name='affiliate_commission_percent',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('2.00'),
                help_text='Affiliate share of listing base when an affiliate coupon applies (default 2%).',
                max_digits=6,
            ),
        ),
        migrations.AlterField(
            model_name='globalfeesettings',
            name='base_buyer_fee_percent',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('7.00'),
                help_text='Buyer service fee with no coupon (default 7%).',
                max_digits=6,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
