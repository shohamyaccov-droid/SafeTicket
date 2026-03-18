# Generated manually for adding detailed seating fields to Ticket model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_add_is_together_to_ticket'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='section',
            field=models.CharField(blank=True, help_text='Section/Block/Gate (e.g., Gate 11)', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='row',
            field=models.CharField(blank=True, help_text='Row number (e.g., Row 12)', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='seat_numbers',
            field=models.CharField(blank=True, help_text='Seat numbers (e.g., 12-15). Not shown to buyers before purchase.', max_length=200, null=True),
        ),
    ]






