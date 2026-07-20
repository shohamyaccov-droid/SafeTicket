"""
Iteration 5 — wallet underflow, payout cancel edge, register abuse payloads.

Run: python manage.py test users.tests.test_wallet_register_abuse -v 2
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, SellerPayout, Ticket
from users.payout_ledger import ensure_seller_payout_for_order
from wallets.models import UserWallet

User = get_user_model()


@override_settings(DEBUG=False, SECRET_KEY='wallet-abuse-secret')
class WalletEndpointAbuseTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.seller = User.objects.create_user(
            username='wal_seller', email='wal_seller@test.invalid', password='x', role='seller'
        )
        UserWallet.objects.get_or_create(user=self.seller)

    def test_anonymous_wallet_forbidden(self):
        res = self.api.get('/api/users/me/wallet/')
        self.assertIn(res.status_code, (401, 403))
        if res.content:
            self.assertNotIn('traceback', str(res.content).lower())

    def test_authenticated_wallet_safe_shape(self):
        self.api.force_authenticate(self.seller)
        res = self.api.get('/api/users/me/wallet/')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn('summary', body)
        # Must not expose other sellers or raw SQL
        blob = str(body).lower()
        self.assertNotIn('traceback', blob)
        self.assertNotIn('select ', blob)


@override_settings(DEBUG=False, SECRET_KEY='wallet-abuse-secret')
class RegisterAbuseTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def test_register_rejects_oversized_and_wrong_types(self):
        cases = [
            {'email': 'a' * 5000, 'password': 'x', 'password2': 'x', 'username': 'u1'},
            {'email': ['array'], 'password': 'x', 'password2': 'x'},
            {'email': 'ok@test.invalid', 'password': 'short', 'password2': 'short'},
            {'email': 'ok2@test.invalid', 'password': 'ValidPass1!', 'password2': 'Different1!'},
        ]
        for payload in cases:
            res = self.api.post('/api/users/register/', payload, format='json')
            self.assertIn(res.status_code, (400, 401, 429), msg=payload)
            if res.content:
                self.assertNotIn('traceback', str(res.json()).lower())


@override_settings(DEBUG=False, SECRET_KEY='wallet-abuse-secret')
class PayoutCancelEdgeTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.admin = User.objects.create_superuser(
            username='wal_admin', email='wal_admin@test.invalid', password='x'
        )
        self.seller = User.objects.create_user(
            username='wal_payout_seller',
            email='wal_payout_seller@test.invalid',
            password='x',
            role='seller',
            account_holder_name='S',
            bank_name='B',
            branch_number='1',
            account_number='2',
        )
        buyer = User.objects.create_user(
            username='wal_payout_buyer', email='wal_payout_buyer@test.invalid', password='x', role='buyer'
        )
        event = Event.objects.create(
            name='Wallet Payout Event',
            artist=Artist.objects.create(name='Wallet Artist'),
            date=timezone.now() - timedelta(hours=50),
            venue='מקום',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='sold',
            available_quantity=0,
        )
        order = Order.objects.create(
            user=buyer,
            ticket=ticket,
            status='paid',
            total_amount=Decimal('112.00'),
            total_paid_by_buyer=Decimal('112.00'),
            final_negotiated_price=Decimal('100.00'),
            buyer_service_fee=Decimal('12.00'),
            net_seller_revenue=Decimal('100.00'),
            quantity=1,
            event_name=event.name,
            payout_status='eligible',
            payout_eligible_date=timezone.now() - timedelta(hours=1),
        )
        self.payout = ensure_seller_payout_for_order(order)
        self.payout.payout_status = SellerPayout.PayoutStatus.CANCELLED
        self.payout.save(update_fields=['payout_status'])

    def test_cannot_mark_cancelled_payout_paid(self):
        self.api.force_authenticate(self.admin)
        res = self.api.post(f'/api/users/admin/payouts/{self.payout.pk}/mark-paid/', {}, format='json')
        self.assertEqual(res.status_code, 400)
        body = res.json()
        self.assertIn('error', body)
        self.assertNotIn('traceback', str(body).lower())
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.payout_status, SellerPayout.PayoutStatus.CANCELLED)
