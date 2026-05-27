"""
Data fix: Bloomfield concert events (e.g. אייל גולן) use concert venue label + map sections.

Ensures Event.venue = אצטדיון בלומפילד (הופעות) and seeds the 49 concert block names on the
Bloomfield Venue place so sell/checkout section pickers match BloomfieldConcertMap.
"""

from django.db import migrations
from django.db.models import Q

VENUE_BLOOMFIELD_CONCERT = 'אצטדיון בלומפילד (הופעות)'
VENUE_BLOOMFIELD_PLACE = 'אצטדיון בלומפילד'
VENUE_CITY = 'תל אביב'

BLOOMFIELD_CONCERT_SECTION_NAMES = [
    *[f'A{n}' for n in range(1, 7)],
    *[f'B{n}' for n in range(1, 6)],
    *[f'C{n}' for n in range(1, 6)],
    *[str(n) for n in range(101, 107)],
    *[str(n) for n in range(42, 48)],
    *[f'{n}A' for n in range(70, 81)],
    *[f'{n}B' for n in range(71, 81)],
]


def fix_bloomfield_concert_catalog(apps, schema_editor):
    Event = apps.get_model('users', 'Event')
    Venue = apps.get_model('users', 'Venue')
    VenueSection = apps.get_model('users', 'VenueSection')

    venue_obj, _ = Venue.objects.get_or_create(name=VENUE_BLOOMFIELD_PLACE, city=VENUE_CITY)
    for section_name in BLOOMFIELD_CONCERT_SECTION_NAMES:
        VenueSection.objects.get_or_create(venue=venue_obj, name=section_name)

    concert_filter = Q(category__iexact='concert') & (
        Q(venue__icontains='בלומפילד')
        | Q(name__icontains='אייל גולן')
        | Q(name__icontains='בלומפילד')
    )
    Event.objects.filter(concert_filter).update(
        venue=VENUE_BLOOMFIELD_CONCERT,
        category='concert',
        venue_place=venue_obj,
    )

    # Eyal Golan at Bloomfield by name even if category was mis-set.
    Event.objects.filter(
        Q(name__icontains='אייל גולן') & Q(name__icontains='בלומפילד')
    ).update(
        venue=VENUE_BLOOMFIELD_CONCERT,
        category='concert',
        venue_place=venue_obj,
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0054_alter_event_venue_bloomfield_concerts'),
    ]

    operations = [
        migrations.RunPython(fix_bloomfield_concert_catalog, noop_reverse),
    ]
