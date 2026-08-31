"""Resend the buyer ticket/receipt email for a paid order (missed webhook mail).

Usage:
  python manage.py send_order_receipt --order-id 123
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from users.models import Order
from users.utils.emails import send_paid_order_receipt


class Command(BaseCommand):
    help = 'Send (or resend) the ticket/receipt email for a paid order.'

    def add_arguments(self, parser):
        parser.add_argument('--order-id', type=int, required=True, help='Order primary key.')

    def handle(self, *args, **options):
        order_id = options['order_id']
        order = Order.objects.select_related('user').filter(pk=order_id).first()
        if not order:
            raise CommandError(f'Order #{order_id} not found.')
        if order.status not in ('paid', 'completed'):
            raise CommandError(f'Order #{order_id} status={order.status!r} (expected paid/completed).')
        self.stdout.write(f'Sending receipt for order #{order_id}...')
        ok, message = send_paid_order_receipt(order, source='send_order_receipt')
        if not ok:
            raise CommandError(message)
        self.stdout.write(self.style.SUCCESS(message))
