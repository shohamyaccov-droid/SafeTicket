from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0031_order_pending_payment_and_hold'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_confirm_token',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
