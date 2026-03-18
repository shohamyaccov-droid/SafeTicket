# Generated migration for adding available_quantity field to Ticket model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_add_seating_details_to_ticket'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='available_quantity',
            field=models.IntegerField(default=1, help_text='Number of tickets available for sale (1-10)'),
        ),
    ]






