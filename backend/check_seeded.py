#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import django

# Fix console encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safeticket.settings')
django.setup()

from users.models import Event, Artist

print('==== SEEDING VERIFICATION ====\n')

print(f'Total Events: {Event.objects.count()}')
print(f'Total Artists: {Artist.objects.count()}')

recent_events = Event.objects.order_by('-created_at')[:10]
print(f'\nRecent Events ({len(recent_events)}):')
for e in recent_events:
    date_str = e.date.strftime('%d.%m.%Y') if e.date else 'N/A'
    print(f'  - {e.name} ({date_str})')

hysteria_events = Event.objects.filter(name__icontains='היסטריה').count()
other_new = Event.objects.filter(name__icontains='אמפי').count()
print(f'\n==== COUNTS ====')
print(f'Hysteria events: {hysteria_events}')
print(f'Amphy/Recent events: {other_new}')
