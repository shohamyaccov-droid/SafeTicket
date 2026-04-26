from django.db import migrations


VENUE_SECTIONS = {
    ('היכל מנורה מבטחים', 'תל אביב'): [
        *[str(n) for n in range(101, 113)],
        *[str(n) for n in range(301, 313)],
    ],
    ('אצטדיון בלומפילד', 'תל אביב'): [
        *[str(n) for n in range(201, 210)],
        *[str(n) for n in range(214, 217)],
        *[str(n) for n in range(221, 230)],
        *[str(n) for n in range(234, 237)],
        *[str(n) for n in range(301, 339)],
        *[str(n) for n in range(404, 407)],
        *[str(n) for n in range(419, 432)],
    ],
    ('פיס ארנה ירושלים', 'ירושלים'): [
        *[str(n) for n in range(101, 123)],
        *[str(n) for n in range(301, 331)],
    ],
}


def seed_sections(apps, schema_editor):
    Venue = apps.get_model('users', 'Venue')
    VenueSection = apps.get_model('users', 'VenueSection')
    for (venue_name, city), section_names in VENUE_SECTIONS.items():
        venue, _ = Venue.objects.get_or_create(name=venue_name, city=city)
        for section_name in section_names:
            VenueSection.objects.get_or_create(venue=venue, name=section_name)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0048_sync_official_venue_choices'),
    ]

    operations = [
        migrations.RunPython(seed_sections, noop_reverse),
    ]
