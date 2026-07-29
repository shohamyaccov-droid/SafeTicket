from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0077_seller_bonus_banner_copy'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='eligible_for_bonus',
            field=models.BooleanField(
                default=False,
                help_text='Whether this ticket qualifies for the seller bonus when sold.',
            ),
        ),
    ]
