"""
One-off cleanup: remove all Orders and reset every non-active Ticket back to "active".

Usage:
    python manage.py reset_test_data              # dry-run (shows counts only)
    python manage.py reset_test_data --execute    # actually wipes the data
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from users.reset_test_data_core import get_reset_test_data_preview, run_reset_test_data


class Command(BaseCommand):
    help = "Delete all Orders and reset sold/reserved Ticket rows back to active."

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Actually perform the reset. Omit to run in dry-run / preview mode.",
        )

    def handle(self, *args, **options):
        execute = options["execute"]

        preview = get_reset_test_data_preview()

        self.stdout.write("")
        self.stdout.write("=== reset_test_data preview ===")
        self.stdout.write(f"  Orders to delete          : {preview['order_count']}")
        self.stdout.write(f"  Offers to delete          : {preview['offer_count']}")
        self.stdout.write(f"  Seller payouts to delete  : {preview['seller_payout_count']}")
        self.stdout.write(f"  Wallet ledger rows delete : {preview['wallet_transaction_count']}")
        self.stdout.write(f"  Tickets to reset to active: {preview['dirty_ticket_count']}")
        self.stdout.write(f"  Active tickets with qty=0 : {preview['held_ticket_count']}")
        self.stdout.write("")

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run complete. Re-run with --execute to apply changes."
                )
            )
            return

        result = run_reset_test_data()

        self.stdout.write(self.style.SUCCESS("=== reset_test_data complete ==="))
        self.stdout.write(self.style.SUCCESS(f"  Offers deleted            : {result['offers_deleted']}"))
        self.stdout.write(self.style.SUCCESS(f"  Seller payouts deleted    : {result['seller_payouts_deleted']}"))
        self.stdout.write(self.style.SUCCESS(f"  Wallet ledger rows deleted: {result['wallet_transactions_deleted']}"))
        self.stdout.write(self.style.SUCCESS(f"  Orders deleted            : {result['orders_deleted']}"))
        self.stdout.write(self.style.SUCCESS(f"  Wallet balances reset     : {result['wallet_balances_reset']}"))
        self.stdout.write(self.style.SUCCESS(f"  Tickets reset to active   : {result['tickets_reset']}"))
        self.stdout.write(self.style.SUCCESS(f"  Ticket qty restored to 1  : {result['qty_restored']}"))
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Admin dashboard stats will now show zero revenue and zero tickets sold."
            )
        )
