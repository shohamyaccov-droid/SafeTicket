"""
Export critical marketplace rows to a JSON hard-copy before deploy/migrate/seed.

Purpose:
  Survive catastrophic DB wipes (bad seed, wrong DATABASE_URL, nuke migrations).
  The file lives *outside* Postgres — on local disk and optionally Cloudinary raw.

Usage:
  python manage.py backup_critical_data
  python manage.py backup_critical_data --output /tmp/backup.json
  python manage.py backup_critical_data --no-cloudinary

Restore (manual, after verifying the DB target):
  python manage.py loaddata path/to/critical_backup_….json
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

# Models whose rows must survive a marketplace wipe. Order matters for human readability only;
# loaddata resolves FKs via natural PK references in the dump.
CRITICAL_MODEL_LABELS = (
    'users.User',
    'users.Artist',
    'users.Venue',
    'users.VenueSection',
    'users.Event',
    'users.Ticket',
    'users.Order',
    'users.Offer',
    'users.SellerPayout',
    'users.TicketAlert',
    'wallets.UserWallet',
    'wallets.WalletTransaction',
)

KEEP_LOCAL_BACKUPS = 30


def default_backup_dir() -> Path:
    raw = (os.environ.get('CRITICAL_BACKUP_DIR') or '').strip()
    if raw:
        return Path(raw)
    configured = getattr(settings, 'CRITICAL_BACKUP_DIR', None)
    if configured:
        return Path(configured)
    return Path(settings.BASE_DIR) / 'critical_backups'


class Command(BaseCommand):
    help = (
        'Export Orders, Tickets, Users, Events (and related payout/wallet rows) '
        'to a JSON hard-copy outside Postgres.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='',
            help='Explicit output path (default: CRITICAL_BACKUP_DIR/critical_backup_<utc>.json).',
        )
        parser.add_argument(
            '--no-cloudinary',
            action='store_true',
            help='Skip Cloudinary raw upload even when USE_CLOUDINARY is enabled.',
        )
        parser.add_argument(
            '--keep',
            type=int,
            default=KEEP_LOCAL_BACKUPS,
            help=f'How many local timestamped backups to retain (default {KEEP_LOCAL_BACKUPS}).',
        )

    def handle(self, *args, **options):
        out_arg = (options.get('output') or '').strip()
        keep = max(1, int(options.get('keep') or KEEP_LOCAL_BACKUPS))
        skip_cloud = bool(options.get('no_cloudinary'))

        # Fail fast if DB is unreachable — deploy must not continue without a readable source.
        try:
            connection.ensure_connection()
        except Exception as exc:
            raise CommandError(f'Cannot connect to database for critical backup: {exc!r}') from exc

        models = []
        for label in CRITICAL_MODEL_LABELS:
            try:
                models.append(apps.get_model(label))
            except LookupError:
                self.stdout.write(self.style.WARNING(f'  skip missing model {label}'))

        counts: dict[str, int] = {}
        objects = []
        for model in models:
            try:
                qs = model.objects.all().order_by('pk')
                n = qs.count()
                counts[model._meta.label] = n
                objects.extend(list(qs.iterator(chunk_size=500)))
            except Exception as exc:
                # First deploy / pre-migrate: tables may not exist yet — still write an empty hard-copy.
                self.stdout.write(
                    self.style.WARNING(
                        f'  skip {model._meta.label} (table missing or unreadable): {exc!r}'
                    )
                )
                counts[model._meta.label] = 0

        order_count = counts.get('users.Order', 0)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup_dir = default_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)

        if out_arg:
            out_path = Path(out_arg)
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_path = backup_dir / f'critical_backup_{stamp}.json'

        payload_meta = {
            'exported_at_utc': stamp,
            'database_engine': settings.DATABASES.get('default', {}).get('ENGINE', ''),
            'database_host': settings.DATABASES.get('default', {}).get('HOST', '') or '',
            'database_name': str(settings.DATABASES.get('default', {}).get('NAME', '')),
            'counts': counts,
            'models': [m._meta.label for m in models],
        }

        # Django fixture JSON (loaddata-compatible) plus a sibling .meta.json for operators.
        fixture_json = serializers.serialize(
            'json',
            objects,
            indent=2,
            use_natural_foreign_keys=False,
            use_natural_primary_keys=False,
        )
        out_path.write_text(fixture_json, encoding='utf-8')
        meta_path = out_path.with_suffix(out_path.suffix + '.meta.json')
        meta_path.write_text(json.dumps(payload_meta, indent=2, ensure_ascii=False), encoding='utf-8')

        latest = backup_dir / 'latest_critical_backup.json'
        latest_meta = backup_dir / 'latest_critical_backup.json.meta.json'
        try:
            latest.write_text(fixture_json, encoding='utf-8')
            latest_meta.write_text(json.dumps(payload_meta, indent=2, ensure_ascii=False), encoding='utf-8')
        except OSError as exc:
            self.stdout.write(self.style.WARNING(f'Could not refresh latest_* pointers: {exc!r}'))

        size_kb = out_path.stat().st_size / 1024.0
        self.stdout.write(
            self.style.SUCCESS(
                f'[backup_critical_data] wrote {out_path} ({size_kb:.1f} KiB) '
                f'orders={order_count} tickets={counts.get("users.Ticket", 0)} '
                f'events={counts.get("users.Event", 0)} users={counts.get("users.User", 0)}'
            )
        )

        cloud_url = ''
        if not skip_cloud and getattr(settings, 'USE_CLOUDINARY', False):
            cloud_url = self._upload_cloudinary(out_path, stamp)
            if cloud_url:
                self.stdout.write(self.style.SUCCESS(f'[backup_critical_data] Cloudinary raw: {cloud_url}'))
            else:
                self.stdout.write(
                    self.style.WARNING('[backup_critical_data] Cloudinary upload skipped/failed (local file kept).')
                )

        self._prune_old_backups(backup_dir, keep=keep)

        if order_count > 0 and out_path.stat().st_size < 32:
            raise CommandError(
                f'Backup looks empty ({out_path.stat().st_size} bytes) but Order.count={order_count}. Aborting.'
            )

        self.stdout.write(
            self.style.NOTICE(
                f'[backup_critical_data] hard-copy location: {backup_dir} '
                f'(set CRITICAL_BACKUP_DIR for a Render persistent disk mount).'
            )
        )

    def _upload_cloudinary(self, path: Path, stamp: str) -> str:
        try:
            import cloudinary.uploader
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'cloudinary import failed: {exc!r}'))
            return ''
        try:
            result = cloudinary.uploader.upload(
                str(path),
                resource_type='raw',
                folder='critical_backups',
                public_id=f'critical_backup_{stamp}',
                overwrite=True,
                invalidate=True,
            )
            return str(result.get('secure_url') or result.get('url') or '')
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'Cloudinary upload error: {exc!r}'))
            return ''

    def _prune_old_backups(self, backup_dir: Path, *, keep: int) -> None:
        files = sorted(
            backup_dir.glob('critical_backup_*.json'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        # Keep meta alongside; never delete latest_* pointers here.
        for stale in files[keep:]:
            try:
                stale.unlink(missing_ok=True)
                meta = Path(str(stale) + '.meta.json')
                meta.unlink(missing_ok=True)
            except OSError:
                pass
