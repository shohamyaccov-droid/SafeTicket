from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0070_ticket_status_taken'),
    ]

    operations = [
        migrations.AddField(
            model_name='coupon',
            name='discount_amount',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text=(
                    'Fixed amount deducted from checkout total; '
                    '0 keeps percentage-based coupon pricing.'
                ),
                max_digits=10,
            ),
        ),
        migrations.AddConstraint(
            model_name='coupon',
            constraint=models.CheckConstraint(
                condition=models.Q(discount_amount__gte=Decimal('0.00')),
                name='users_coupon_discount_amount_nonnegative',
            ),
        ),
    ]
