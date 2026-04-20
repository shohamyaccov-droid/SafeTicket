"""
Hard-reset stadium-mapped catalog rows (Eyal Golan / Bloomfield / Menora) and optionally re-seed.

  cd backend
  python manage.py prune_stadium_catalog --dry-run
  python manage.py prune_stadium_catalog --reseed

On Render (Shell, against production DATABASE_URL):

  cd backend && python manage.py prune_stadium_catalog --reseed

Frontend maps (no backend geometry files — client-side only):
  Bloomfield: frontend/src/utils/bloomfieldSectionGeometry.js
  Menora: frontend/src/components/InteractiveMenoraMap.jsx (inline paths)
  Jerusalem: frontend/src/utils/jerusalemArenaGeometry.js
"""
from __future__ import annotations

import sys
from pathlib import Path

from django.core.management.base import BaseCommand

# seed_production.py lives in backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


class Command(BaseCommand):
    help = (
        'Delete events matching Eyal Golan, Bloomfield, or Menora; optionally run full production seed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print matching events only; do not delete or reseed.',
        )
        parser.add_argument(
            '--reseed',
            action='store_true',
            help='After delete, run seed_production catalog (QA user, artists, 4 launch + 2 waitlist).',
        )

    def handle(self, *args, **options):
        from seed_production import (
            assert_catalog_event_inventory,
            prune_stadium_catalog_refresh_targets,
            _seed_all,
        )

        dry = options['dry_run']
        reseed = options['reseed']

        result = prune_stadium_catalog_refresh_targets(dry_run=dry)
        if dry:
            for row in result:
                self.stdout.write(f"  would delete id={row['id']} reasons={row['reasons']}")
            self.stdout.write(self.style.WARNING(f'Dry-run: {len(result)} event(s); no DB changes.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Deleted {len(result)} event(s). IDs: {[r["id"] for r in result]}'))

        if reseed:
            self.stdout.write('Running full production seed (skip legacy prune already done for stadium rows)...')
            _seed_all(skip_prune=True)
            assert_catalog_event_inventory()
            self.stdout.write(self.style.SUCCESS('Reseed complete; catalog inventory assertions passed.'))
        else:
            self.stdout.write(
                self.style.WARNING('No --reseed: run `python manage.py prune_stadium_catalog --reseed` or `python seed_production.py` to rebuild catalog.')
            )
