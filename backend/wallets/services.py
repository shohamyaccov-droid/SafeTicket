"""
Balance mutations for wallet-to-wallet payouts. Uses select_for_update() for safe concurrent updates.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

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


def _event_for_payout(payout):
    order = getattr(payout, 'order', None)
    ticket = getattr(order, 'ticket', None) if order else None
    return getattr(ticket, 'event', None) if ticket else None


def credit_wallet_for_seller_payout(payout) -> WalletTransaction | None:
    """
    Idempotently credit the seller wallet when a paid order creates a SellerPayout.
    Locked escrow goes to locked_balance; already-eligible payouts go straight to available_balance.
    """
    if payout is None or payout.pk is None or payout.seller_id is None:
        return None

    amount = Decimal(payout.net_payout or 0).quantize(Decimal('0.01'))
    if amount <= 0:
        return None

    with transaction.atomic():
        existing = (
            WalletTransaction.objects.select_for_update()
            .filter(
                seller_payout=payout,
                transaction_type=WalletTransaction.TransactionType.SALE_CREDIT,
            )
            .first()
        )
        if existing:
            return existing

        wallet, _created = UserWallet.objects.select_for_update().get_or_create(user_id=payout.seller_id)
        escrow_status = (getattr(payout.order, 'payout_status', '') or 'locked').strip()
        is_available = escrow_status in ('eligible', 'paid')

        if is_available:
            wallet.available_balance += amount
            tx_status = WalletTransaction.Status.COMPLETED
        else:
            wallet.locked_balance += amount
            tx_status = WalletTransaction.Status.PENDING
        wallet.save(update_fields=['available_balance', 'locked_balance', 'updated_at'])

        tx = WalletTransaction.objects.create(
            sender_wallet=None,
            receiver_wallet=wallet,
            amount=amount,
            status=tx_status,
            transaction_type=WalletTransaction.TransactionType.SALE_CREDIT,
            associated_event=_event_for_payout(payout),
            seller_payout=payout,
            note=f'Order #{payout.order_id} seller net payout',
        )
        return tx


def release_eligible_wallet_payouts(*, seller=None) -> int:
    """
    Move seller payout credits from locked_balance to available_balance once escrow is eligible.
    Returns number of wallet transactions released.
    """
    from users.models import SellerPayout

    qs = (
        SellerPayout.objects.select_related('seller', 'order')
        .filter(payout_status=SellerPayout.PayoutStatus.PENDING, order__payout_status='eligible')
    )
    if seller is not None:
        qs = qs.filter(seller=seller)

    released = 0
    for payout in qs.iterator():
        with transaction.atomic():
            tx = (
                WalletTransaction.objects.select_for_update()
                .filter(
                    seller_payout=payout,
                    transaction_type=WalletTransaction.TransactionType.SALE_CREDIT,
                )
                .first()
            )
            if tx is None:
                tx = credit_wallet_for_seller_payout(payout)
            if tx is None or tx.status == WalletTransaction.Status.COMPLETED:
                continue

            amount = Decimal(tx.amount or 0).quantize(Decimal('0.01'))
            wallet = UserWallet.objects.select_for_update().get(pk=tx.receiver_wallet_id)
            if wallet.locked_balance < amount:
                raise ValidationError('Wallet locked balance is insufficient to release payout.')
            wallet.locked_balance -= amount
            wallet.available_balance += amount
            wallet.save(update_fields=['locked_balance', 'available_balance', 'updated_at'])
            tx.status = WalletTransaction.Status.COMPLETED
            tx.note = (tx.note or 'Seller payout released from escrow')[:255]
            tx.save(update_fields=['status', 'note', 'updated_at'])
            released += 1
    return released


def mark_seller_payout_paid(payout):
    """
    Mark one available SellerPayout as manually transferred and write a negative wallet withdrawal.
    """
    from users.models import Order, SellerPayout

    if payout.payout_status == SellerPayout.PayoutStatus.TRANSFERRED:
        return payout
    if payout.payout_status == SellerPayout.PayoutStatus.CANCELLED:
        raise ValidationError('Cannot mark a cancelled payout as paid.')

    release_eligible_wallet_payouts(seller=payout.seller)

    amount = Decimal(payout.net_payout or 0).quantize(Decimal('0.01'))
    with transaction.atomic():
        payout = SellerPayout.objects.select_for_update().select_related('seller', 'order').get(pk=payout.pk)
        if payout.payout_status == SellerPayout.PayoutStatus.TRANSFERRED:
            return payout
        if payout.payout_status == SellerPayout.PayoutStatus.CANCELLED:
            raise ValidationError('Cannot mark a cancelled payout as paid.')
        if (payout.order.payout_status if payout.order_id else 'eligible') == 'locked':
            raise ValidationError('Payout is still locked in escrow.')

        wallet, _created = UserWallet.objects.select_for_update().get_or_create(user_id=payout.seller_id)
        if wallet.available_balance < amount:
            raise ValidationError('Seller wallet available balance is insufficient for payout.')
        wallet.available_balance -= amount
        wallet.save(update_fields=['available_balance', 'updated_at'])

        WalletTransaction.objects.create(
            sender_wallet=None,
            receiver_wallet=wallet,
            amount=-amount,
            status=WalletTransaction.Status.COMPLETED,
            transaction_type=WalletTransaction.TransactionType.WITHDRAWAL,
            associated_event=_event_for_payout(payout),
            seller_payout=payout,
            note=f'Manual payout transfer for order #{payout.order_id}',
        )

        payout.payout_status = SellerPayout.PayoutStatus.TRANSFERRED
        payout.transferred_at = timezone.now()
        payout.save(update_fields=['payout_status', 'transferred_at'])
        if payout.order_id:
            Order.objects.filter(pk=payout.order_id, payout_status__in=('locked', 'eligible')).update(
                payout_status='paid'
            )
        return payout
