# Data migration: pre-launch catalog reset — delete all Event/Ticket rows, then re-seed from seed_production.

from django.db import migrations


def nuke_events_and_tickets_then_reseed(apps, schema_editor):
    Ticket = apps.get_model('users', 'Ticket')
    Event = apps.get_model('users', 'Event')
    Ticket.objects.all().delete()
    Event.objects.all().delete()

    from seed_production import run_after_total_wipe

    run_after_total_wipe()


def noop_reverse(apps, schema_editor):
    """Irreversible: cannot restore wiped marketplace data."""
    pass


class Migration(migrations.Migration):
    """
    Runs automatically on deploy (migrate during build/start). No Render Shell required.

    Deletes every Event and Ticket, then repopulates exactly 7 catalog events via seed_production.
    """

    atomic = False  # seed performs HTTP image fetches; avoid holding one DB transaction open

    dependencies = [
        ('users', '0045_ticketalert_phone'),
    ]

    operations = [
        migrations.RunPython(nuke_events_and_tickets_then_reseed, noop_reverse),
    ]
