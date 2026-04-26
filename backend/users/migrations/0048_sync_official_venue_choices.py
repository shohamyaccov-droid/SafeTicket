from django.db import migrations, models


OFFICIAL_VENUES = [
    ('היכל מנורה מבטחים', 'תל אביב'),
    ('אצטדיון בלומפילד', 'תל אביב'),
    ('פיס ארנה ירושלים', 'ירושלים'),
]


def seed_official_venues(apps, schema_editor):
    Venue = apps.get_model('users', 'Venue')
    for name, city in OFFICIAL_VENUES:
        Venue.objects.get_or_create(name=name, city=city)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0047_remove_student_day_events'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='venue',
            field=models.CharField(
                choices=[
                    ('היכל מנורה מבטחים', 'היכל מנורה מבטחים'),
                    ('אצטדיון בלומפילד', 'אצטדיון בלומפילד'),
                    ('פיס ארנה ירושלים', 'פיס ארנה ירושלים'),
                    ('סמי עופר', 'סמי עופר'),
                    ('בארבי תל אביב', 'בארבי תל אביב'),
                    ('אחר', 'אחר'),
                ],
                default='היכל מנורה מבטחים',
                help_text='Venue name',
                max_length=255,
            ),
        ),
        migrations.RunPython(seed_official_venues, noop_reverse),
    ]
