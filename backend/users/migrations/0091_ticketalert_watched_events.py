from django.db import migrations, models


def backfill_watched_events(apps, schema_editor):
    TicketAlert = apps.get_model('users', 'TicketAlert')
    Through = TicketAlert.watched_events.through
    rows = []
    for alert in TicketAlert.objects.filter(event_id__isnull=False).only('id', 'event_id').iterator():
        rows.append(Through(ticketalert_id=alert.id, event_id=alert.event_id))
    if rows:
        Through.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0090_seller_reminder'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketalert',
            name='full_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Buyer name from waitlist signup',
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name='ticketalert',
            name='watched_events',
            field=models.ManyToManyField(
                blank=True,
                help_text='All event dates this waitlist registration should match',
                related_name='waitlist_alerts',
                to='users.event',
            ),
        ),
        migrations.RunPython(backfill_watched_events, migrations.RunPython.noop),
    ]
