"""
Unit tests for delayed marketplace wallet balances and settlements.
"""

import unittest
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from users.models import Event
from wallets.models import UserWallet, WalletTransaction
from wallets.services import apply_completed_wallet_transfer

User = get_user_model()


class UserWalletModelTests(TransactionTestCase):
    reset_sequences = True

    def test_wallet_one_to_one_with_user(self):
        user = User.objects.create_user(username='buyer1', password='x' * 12)
        self.assertTrue(hasattr(user, 'wallet'))
        wallet = user.wallet
        self.assertIsInstance(wallet, UserWallet)
        self.assertEqual(wallet.user_id, user.id)
        self.assertEqual(wallet.available_balance, Decimal('0.00'))
        self.assertEqual(wallet.locked_balance, Decimal('0.00'))

    def test_manual_wallet_create(self):
        user = User.objects.create_user(username='seller9', password='y' * 12)
        w = UserWallet.objects.get(user=user)
        w.available_balance = Decimal('10.00')
        w.save()
        w.refresh_from_db()
        self.assertEqual(w.available_balance, Decimal('10.00'))


class WalletTransactionTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.sender = User.objects.create_user(username='escrow_sender', password='p' * 12)
        self.receiver = User.objects.create_user(username='escrow_receiver', password='q' * 12)
        self.sender_wallet = UserWallet.objects.get(user=self.sender)
        self.receiver_wallet = UserWallet.objects.get(user=self.receiver)
        self.sender_wallet.locked_balance = Decimal('100.00')
        self.sender_wallet.save()
        self.event = Event.objects.create(
            name='QA Show',
            date=timezone.now(),
            city='Tel Aviv',
        )

    def test_transaction_defaults_and_event_link(self):
        wt = WalletTransaction.objects.create(
            sender_wallet=self.sender_wallet,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('25.50'),
            associated_event=self.event,
        )
        self.assertEqual(wt.status, WalletTransaction.Status.PENDING)
        self.assertIsNone(wt.payme_batch_id)
        self.assertEqual(wt.associated_event_id, self.event.id)

    def test_status_choices_round_trip(self):
        wt = WalletTransaction.objects.create(
            sender_wallet=None,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('5.00'),
            status=WalletTransaction.Status.PROCESSING,
            payme_batch_id='batch-1',
            payme_transfer_id='tr-99',
        )
        self.assertEqual(wt.status, WalletTransaction.Status.PROCESSING)
        wt.status = WalletTransaction.Status.FAILED
        wt.save()
        wt.refresh_from_db()
        self.assertEqual(wt.status, WalletTransaction.Status.FAILED)

    def test_apply_completed_moves_locked_to_available(self):
        wt = WalletTransaction.objects.create(
            sender_wallet=self.sender_wallet,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('40.00'),
            status=WalletTransaction.Status.COMPLETED,
            associated_event=self.event,
        )
        before_sender_locked = self.sender_wallet.locked_balance
        before_recv_avail = self.receiver_wallet.available_balance
        wt.apply_balance_move_for_completed()
        self.sender_wallet.refresh_from_db()
        self.receiver_wallet.refresh_from_db()
        self.assertEqual(self.sender_wallet.locked_balance, before_sender_locked - Decimal('40.00'))
        self.assertEqual(self.receiver_wallet.available_balance, before_recv_avail + Decimal('40.00'))

    def test_platform_payout_no_sender_wallet(self):
        wt = WalletTransaction.objects.create(
            sender_wallet=None,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('12.00'),
            status=WalletTransaction.Status.COMPLETED,
        )
        before = self.receiver_wallet.available_balance
        apply_completed_wallet_transfer(wt)
        self.receiver_wallet.refresh_from_db()
        self.assertEqual(self.receiver_wallet.available_balance, before + Decimal('12.00'))

    def test_apply_completed_rejects_non_completed_status(self):
        wt = WalletTransaction.objects.create(
            sender_wallet=self.sender_wallet,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('1.00'),
            status=WalletTransaction.Status.PENDING,
        )
        with self.assertRaises(ValidationError):
            wt.apply_balance_move_for_completed()

    def test_apply_completed_insufficient_locked(self):
        wt = WalletTransaction.objects.create(
            sender_wallet=self.sender_wallet,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('500.00'),
            status=WalletTransaction.Status.COMPLETED,
        )
        with self.assertRaises(ValidationError):
            wt.apply_balance_move_for_completed()

    def test_two_sequential_completed_settlements_consistent_balances(self):
        wt1 = WalletTransaction.objects.create(
            sender_wallet=self.sender_wallet,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('10.00'),
            status=WalletTransaction.Status.COMPLETED,
        )
        wt2 = WalletTransaction.objects.create(
            sender_wallet=self.sender_wallet,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('15.00'),
            status=WalletTransaction.Status.COMPLETED,
        )
        apply_completed_wallet_transfer(wt1)
        apply_completed_wallet_transfer(wt2)
        self.sender_wallet.refresh_from_db()
        self.receiver_wallet.refresh_from_db()
        self.assertEqual(self.sender_wallet.locked_balance, Decimal('75.00'))
        self.assertEqual(self.receiver_wallet.available_balance, Decimal('25.00'))

    @unittest.skipUnless(connection.vendor == 'postgresql', 'SQLite cannot run two concurrent writers on the same rows')
    def test_concurrent_settlements_postgres_only(self):
        from threading import Barrier, Thread

        wt1 = WalletTransaction.objects.create(
            sender_wallet=self.sender_wallet,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('10.00'),
            status=WalletTransaction.Status.COMPLETED,
        )
        wt2 = WalletTransaction.objects.create(
            sender_wallet=self.sender_wallet,
            receiver_wallet=self.receiver_wallet,
            amount=Decimal('15.00'),
            status=WalletTransaction.Status.COMPLETED,
        )
        barrier = Barrier(2)
        errors = []

        def run(wt):
            try:
                barrier.wait()
                apply_completed_wallet_transfer(wt)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = Thread(target=run, args=(wt1,))
        t2 = Thread(target=run, args=(wt2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(errors, [])
        self.sender_wallet.refresh_from_db()
        self.receiver_wallet.refresh_from_db()
        self.assertEqual(self.sender_wallet.locked_balance, Decimal('75.00'))
        self.assertEqual(self.receiver_wallet.available_balance, Decimal('25.00'))
