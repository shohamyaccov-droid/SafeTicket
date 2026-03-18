# Migration: add is_email_verified to User (default True for existing users)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0025_add_ticket_ids_to_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='is_email_verified',
            field=models.BooleanField(default=True, help_text='Email verified via OTP (False for new unverified accounts)'),
        ),
    ]
