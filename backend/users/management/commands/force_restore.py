"""
Fault-tolerant database restore from critical backup JSON.

PURPOSE:
  Restores critical marketplace data (Users, Events, Tickets, Orders) from a JSON backup,
  skipping individual records that fail (e.g., IntegrityError due to existing PKs) while
  continuing to restore all valid records. This ensures that deleted tickets are recovered
  even if some related objects already exist.

PROBLEM SOLVED:
  Standard loaddata is atomic: if ANY record fails, the entire transaction rolls back
  and NO records are restored. This leaves deleted tickets gone.

SOLUTION:
  This script uses deserialize + try/except to attempt each object individually.
  If a record fails (e.g., PK conflict), it logs a warning and moves to the next one.
  Result: All restorable records are restored; broken ones are skipped.

USAGE:
  python manage.py force_restore
  python manage.py force_restore --file path/to/custom.json
  python manage.py force_restore --dry-run
"""

import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers import deserialize
from django.db import IntegrityError, transaction


class Command(BaseCommand):
    help = 'Fault-tolerant restore from critical backup JSON (skips failed records, restores valid ones)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='',
            help='Custom backup file path (default: critical_backups/latest_critical_backup.json)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be restored without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        custom_file = (options.get('file') or '').strip()

        # Determine backup file path
        if custom_file:
            backup_path = Path(custom_file)
        else:
            backup_path = Path(settings.BASE_DIR) / 'critical_backups' / 'latest_critical_backup.json'

        if not backup_path.exists():
            raise CommandError(f'Backup file not found: {backup_path}')

        self.stdout.write(self.style.SUCCESS(f'📂 Reading backup: {backup_path}'))

        # Read and parse JSON
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON in backup file: {e}')
        except Exception as e:
            raise CommandError(f'Error reading backup file: {e}')

        if not isinstance(backup_data, list):
            raise CommandError('Backup JSON must be an array of objects')

        if not backup_data:
            self.stdout.write(self.style.WARNING('⚠️  Backup file is empty'))
            return

        self.stdout.write(self.style.SUCCESS(f'📊 Backup contains {len(backup_data)} objects'))

        # Deserialize JSON
        try:
            deserialized_objects = list(deserialize('json', json.dumps(backup_data)))
        except Exception as e:
            raise CommandError(f'Error deserializing backup: {e}')

        if not deserialized_objects:
            self.stdout.write(self.style.WARNING('⚠️  No objects to deserialize'))
            return

        self.stdout.write(self.style.SUCCESS(f'✓ Deserialized {len(deserialized_objects)} objects'))

        # Restore objects with fault tolerance
        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 DRY-RUN MODE: No database changes will be made\n'))

        restored_count = 0
        skipped_count = 0
        error_count = 0
        errors_detail = []

        for i, deserialized_obj in enumerate(deserialized_objects, 1):
            # DeserializedObject wraps the actual model instance
            obj = deserialized_obj.object
            model_label = f'{obj._meta.app_label}.{obj._meta.model_name}'
            obj_id = getattr(obj, 'pk', '?')

            if dry_run:
                self.stdout.write(f'  [{i:3d}] {model_label} pk={obj_id}')
                restored_count += 1
                continue

            # Attempt to save the object
            try:
                # Use a separate transaction for each object to prevent rollback cascade
                with transaction.atomic():
                    obj.save()
                restored_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ [{i:3d}] {model_label} pk={obj_id}')
                )
            except IntegrityError as e:
                # PK conflict or unique constraint violation — object may already exist
                error_msg = str(e)
                skipped_count += 1
                errors_detail.append((model_label, obj_id, error_msg))
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠️  [{i:3d}] {model_label} pk={obj_id} — skipped (likely already exists)'
                    )
                )
            except Exception as e:
                # Unexpected error
                error_count += 1
                error_msg = str(e)
                errors_detail.append((model_label, obj_id, error_msg))
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ [{i:3d}] {model_label} pk={obj_id} — ERROR: {type(e).__name__}: {error_msg[:60]}'
                    )
                )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        if dry_run:
            self.stdout.write(self.style.WARNING(f'🔍 DRY-RUN SUMMARY'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✨ RESTORE COMPLETE ✨'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'📦 Total objects in backup: {len(deserialized_objects)}')
        self.stdout.write(self.style.SUCCESS(f'✓  Restored: {restored_count}'))
        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Skipped (already exist): {skipped_count}')
            )
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ Errors: {error_count}')
            )

        if errors_detail and error_count > 0:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('Failed records:'))
            for model_label, obj_id, error_msg in errors_detail:
                self.stdout.write(f'  • {model_label} pk={obj_id}: {error_msg[:80]}')

        self.stdout.write(self.style.SUCCESS('=' * 70))

        # Exit status
        if dry_run:
            self.stdout.write(self.style.WARNING(f'(dry-run mode: no changes made)'))
        elif error_count > 0 and restored_count == 0:
            self.stdout.write(
                self.style.ERROR('⚠️  No records were restored. Check errors above.')
            )
            raise CommandError('Restore failed: all records failed to save')
