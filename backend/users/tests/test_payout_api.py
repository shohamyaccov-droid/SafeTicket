"""
Tests for admin payout APIs and seller wallet endpoint.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Event, Order, SellerPayout, Ticket
from users.payout_ledger import ensure_seller_payout_for_order
from wallets.models import WalletTransaction

User = get_user_model()


@override_settings(DEBUG=True, SECRET_KEY='test-secret-key-for-local')
class PayoutApiTestBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin_fin',
            email='admin_fin@test.com',
            password='test-pass-123',
            is_staff=True,
        )
        self.seller = User.objects.create_user(
            username='seller_fin',
            email='seller_fin@test.com',
            password='test-pass-123',
            role='seller',
            account_holder_name='Seller Name',
            bank_name='12',
            branch_number='456',
            account_number='123456789',
        )
        self.buyer = User.objects.create_user(
            username='buyer_fin',
            email='buyer_fin@test.com',
            password='test-pass-123',
        )
        self.event = Event.objects.create(
            name='Wallet Event',
            date=timezone.now() + timedelta(days=30),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='sold',
            available_quantity=0,
        )

    def _create_paid_order(self, *, escrow='locked'):
        order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='paid',
            total_amount=Decimal('115.00'),
            total_paid_by_buyer=Decimal('115.00'),
            quantity=1,
            event_name=self.event.name,
            payout_status=escrow,
            payout_eligible_date=timezone.now() + timedelta(days=5) if escrow == 'locked' else timezone.now() - timedelta(hours=1),
        )
        return ensure_seller_payout_for_order(order)


@override_settings(DEBUG=True, SECRET_KEY='test-secret-key-for-local')
class AdminPayoutApiTests(PayoutApiTestBase):
    def test_admin_payouts_list_requires_staff(self):
        payout = self._create_paid_order()
        self.client.force_authenticate(user=self.seller)
        res = self.client.get('/api/users/admin/payouts/')
        self.assertEqual(res.status_code, 403)

        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/users/admin/payouts/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['summary']['pending_count'], 1)
        self.assertEqual(res.data['payouts'][0]['id'], payout.pk)
        self.assertEqual(res.data['payouts'][0]['seller_bank']['account_holder_name'], 'Seller Name')

    def test_admin_summary_fee_math(self):
        self._create_paid_order()
        self.client.force_authenticate(user=self.admin)
        res = self.client.get('/api/users/admin/payouts/')
        summary = res.data['summary']
        self.assertEqual(summary['total_pending_owed'], '97.75')
        self.assertEqual(summary['total_pending_platform_fees'], '17.25')
        self.assertEqual(summary['total_platform_revenue'], '17.25')

    def test_admin_mark_paid_updates_status(self):
        payout = self._create_paid_order(escrow='eligible')
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.available_balance, Decimal('97.75'))
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(f'/api/users/admin/payouts/{payout.pk}/mark-paid/', {}, format='json')
        self.assertEqual(res.status_code, 200)
        payout.refresh_from_db()
        self.assertEqual(payout.payout_status, SellerPayout.PayoutStatus.TRANSFERRED)
        self.assertIsNotNone(payout.transferred_at)
        payout.order.refresh_from_db()
        self.assertEqual(payout.order.payout_status, 'paid')
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.available_balance, Decimal('0.00'))
        self.assertTrue(
            WalletTransaction.objects.filter(
                seller_payout=payout,
                transaction_type=WalletTransaction.TransactionType.WITHDRAWAL,
                amount=Decimal('-97.75'),
            ).exists()
        )
        self.assertEqual(res.data['summary']['pending_count'], 0)

    def test_admin_mark_paid_idempotent_message(self):
        payout = self._create_paid_order()
        payout.payout_status = SellerPayout.PayoutStatus.TRANSFERRED
        payout.transferred_at = timezone.now()
        payout.save()
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(f'/api/users/admin/payouts/{payout.pk}/mark-paid/', {}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('already', res.data['message'].lower())


@override_settings(DEBUG=True, SECRET_KEY='test-secret-key-for-local')
class UserWalletApiTests(PayoutApiTestBase):
    def test_wallet_requires_auth(self):
        res = self.client.get('/api/users/me/wallet/')
        self.assertEqual(res.status_code, 401)

    def test_wallet_summary_splits_pending_and_available(self):
        locked_payout = self._create_paid_order(escrow='locked')
        eligible_order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='paid',
            total_amount=Decimal('230.00'),
            total_paid_by_buyer=Decimal('230.00'),
            quantity=1,
            event_name=self.event.name,
            payout_status='eligible',
        )
        eligible_payout = ensure_seller_payout_for_order(eligible_order)

        self.client.force_authenticate(user=self.seller)
        res = self.client.get('/api/users/me/wallet/')
        self.assertEqual(res.status_code, 200)
        summary = res.data['summary']
        self.assertEqual(summary['pending_funds'], '97.75')
        self.assertEqual(summary['available_funds'], '195.50')
        self.assertEqual(summary['total_earned'], '0.00')
        self.assertEqual(len(res.data['transactions']), 2)

        tx_by_id = {t['id']: t for t in res.data['transactions']}
        self.assertEqual(tx_by_id[locked_payout.pk]['display_status'], 'pending_event')
        self.assertEqual(tx_by_id[eligible_payout.pk]['display_status'], 'available')
        self.assertEqual(tx_by_id[locked_payout.pk]['platform_fee'], '17.25')
        self.assertEqual(tx_by_id[locked_payout.pk]['net_earnings'], '97.75')
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.locked_balance, Decimal('97.75'))
        self.assertEqual(self.seller.wallet.available_balance, Decimal('195.50'))

    def test_wallet_shows_transferred_as_earned(self):
        payout = self._create_paid_order()
        payout.payout_status = SellerPayout.PayoutStatus.TRANSFERRED
        payout.transferred_at = timezone.now()
        payout.save()

        self.client.force_authenticate(user=self.seller)
        res = self.client.get('/api/users/me/wallet/')
        self.assertEqual(res.data['summary']['total_earned'], '97.75')
        self.assertEqual(res.data['transactions'][0]['display_status'], 'paid')

    def test_wallet_15_percent_fee_on_transaction(self):
        payout = self._create_paid_order()
        self.client.force_authenticate(user=self.seller)
        res = self.client.get('/api/users/me/wallet/')
        tx = res.data['transactions'][0]
        total = Decimal(tx['ticket_price'])
        fee = Decimal(tx['platform_fee'])
        net = Decimal(tx['net_earnings'])
        self.assertEqual(fee, (total * Decimal('0.15')).quantize(Decimal('0.01')))
        self.assertEqual(net, (total - fee).quantize(Decimal('0.01')))
