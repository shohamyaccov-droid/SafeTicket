"""
Delete all marketplace catalog rows: Order -> Offer -> Ticket -> TicketAlert -> Event.
Does not seed data. Use when the platform should show zero events (homepage empty state).

Usage:
  python manage.py wipe_events_catalog
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Event, Offer, Order, Ticket, TicketAlert


class Command(BaseCommand):
    help = "Remove all orders, offers, tickets, ticket alerts, and events (no seed)."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "Deleting Order -> Offer -> Ticket -> TicketAlert -> Event ..."
            )
        )
        with transaction.atomic():
            n_orders = Order.objects.count()
            n_offers = Offer.objects.count()
            n_tickets = Ticket.objects.count()
            n_alerts = TicketAlert.objects.count()
            n_events = Event.objects.count()

            Order.objects.all().delete()
            Offer.objects.all().delete()
            Ticket.objects.all().delete()
            TicketAlert.objects.all().delete()
            Event.objects.all().delete()

        self.stdout.write(
            f"Removed: orders={n_orders}, offers={n_offers}, tickets={n_tickets}, "
            f"alerts={n_alerts}, events={n_events}."
        )

        ec = Event.objects.count()
        tc = Ticket.objects.count()
        if ec != 0 or tc != 0:
            self.stdout.write(
                self.style.ERROR(f"FAILED: Event.count={ec}, Ticket.count={tc} (expected 0).")
            )
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Catalog empty: Event=0, Ticket=0."))
