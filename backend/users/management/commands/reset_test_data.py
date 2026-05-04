"""
One-off cleanup: remove all Orders and reset every non-active Ticket back to "active".

Usage:
    python manage.py reset_test_data              # dry-run (shows counts only)
    python manage.py reset_test_data --execute    # actually wipes the data
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction


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

        # Import inside handle so Django app registry is fully loaded
        from users.models import Offer, Order, Ticket

        # ── counts before ─────────────────────────────────────────────────────
        order_count = Order.objects.count()
        offer_count = Offer.objects.count()

        dirty_statuses = ["sold", "pending_payout", "paid_out", "reserved"]
        dirty_tickets = Ticket.objects.filter(status__in=dirty_statuses)
        dirty_ticket_count = dirty_tickets.count()

        held_tickets = Ticket.objects.filter(available_quantity__lt=1, status="active")
        held_ticket_count = held_tickets.count()

        self.stdout.write("")
        self.stdout.write("=== reset_test_data preview ===")
        self.stdout.write(f"  Orders to delete          : {order_count}")
        self.stdout.write(f"  Offers to delete          : {offer_count}")
        self.stdout.write(f"  Tickets to reset to active: {dirty_ticket_count}")
        self.stdout.write(f"  Active tickets with qty=0 : {held_ticket_count}")
        self.stdout.write("")

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run complete. Re-run with --execute to apply changes."
                )
            )
            return

        # ── execute ───────────────────────────────────────────────────────────
        with transaction.atomic():
            # 1. Delete all offers first (FK referenced by Order.related_offer)
            offer_del, _ = Offer.objects.all().delete()

            # 2. Delete all orders
            order_del, _ = Order.objects.all().delete()

            # 3. Reset sold/reserved/payout tickets → active
            ticket_reset = dirty_tickets.update(
                status="active",
                reserved_by=None,
                reserved_at=None,
                reservation_email=None,
            )

            # 4. Restore available_quantity for tickets that were held
            #    (held_ticket.available_quantity was decremented; set back to 1 minimum)
            qty_fixed = 0
            for t in Ticket.objects.filter(available_quantity=0, status="active"):
                t.available_quantity = 1
                t.save(update_fields=["available_quantity", "updated_at"])
                qty_fixed += 1

        self.stdout.write(self.style.SUCCESS("=== reset_test_data complete ==="))
        self.stdout.write(self.style.SUCCESS(f"  Offers deleted            : {offer_del}"))
        self.stdout.write(self.style.SUCCESS(f"  Orders deleted            : {order_del}"))
        self.stdout.write(self.style.SUCCESS(f"  Tickets reset to active   : {ticket_reset}"))
        self.stdout.write(self.style.SUCCESS(f"  Ticket qty restored to 1  : {qty_fixed}"))
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Admin dashboard stats will now show zero revenue and zero tickets sold."
            )
        )
