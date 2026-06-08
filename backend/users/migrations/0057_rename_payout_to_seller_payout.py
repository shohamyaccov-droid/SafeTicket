# Generated manually — rename Payout → SellerPayout with 15% platform fee fields

from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _remap_payout_status_values(apps, schema_editor):
    SellerPayout = apps.get_model('users', 'SellerPayout')
    mapping = {
        'PENDING': 'pending',
        'PROCESSING': 'pending',
        'PAID': 'transferred',
    }
    for old, new in mapping.items():
        SellerPayout.objects.filter(payout_status=old).update(payout_status=new)


def _recompute_fifteen_percent_fees(apps, schema_editor):
    """Recalculate platform_fee / net_payout as 15% of total_paid for existing rows."""
    SellerPayout = apps.get_model('users', 'SellerPayout')
    rate = Decimal('0.15')
    for row in SellerPayout.objects.all().iterator():
        total = Decimal(row.total_paid).quantize(Decimal('0.01'))
        fee = (total * rate).quantize(Decimal('0.01'))
        net = (total - fee).quantize(Decimal('0.01'))
        SellerPayout.objects.filter(pk=row.pk).update(
            platform_fee=fee,
            net_payout=net,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0056_seller_payout_ledger_and_bank_fields'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='payout',
            name='users_payou_status_8a94a6_idx',
        ),
        migrations.RemoveIndex(
            model_name='payout',
            name='users_payou_seller__a2e6c0_idx',
        ),
        migrations.RenameModel(
            old_name='Payout',
            new_name='SellerPayout',
        ),
        migrations.RenameField(
            model_name='sellerpayout',
            old_name='total_sale_amount',
            new_name='total_paid',
        ),
        migrations.RenameField(
            model_name='sellerpayout',
            old_name='platform_commission',
            new_name='platform_fee',
        ),
        migrations.RenameField(
            model_name='sellerpayout',
            old_name='status',
            new_name='payout_status',
        ),
        migrations.RenameField(
            model_name='sellerpayout',
            old_name='paid_at',
            new_name='transferred_at',
        ),
        migrations.AlterField(
            model_name='sellerpayout',
            name='platform_fee',
            field=models.DecimalField(
                decimal_places=2,
                help_text='TradeTix platform fee (15% of total_paid)',
                max_digits=10,
            ),
        ),
        migrations.AlterField(
            model_name='sellerpayout',
            name='total_paid',
            field=models.DecimalField(
                decimal_places=2,
                help_text='Total amount the buyer paid via PayMe',
                max_digits=10,
            ),
        ),
        migrations.AlterField(
            model_name='sellerpayout',
            name='payout_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('transferred', 'Transferred'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='sellerpayout',
            name='transferred_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the net payout was transferred to the seller',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='sellerpayout',
            name='seller',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='seller_payouts',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name='sellerpayout',
            index=models.Index(fields=['payout_status', '-created_at'], name='users_seller_payout_status_idx'),
        ),
        migrations.AddIndex(
            model_name='sellerpayout',
            index=models.Index(fields=['seller', 'payout_status'], name='users_seller_payout_seller_idx'),
        ),
        migrations.RunPython(_remap_payout_status_values, migrations.RunPython.noop),
        migrations.RunPython(_recompute_fifteen_percent_fees, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='sellerpayout',
            options={
                'ordering': ['-created_at'],
                'verbose_name': 'Seller payout',
                'verbose_name_plural': 'Seller payouts',
            },
        ),
    ]
