# Generated manually for Order price integrity fields

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0027_alter_order_ticket_ids_alter_user_is_email_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='related_offer',
            field=models.ForeignKey(
                blank=True,
                help_text='Accepted offer this order fulfilled, if any',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='orders',
                to='users.offer',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='final_negotiated_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Seller bundle price: offer amount if negotiated, else asking × quantity',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='buyer_service_fee',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Amount buyer pays beyond final_negotiated_price (typically platform fee)',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='total_paid_by_buyer',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Total charged to buyer (mirrors total_amount when set)',
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='net_seller_revenue',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Amount seller receives for this sale (negotiated base; no extra commission here)',
                max_digits=10,
                null=True,
            ),
        ),
    ]
