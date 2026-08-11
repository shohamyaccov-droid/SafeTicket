"""Ensure Render start/build scripts run critical backup before migrations and seeds."""
from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase

_REPO_ROOT = Path(__file__).resolve().parents[3]
_START_RENDER = _REPO_ROOT / 'backend' / 'start_render.sh'
_BUILD_RENDER = _REPO_ROOT / 'build_render.sh'


class RenderDeployHooksTests(SimpleTestCase):
    def test_start_render_runs_migrate_and_menora_seeds(self):
        self.assertTrue(_START_RENDER.is_file(), f'missing {_START_RENDER}')
        text = _START_RENDER.read_text(encoding='utf-8')
        self.assertIn('python manage.py backup_critical_data', text)
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
        # Destructive wipe must never be invoked on boot.
        self.assertNotIn('manage.py reset_test_data', text)
        self.assertNotIn('manage.py wipe_events_catalog', text)
        self.assertNotIn('manage.py prune_stadium_catalog', text)
        self.assertNotIn('manage.py reset_all_tickets', text)
        # Failsafe: backup must run before migrate and before seed_production
        backup_idx = text.index('python manage.py backup_critical_data')
        migrate_idx = text.index('python manage.py migrate --noinput')
        seed_idx = text.index('python seed_production.py')
        self.assertLess(backup_idx, migrate_idx)
        self.assertLess(migrate_idx, seed_idx)
        # taken lock must run after dummy seed re-creates active inventory
        dummy_idx = text.index('python manage.py seed_dummy_tickets')
        taken_idx = text.index('python manage.py mark_tickets_taken')
        fomo_idx = text.index('python manage.py seed_taken_tickets')
        self.assertGreater(taken_idx, dummy_idx)
        self.assertGreater(fomo_idx, taken_idx)

    def test_build_render_backs_up_before_migrate(self):
        self.assertTrue(_BUILD_RENDER.is_file(), f'missing {_BUILD_RENDER}')
        text = _BUILD_RENDER.read_text(encoding='utf-8')
        self.assertIn('python manage.py backup_critical_data', text)
        self.assertIn('python manage.py migrate --noinput', text)
        self.assertNotIn('manage.py reset_test_data', text)
        self.assertNotIn('manage.py wipe_events_catalog', text)
        backup_idx = text.index('python manage.py backup_critical_data')
        migrate_idx = text.index('python manage.py migrate --noinput')
        self.assertLess(backup_idx, migrate_idx)

    def test_render_yaml_start_command_is_safe(self):
        yaml_path = _REPO_ROOT / 'render.yaml'
        self.assertTrue(yaml_path.is_file(), f'missing {yaml_path}')
        text = yaml_path.read_text(encoding='utf-8')
        self.assertIn('startCommand: bash start_render.sh', text)
        self.assertNotIn('manage.py reset_test_data', text)
        self.assertNotIn('manage.py wipe_events_catalog', text)
