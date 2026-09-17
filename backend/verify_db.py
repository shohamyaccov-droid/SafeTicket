#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import django

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Event, Artist

print('==== CURRENT DATABASE STATE ====\n')

# Check high-demand events
high_demand = Event.objects.filter(high_demand=True).order_by('-date')[:20]
print(f'High-Demand Events: {high_demand.count()}')
for e in high_demand:
    date_str = e.date.strftime('%d.%m.%Y') if e.date else 'N/A'
    image_status = 'HAS_IMAGE' if e.image else 'NO_IMAGE'
    print(f'  - {e.name} ({date_str}) [{image_status}]')

# Check specific artists we need
target_artists = [
    'פאר טסי וחנן בן ארי',
    'ישי ריבו',
    'אזיליה בנקס',
    'מור',
    'איתי לוי',
    'נועם בתן',
    'היסטריה'
]

print(f'\n==== TARGET ARTISTS ====')
for artist_name in target_artists:
    artist = Artist.objects.filter(name=artist_name).first()
    if artist:
        events_count = artist.events.count()
        print(f'{artist_name}: {events_count} events')
        for ev in artist.events.order_by('date')[:3]:
            date_str = ev.date.strftime('%d.%m.%Y') if ev.date else 'N/A'
            image_status = 'IMG' if ev.image else 'NO_IMG'
            print(f'    - {ev.name} ({date_str}) [{image_status}]')
    else:
        print(f'{artist_name}: NOT_FOUND')
