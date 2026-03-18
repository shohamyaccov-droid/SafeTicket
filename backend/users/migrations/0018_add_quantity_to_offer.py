# Generated migration for adding quantity field to Offer model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0017_offer'),
    ]

    operations = [
        migrations.AddField(
            model_name='offer',
            name='quantity',
            field=models.IntegerField(default=1, help_text='Number of tickets in this offer'),
        ),
    ]
