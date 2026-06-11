# Generated manually for TicketAlert user/artist subscriptions

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0057_rename_payout_to_seller_payout'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='ticketalert',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='ticketalert',
            name='artist',
            field=models.ForeignKey(
                blank=True,
                help_text='Subscribe to all future shows for this artist',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ticket_alerts',
                to='users.artist',
            ),
        ),
        migrations.AddField(
            model_name='ticketalert',
            name='user',
            field=models.ForeignKey(
                blank=True,
                help_text='Registered user (optional — guests use email only)',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='ticket_alerts',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='ticketalert',
            name='event',
            field=models.ForeignKey(
                blank=True,
                help_text='Subscribe to a specific event',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='alerts',
                to='users.event',
            ),
        ),
        migrations.AddIndex(
            model_name='ticketalert',
            index=models.Index(fields=['artist', 'notified'], name='users_ticke_artist__8a1f2d_idx'),
        ),
        migrations.AddConstraint(
            model_name='ticketalert',
            constraint=models.UniqueConstraint(
                condition=models.Q(('event__isnull', False)),
                fields=('event', 'email'),
                name='unique_ticket_alert_event_email',
            ),
        ),
        migrations.AddConstraint(
            model_name='ticketalert',
            constraint=models.UniqueConstraint(
                condition=models.Q(('artist__isnull', False), ('event__isnull', True)),
                fields=('artist', 'email'),
                name='unique_ticket_alert_artist_email',
            ),
        ),
    ]
