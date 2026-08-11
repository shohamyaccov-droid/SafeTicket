"""
Reconcile paid orders that were manually marked paid without inventory/payout side-effects.

Usage:
  python manage.py reconcile_paid_order 132
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import Order
from users.payments import _fulfill_paid_order_ticket_rows
from users.payout_ledger import ensure_seller_payout_for_order


class Command(BaseCommand):
    help = 'Mark tickets sold + ensure SellerPayout for an already-paid order.'

    def add_arguments(self, parser):
        parser.add_argument('order_id', type=int)

    def handle(self, *args, **options):
        order_id = options['order_id']
        order = Order.objects.filter(pk=order_id).first()
        if not order:
            raise CommandError(f'Order {order_id} not found')
        if order.status != 'paid':
            raise CommandError(f'Order {order_id} status={order.status!r} (expected paid)')

        with transaction.atomic():
            locked = Order.objects.select_for_update().get(pk=order_id)
            _fulfill_paid_order_ticket_rows(locked)
            payout = ensure_seller_payout_for_order(locked)

        self.stdout.write(self.style.SUCCESS(
            f'Order #{order_id} reconciled. payout_id={getattr(payout, "pk", None)} '
            f'net={getattr(payout, "net_payout", None)}'
        ))
