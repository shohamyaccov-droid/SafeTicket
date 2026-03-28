# Generated manually for EventRequest model

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0029_order_escrow_payout'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submitted_email', models.EmailField(blank=True, help_text='Email at time of submission', max_length=254)),
                ('event_hint', models.CharField(blank=True, help_text='Artist, teams, or event name', max_length=400)),
                ('details', models.TextField(help_text='Date, venue, category, or other context')),
                ('category', models.CharField(blank=True, help_text='Sell flow category (e.g. concert, sport)', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_handled', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
