"""
Shared reset logic: wipe Orders/Offers and restore Ticket rows to sellable state.

Used by the `reset_test_data` management command and the Django Admin superuser action.
Wallet ledger and payout rows are deleted before Orders because SellerPayout.order is protected.
"""
from __future__ import annotations

from django.db import transaction

# Ticket rows that should return to the normal marketplace listing state
DIRTY_TICKET_STATUSES = ('sold', 'pending_payout', 'paid_out', 'reserved')


def get_reset_test_data_preview():
    """Return counts for dry-run / confirmation UI (read-only)."""
    from users.models import Offer, Order, SellerPayout, Ticket
    from wallets.models import WalletTransaction

    dirty_qs = Ticket.objects.filter(status__in=DIRTY_TICKET_STATUSES)
    return {
        'order_count': Order.objects.count(),
        'offer_count': Offer.objects.count(),
        'seller_payout_count': SellerPayout.objects.count(),
        'wallet_transaction_count': WalletTransaction.objects.count(),
        'dirty_ticket_count': dirty_qs.count(),
        'held_ticket_count': Ticket.objects.filter(
            available_quantity__lt=1, status='active'
        ).count(),
    }


def run_reset_test_data():
    """
    Atomically delete all Offers and Orders, reset dirty tickets to ``active``,
    and bump ``available_quantity`` from 0 to 1 on active rows.

    Returns a dict of integers suitable for logging / admin messages.
    """
    from users.models import Offer, Order, SellerPayout, Ticket
    from users.production_safety import refuse_destructive
    from wallets.models import UserWallet, WalletTransaction

    refuse_destructive('reset_test_data')

    with transaction.atomic():
        dirty_qs = Ticket.objects.filter(status__in=DIRTY_TICKET_STATUSES)
        wallet_tx_del, _ = WalletTransaction.objects.all().delete()
        seller_payout_del, _ = SellerPayout.objects.all().delete()
        offer_del, _ = Offer.objects.all().delete()
        order_del, _ = Order.objects.all().delete()
        wallet_balances_reset = UserWallet.objects.update(
            locked_balance=0,
            available_balance=0,
        )
        ticket_reset = dirty_qs.update(
            status='active',
            reserved_by=None,
            reserved_at=None,
            reservation_email=None,
        )
        qty_fixed = 0
        for t in Ticket.objects.filter(available_quantity=0, status='active'):
            t.available_quantity = 1
            t.save(update_fields=['available_quantity', 'updated_at'])
            qty_fixed += 1

    return {
        'offers_deleted': offer_del,
        'wallet_transactions_deleted': wallet_tx_del,
        'seller_payouts_deleted': seller_payout_del,
        'orders_deleted': order_del,
        'wallet_balances_reset': wallet_balances_reset,
        'tickets_reset': ticket_reset,
        'qty_restored': qty_fixed,
    }
