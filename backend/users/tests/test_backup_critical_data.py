"""Tests for production wipe lock and critical JSON backup failsafe."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from users.models import Artist, Event, Order, Ticket, User
from users.production_safety import is_production_locked, refuse_destructive
from users.reset_test_data_core import run_reset_test_data


class ProductionSafetyTests(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_unlocked_when_debug_and_not_render(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('RENDER', None)
            self.assertFalse(is_production_locked())

    @override_settings(DEBUG=True)
    def test_locked_when_render_even_if_debug(self):
        with mock.patch.dict(os.environ, {'RENDER': 'true'}, clear=False):
            self.assertTrue(is_production_locked())
            with self.assertRaises(ImproperlyConfigured):
                refuse_destructive('unit-test-wipe')

    @override_settings(DEBUG=False)
    def test_locked_when_not_debug(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('RENDER', None)
            with mock.patch('users.production_safety._running_tests', return_value=False):
                self.assertTrue(is_production_locked())


class BackupCriticalDataTests(TestCase):
    def test_backup_writes_json_with_orders_tickets_users_events(self):
        seller = User.objects.create_user(
            username='backup_seller',
            email='backup_seller@example.com',
            password='x',
            role='seller',
        )
        buyer = User.objects.create_user(
            username='backup_buyer',
            email='backup_buyer@example.com',
            password='x',
        )
        artist = Artist.objects.create(name='Backup Artist')
        event = Event.objects.create(
            artist=artist,
            name='Backup Event',
            date=timezone.now(),
            venue='Arena',
            city='TLV',
            country='IL',
            status='פעיל',
        )
        ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            pdf_file='tickets/pdfs/test.pdf',
            status='active',
            verification_status='מאומת',
            available_quantity=1,
        )
        Order.objects.create(
            user=buyer,
            ticket=ticket,
            ticket_ids=[ticket.id],
            status='paid',
            total_amount=Decimal('115.00'),
            currency='ILS',
            quantity=1,
        )

        out_dir = Path(tempfile.mkdtemp(prefix='critical_backup_test_'))
        self.addCleanup(lambda: shutil.rmtree(out_dir, ignore_errors=True))
        out_file = out_dir / 'test_backup.json'
        call_command('backup_critical_data', output=str(out_file), no_cloudinary=True)

        self.assertTrue(out_file.is_file())
        payload = json.loads(out_file.read_text(encoding='utf-8'))
        models = {row['model'] for row in payload}
        self.assertIn('users.order', models)
        self.assertIn('users.ticket', models)
        self.assertIn('users.event', models)
        self.assertIn('users.user', models)

        meta = json.loads(out_file.with_suffix(out_file.suffix + '.meta.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(meta['counts'].get('users.Order', 0), 1)


class ResetTestDataProductionLockTests(TestCase):
    @override_settings(DEBUG=False)
    def test_reset_test_data_refuses_when_not_debug(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('RENDER', None)
            with mock.patch('users.production_safety._running_tests', return_value=False):
                with self.assertRaises(ImproperlyConfigured):
                    run_reset_test_data()

    @override_settings(DEBUG=False)
    def test_reset_test_data_command_soft_skips_when_locked(self):
        """Stray deploy hooks must not crash boot — command exits 0 without wiping."""
        with mock.patch.dict(os.environ, {'RENDER': 'true'}, clear=False):
            # Should not raise even though lock is active.
            call_command('reset_test_data', execute=True)
            call_command('reset_test_data')
