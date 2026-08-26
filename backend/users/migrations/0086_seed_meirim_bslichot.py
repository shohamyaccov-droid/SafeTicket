from django.db import migrations


def seed_forward(apps, schema_editor):
    from users.meirim_bslichot import seed_meirim_bslichot

    seed_meirim_bslichot(attach_poster=True)


def seed_reverse(apps, schema_editor):
    Event = apps.get_model('users', 'Event')
    Artist = apps.get_model('users', 'Artist')
    Event.objects.filter(artist__slug='meirim-bslichot', name='מאירים בסליחות').delete()
    Artist.objects.filter(slug='meirim-bslichot', name='מאירים בסליחות').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0085_event_ascii_artist_date_slug'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
