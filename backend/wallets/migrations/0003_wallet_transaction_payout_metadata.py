from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0058_ticket_alert_user_artist'),
        ('wallets', '0002_backfill_user_wallets'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallettransaction',
            name='transaction_type',
            field=models.CharField(
                choices=[
                    ('SALE_CREDIT', 'Seller sale credit'),
                    ('WITHDRAWAL', 'Manual seller payout withdrawal'),
                ],
                db_index=True,
                default='SALE_CREDIT',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='wallettransaction',
            name='seller_payout',
            field=models.ForeignKey(
                blank=True,
                help_text='Seller payout row this wallet ledger entry belongs to.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='wallet_transactions',
                to='users.sellerpayout',
            ),
        ),
        migrations.AddField(
            model_name='wallettransaction',
            name='note',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
