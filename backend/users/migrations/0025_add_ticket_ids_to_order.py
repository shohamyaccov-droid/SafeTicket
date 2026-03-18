# Generated migration for multi-ticket download support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0024_add_offer_round_and_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='ticket_ids',
            field=models.JSONField(default=list, blank=True, help_text='List of ticket IDs in this order (for multi-ticket downloads)'),
        ),
    ]
