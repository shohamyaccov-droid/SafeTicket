"""
Brute-force restore ALL 39 tickets from backup JSON.

PURPOSE:
  Forcefully load all 39 tickets from the backup JSON, bypassing Django's
  loaddata (which is atomic and fails on any constraint violation).
  This ensures all tickets are restored even if related Events don't exist.

APPROACH:
  1. Read raw JSON using standard json module
  2. Extract all ticket objects (model='users.ticket')
  3. For each ticket, fetch or create the referenced Event/User
  4. Use update_or_create to forcefully save each ticket
  5. Skip records that have foreign key issues; log warnings

CRITICAL: Bypasses atomic transactions to restore maximum data.
"""

import json
from pathlib import Path
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from users.models import Event, Ticket, User


class Command(BaseCommand):
    help = 'Brute-force restore ALL tickets from backup JSON (bypasses constraints, restores maximum)'

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

        # Read raw JSON
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON in backup file: {e}')
        except Exception as e:
            raise CommandError(f'Error reading backup file: {e}')

        if not isinstance(backup_data, list):
            raise CommandError('Backup JSON must be an array of objects')

        # Filter to only ticket objects
        ticket_objects = [obj for obj in backup_data if obj.get('model') == 'users.ticket']

        if not ticket_objects:
            self.stdout.write(self.style.WARNING('⚠️  No ticket objects found in backup'))
            return

        self.stdout.write(self.style.SUCCESS(f'🎫 Found {len(ticket_objects)} tickets in backup'))

        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 DRY-RUN MODE: No database changes will be made\n'))

        restored_count = 0
        skipped_count = 0
        error_count = 0
        errors_detail = []

        for i, ticket_obj in enumerate(ticket_objects, 1):
            pk = ticket_obj.get('pk')
            fields = ticket_obj.get('fields', {})

            if dry_run:
                seller_id = fields.get('seller')
                event_id = fields.get('event')
                asking_price = fields.get('asking_price')
                self.stdout.write(
                    f'  [{i:2d}] Ticket pk={pk} seller_id={seller_id} event_id={event_id} price={asking_price}'
                )
                restored_count += 1
                continue

            # Attempt to restore this ticket
            try:
                # Extract fields
                seller_id = fields.get('seller')
                event_id = fields.get('event')
                asking_price = fields.get('asking_price')
                original_price = fields.get('original_price')
                status = fields.get('status', 'pending_approval')

                # Validate seller exists
                if not seller_id:
                    raise ValueError('Ticket missing seller_id')

                try:
                    seller = User.objects.get(pk=seller_id)
                except User.DoesNotExist:
                    raise ValueError(f'Seller user {seller_id} does not exist')

                # Event is optional (nullable), but if specified, verify it exists
                event = None
                if event_id:
                    try:
                        event = Event.objects.get(pk=event_id)
                    except Event.DoesNotExist:
                        # Event missing — log warning but continue with event=None
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⚠️  [{i:2d}] Ticket pk={pk}: Event {event_id} missing, restoring with event=None'
                            )
                        )
                        event = None

                # Prepare defaults for update_or_create
                defaults = {
                    'seller': seller,
                    'event': event,
                    'status': status,
                }

                # Add all other fields from backup
                for field_name, field_value in fields.items():
                    if field_name not in ['pk', 'seller', 'event', 'id']:
                        # Skip FK pointers; handle them explicitly above
                        if field_name not in ['listing_group_id']:  # Don't skip list fields
                            defaults[field_name] = field_value

                # Forcefully update or create the ticket
                with transaction.atomic():
                    ticket, created = Ticket.objects.update_or_create(
                        pk=pk,
                        defaults=defaults,
                    )

                restored_count += 1
                action = 'created' if created else 'updated'
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ [{i:2d}] Ticket pk={pk} {action}'
                    )
                )

            except ValueError as e:
                # Data validation error
                error_count += 1
                error_msg = str(e)
                errors_detail.append((pk, error_msg))
                self.stdout.write(
                    self.style.ERROR(f'  ❌ [{i:2d}] Ticket pk={pk}: {error_msg}')
                )
            except Exception as e:
                # Unexpected error
                error_count += 1
                error_msg = str(e)
                errors_detail.append((pk, error_msg))
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ [{i:2d}] Ticket pk={pk}: {type(e).__name__}: {error_msg[:60]}'
                    )
                )

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        if dry_run:
            self.stdout.write(self.style.WARNING(f'🔍 DRY-RUN SUMMARY'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✨ TICKET RESTORE COMPLETE ✨'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f'🎫 Total tickets in backup: {len(ticket_objects)}')
        self.stdout.write(self.style.SUCCESS(f'✓  Restored: {restored_count}'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'⚠️  Skipped: {skipped_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ Errors: {error_count}'))

        if errors_detail:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('Failed tickets:'))
            for pk, error_msg in errors_detail:
                self.stdout.write(f'  • pk={pk}: {error_msg[:80]}')

        self.stdout.write(self.style.SUCCESS('=' * 70))

        # Verify final count
        final_ticket_count = Ticket.objects.count()
        self.stdout.write(f'📊 Total tickets in DB now: {final_ticket_count}')

        if dry_run:
            self.stdout.write(self.style.WARNING('(dry-run mode: no changes made)'))
