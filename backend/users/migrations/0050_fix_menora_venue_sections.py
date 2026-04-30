from django.db import migrations


MENORA_VENUE_NAMES = (
    'היכל מנורה מבטחים',
    'מנורה מבטחים',
    'מנורה ארנה',
    'Menora Arena',
)

MENORA_SECTION_NAMES = [
    f'{number} תחתון' for number in range(1, 13)
] + [
    f'{number} עליון' for number in range(1, 13)
]

BAD_MENORA_SECTION_NAMES = {
    *[str(number) for number in range(101, 113)],
    *[str(number) for number in range(301, 313)],
}


def fix_menora_sections(apps, schema_editor):
    Venue = apps.get_model('users', 'Venue')
    VenueSection = apps.get_model('users', 'VenueSection')

    menora_venues = Venue.objects.filter(name__in=MENORA_VENUE_NAMES)
    for venue in menora_venues:
        VenueSection.objects.filter(venue=venue, name__in=BAD_MENORA_SECTION_NAMES).delete()
        for section_name in MENORA_SECTION_NAMES:
            VenueSection.objects.get_or_create(venue=venue, name=section_name)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0049_seed_official_venue_sections'),
    ]

    operations = [
        migrations.RunPython(fix_menora_sections, noop_reverse),
    ]
