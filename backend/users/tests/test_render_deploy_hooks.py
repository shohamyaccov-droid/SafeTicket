"""Ensure Render start script runs migrations and high-demand Menora seed commands."""
from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase

_REPO_ROOT = Path(__file__).resolve().parents[3]
_START_RENDER = _REPO_ROOT / 'backend' / 'start_render.sh'


class RenderDeployHooksTests(SimpleTestCase):
    def test_start_render_runs_migrate_and_menora_seeds(self):
        self.assertTrue(_START_RENDER.is_file(), f'missing {_START_RENDER}')
        text = _START_RENDER.read_text(encoding='utf-8')
        self.assertIn('python manage.py migrate --noinput', text)
        self.assertIn('python manage.py seed_odiya_osher_hope_event', text)
        self.assertIn('python manage.py seed_eyal_golan_menora', text)
        self.assertIn('python manage.py seed_itay_levi_caesarea', text)
        self.assertIn('python manage.py deactivate_affiliate5_coupon', text)
        self.assertIn('python manage.py seed_platform_coupon', text)
        self.assertIn('python manage.py seed_dummy_tickets', text)
        self.assertIn('python manage.py mark_tickets_taken', text)
        self.assertIn('python manage.py seed_taken_tickets', text)
        self.assertIn('RUN_DUMMY_SEED', text)
        self.assertIn('RUN_FOMO_SEED', text)
        self.assertNotIn('python manage.py seed_affiliate_coupon', text)
        self.assertNotIn('flush --no-input', text)
        self.assertNotIn('wipe_events_catalog', text)
        # taken lock must run after dummy seed re-creates active inventory
        seed_idx = text.index('python manage.py seed_dummy_tickets')
        taken_idx = text.index('python manage.py mark_tickets_taken')
        fomo_idx = text.index('python manage.py seed_taken_tickets')
        self.assertGreater(taken_idx, seed_idx)
        self.assertGreater(fomo_idx, taken_idx)
