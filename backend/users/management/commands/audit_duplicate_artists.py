"""
List artists whose normalized names appear more than once (e.g. duplicate "Taylor Swift" rows).

Run on production (SSH / shell):
  python manage.py audit_duplicate_artists

If the Sell dropdown uses artist_id=A but the USA event is linked to artist_id=B, fix in Django Admin:
  Events → edit event → set Artist to the same row as in the dropdown.
Or merge duplicates manually (reassign events, then delete spare artist).
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from users.models import Artist


class Command(BaseCommand):
    help = 'Print groups of artists with the same case-insensitive trimmed name (possible duplicates).'

    def handle(self, *args, **options):
        groups = defaultdict(list)
        for a in Artist.objects.all().only('id', 'name'):
            key = (a.name or '').strip().lower()
            groups[key].append(a)

        dupes = [(k, v) for k, v in groups.items() if len(v) > 1 and k]
        if not dupes:
            self.stdout.write(self.style.SUCCESS('No duplicate artist names found (case-insensitive).'))
            return

        self.stdout.write(self.style.WARNING(f'Found {len(dupes)} name(s) with multiple Artist rows:\n'))
        for key, rows in sorted(dupes, key=lambda x: x[0]):
            ids = ', '.join(f'{r.id}' for r in rows)
            self.stdout.write(f'  "{rows[0].name}" → ids [{ids}] ({len(rows)} rows)')
