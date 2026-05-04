# Data migration: seed four May 2026 sports fixtures (Bloomfield + Menora).
# Mirrors logic from management command seed_sports_matches; uses apps.get_model only.
# Category is model field ``sport`` (covers both football and basketball).

from datetime import datetime

from django.db import migrations
from zoneinfo import ZoneInfo

TZ_IL = ZoneInfo('Asia/Jerusalem')

VENUE_BLOOMFIELD = 'אצטדיון בלומפילד'
VENUE_MENORA = 'היכל מנורה מבטחים'
CITY_TLV = 'תל אביב'


def _dt(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, 0, tzinfo=TZ_IL)


def _bloomfield_sections():
    return (
        [str(n) for n in range(201, 210)]
        + [str(n) for n in range(214, 217)]
        + [str(n) for n in range(221, 230)]
        + [str(n) for n in range(234, 237)]
        + [str(n) for n in range(301, 339)]
        + [str(n) for n in range(404, 407)]
        + [str(n) for n in range(419, 432)]
    )


def _menora_sections():
    return [f'{n} תחתון' for n in range(1, 13)] + [f'{n} עליון' for n in range(1, 13)]


def _ensure_venue(apps, name, city, section_names):
    Venue = apps.get_model('users', 'Venue')
    VenueSection = apps.get_model('users', 'VenueSection')
    venue, _ = Venue.objects.get_or_create(name=name, city=city)
    for section_name in section_names:
        VenueSection.objects.get_or_create(venue=venue, name=section_name)
    return venue


def seed_four_sports_events(apps, schema_editor):
    Event = apps.get_model('users', 'Event')

    events_spec = (
        {
            'name': 'מכבי תל אביב נגד מכבי חיפה - מחזור 33',
            'date': _dt(2026, 5, 13, 20, 30),
            'venue_key': VENUE_BLOOMFIELD,
            'venue_city': CITY_TLV,
            'sections': _bloomfield_sections(),
            'home_team': 'מכבי תל אביב',
            'away_team': 'מכבי חיפה',
            'tournament': 'ליגת העל בכדורגל',
        },
        {
            'name': 'מכבי תל אביב נגד בית"ר ירושלים - מחזור 34',
            'date': _dt(2026, 5, 16, 20, 30),
            'venue_key': VENUE_BLOOMFIELD,
            'venue_city': CITY_TLV,
            'sections': _bloomfield_sections(),
            'home_team': 'מכבי תל אביב',
            'away_team': 'בית"ר ירושלים',
            'tournament': 'ליגת העל בכדורגל',
        },
        {
            'name': 'מכבי תל אביב נגד הפועל ב"ש',
            'date': _dt(2026, 5, 6, 19, 0),
            'venue_key': VENUE_MENORA,
            'venue_city': CITY_TLV,
            'sections': _menora_sections(),
            'home_team': 'מכבי תל אביב',
            'away_team': 'הפועל באר שבע',
            'tournament': 'ליגת העל בכדורסל',
        },
        {
            'name': 'מכבי תל אביב נגד עירוני קרית אתא',
            'date': _dt(2026, 5, 11, 21, 5),
            'venue_key': VENUE_MENORA,
            'venue_city': CITY_TLV,
            'sections': _menora_sections(),
            'home_team': 'מכבי תל אביב',
            'away_team': 'עירוני קרית אתא',
            'tournament': 'ליגת העל בכדורסל',
        },
    )

    for spec in events_spec:
        venue_obj = _ensure_venue(
            apps,
            spec['venue_key'],
            spec['venue_city'],
            spec['sections'],
        )
        Event.objects.get_or_create(
            name=spec['name'],
            defaults={
                'date': spec['date'],
                'venue': spec['venue_key'],
                'venue_place': venue_obj,
                'city': spec['venue_city'],
                'category': 'sport',
                'status': 'פעיל',
                'country': 'IL',
                'home_team': spec['home_team'],
                'away_team': spec['away_team'],
                'tournament': spec['tournament'],
                'high_demand': True,
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0052_analyticsevent'),
    ]

    operations = [
        migrations.RunPython(seed_four_sports_events, noop_reverse),
    ]
