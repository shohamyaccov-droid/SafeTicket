from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UserWallet(models.Model):
    """
    Per-user balances for delayed (post-event) marketplace payouts.
    `locked_balance` holds escrow until the linked event passes; `available_balance` is withdrawable.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet',
    )
    available_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Funds ready to withdraw or spend internally.',
    )
    locked_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Funds held in escrow until the event ends / payout rules clear.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Wallet({self.user_id}) avail={self.available_balance} locked={self.locked_balance}'


class WalletTransaction(models.Model):
    """
    A single wallet-to-wallet movement (e.g. PayMe batch) tied to an optional marketplace event.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Waiting for event / release conditions'
        PROCESSING = 'PROCESSING', 'API call sent to PayMe'
        COMPLETED = 'COMPLETED', 'Successfully transferred'
        FAILED = 'FAILED', 'Transfer error'

    sender_wallet = models.ForeignKey(
        UserWallet,
        on_delete=models.PROTECT,
        related_name='outgoing_transactions',
        null=True,
        blank=True,
        help_text='Null when funds originate from the platform treasury (not a user wallet row).',
    )
    receiver_wallet = models.ForeignKey(
        UserWallet,
        on_delete=models.PROTECT,
        related_name='incoming_transactions',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    payme_batch_id = models.CharField(max_length=255, blank=True, null=True)
    payme_transfer_id = models.CharField(max_length=255, blank=True, null=True)
    associated_event = models.ForeignKey(
        'users.Event',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return f'WT#{self.pk} {self.amount} {self.status}'

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({'amount': 'Amount must be positive.'})

    def apply_balance_move_for_completed(self):
        """
        Apply ledger changes for a COMPLETED transfer (idempotent for repeated calls is NOT implemented;
        call once when marking COMPLETED). Uses row-level locks when supported (Postgres).
        """
        from wallets.services import apply_completed_wallet_transfer

        apply_completed_wallet_transfer(self)
