# Data migration: remove Technion Student Day catalog row (seed no longer includes it).

from django.db import migrations


def remove_student_day_events(apps, schema_editor):
    Event = apps.get_model('users', 'Event')
    Event.objects.filter(name__contains='יום הסטודנט').delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0046_nuke_events_reseed_catalog'),
    ]

    operations = [
        migrations.RunPython(remove_student_day_events, noop_reverse),
    ]
