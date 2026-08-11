"""
Dump ticket/PDF details for an order (admin recovery).

Usage (on Render shell or local with DATABASE_URL):
  python manage.py dump_order_tickets 132
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from users.models import Order, Ticket


class Command(BaseCommand):
    help = 'Print ticket row/seat/PDF paths for an order (for manual buyer delivery).'

    def add_arguments(self, parser):
        parser.add_argument('order_id', type=int)

    def handle(self, *args, **options):
        order_id = options['order_id']
        order = (
            Order.objects.filter(pk=order_id)
            .select_related('ticket', 'ticket__event', 'user')
            .first()
        )
        if not order:
            raise CommandError(f'Order {order_id} not found')

        buyer = getattr(order.user, 'email', None) or order.guest_email or '—'
        self.stdout.write(f'ORDER {order.pk}')
        self.stdout.write(f'  status={order.status} payme_status={order.payme_status}')
        self.stdout.write(f'  buyer={buyer}')
        self.stdout.write(f'  event_name={order.event_name!r}')
        self.stdout.write(f'  total_amount={order.total_amount} total_paid_by_buyer={order.total_paid_by_buyer}')
        self.stdout.write(f'  payme_transaction_id={order.payme_transaction_id!r}')
        self.stdout.write(f'  ticket_ids={order.ticket_ids!r} ticket_id={order.ticket_id} held_ticket_id={order.held_ticket_id}')

        ids: list[int] = []
        for raw in list(order.ticket_ids or []):
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        for extra in (order.ticket_id, order.held_ticket_id):
            if extra and int(extra) not in ids:
                ids.append(int(extra))

        tickets = (
            Ticket.objects.filter(pk__in=ids)
            .select_related('event', 'seller', 'venue_section')
            .order_by('id')
        )
        if not tickets.exists():
            self.stdout.write(self.style.ERROR('No tickets linked to this order.'))
            return

        self.stdout.write(f'TICKET_COUNT={tickets.count()}')
        for t in tickets:
            event_name = t.event.name if t.event else (t.event_name or '—')
            venue = t.event.venue_display_name() if t.event else (t.venue or '—')
            section = t.get_section_display() if hasattr(t, 'get_section_display') else (t.section or '')
            row = t.seat_row or t.row or t.row_number or '—'
            seat = t.seat_numbers or t.seat_number or '—'
            pdf_path = ''
            pdf_url = ''
            try:
                if t.pdf_file:
                    try:
                        pdf_path = t.pdf_file.path
                    except Exception:
                        pdf_path = str(t.pdf_file.name)
                    try:
                        pdf_url = t.pdf_file.url
                    except Exception:
                        pdf_url = ''
            except Exception as exc:
                pdf_path = f'ERR:{exc}'

            self.stdout.write('---')
            self.stdout.write(f'ticket_id={t.pk} status={t.status}')
            self.stdout.write(f'  event={event_name!r} venue={venue!r}')
            self.stdout.write(f'  section={section!r} row={row!r} seat={seat!r}')
            self.stdout.write(f'  asking_price={t.asking_price} seller={getattr(t.seller, "email", None)}')
            self.stdout.write(f'  pdf_path={pdf_path}')
            self.stdout.write(f'  pdf_url={pdf_url}')
            self.stdout.write(f'  pdf_name={getattr(t.pdf_file, "name", None)}')
