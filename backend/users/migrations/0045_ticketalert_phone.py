# Generated manually for waitlist lead capture

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0044_order_payme_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketalert',
            name='phone',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Optional phone for SMS / WhatsApp follow-up',
                max_length=32,
            ),
        ),
    ]
