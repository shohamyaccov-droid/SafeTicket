"""
Balance mutations for wallet-to-wallet payouts. Uses select_for_update() for safe concurrent updates.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from wallets.models import UserWallet, WalletTransaction


def apply_completed_wallet_transfer(wt: WalletTransaction) -> None:
    """
    For a COMPLETED `WalletTransaction`, move `amount` from sender locked (if any) to receiver available.

    Locks wallets in deterministic primary-key order to reduce deadlock risk when both sides are user wallets.
    """
    if wt.status != WalletTransaction.Status.COMPLETED:
        raise ValidationError('Only COMPLETED transactions can settle balances.')

    if wt.amount is None or wt.amount <= 0:
        raise ValidationError('Invalid transaction amount.')

    amount: Decimal = wt.amount

    with transaction.atomic():
        wallet_ids = sorted({wid for wid in (wt.sender_wallet_id, wt.receiver_wallet_id) if wid is not None})
        locked = {
            row.pk: row
            for row in UserWallet.objects.select_for_update().filter(pk__in=wallet_ids).order_by('pk')
        }
        if len(locked) != len(wallet_ids):
            raise ValidationError('Wallet row missing for settlement.')

        receiver = locked[wt.receiver_wallet_id]
        sender = locked.get(wt.sender_wallet_id) if wt.sender_wallet_id else None

        if sender is not None:
            if sender.locked_balance < amount:
                raise ValidationError('Sender locked balance is insufficient for this settlement.')
            sender.locked_balance -= amount
            sender.save(update_fields=['locked_balance', 'updated_at'])

        receiver.available_balance += amount
        receiver.save(update_fields=['available_balance', 'updated_at'])
