"""
Edge-case suite: pricing math, escrow gates, ticket create validation, concurrency.

Reflection after leakage pass — what could break next?
- Negative / zero / huge listing prices
- Fee math never goes below zero total
- Escrow mark-paid before 36h threshold
- Concurrent reserve of the same ticket
- Wrong types on checkout/order create

Run: python manage.py test users.tests.test_edge_pricing_escrow -v 2
"""
from __future__ import annotations

import threading
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.test import APIClient

from users.fee_settings import get_fee_rates
from users.models import Artist, Event, Order, SellerPayout, Ticket
from users.payout_ledger import ensure_seller_payout_for_order
from users.pricing import (
    affiliate_checkout_amounts,
    buyer_charge_from_base_amount,
    compute_payout_eligible_date,
    expected_buy_now_total,
    seller_fee_from_base_amount,
)

User = get_user_model()


def _minimal_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


@override_settings(DEBUG=False, SECRET_KEY='edge-pricing-secret')
class PricingMathEdgeTests(TestCase):
    def test_zero_and_negative_base_yield_zero_fees(self):
        for base in (0, -1, -100.5, Decimal('-0.01'), '0', '-999'):
            b, fee, total = buyer_charge_from_base_amount(base)
            self.assertEqual(b, Decimal('0.00'))
            self.assertEqual(fee, Decimal('0.00'))
            self.assertEqual(total, Decimal('0.00'))
            self.assertEqual(seller_fee_from_base_amount(base), Decimal('0.00'))

    def test_buyer_total_equals_base_plus_fee(self):
        for base in (Decimal('1.00'), Decimal('99.99'), Decimal('100.00'), Decimal('1234.56')):
            b, fee, total = buyer_charge_from_base_amount(base)
            self.assertEqual(total, (b + fee).quantize(Decimal('0.01')))
            self.assertGreaterEqual(fee, Decimal('0.00'))
            self.assertGreaterEqual(total, b)

    def test_expected_buy_now_matches_unit_charge_times_qty(self):
        unit = Decimal('100.00')
        _, _, unit_total = buyer_charge_from_base_amount(unit)
        self.assertEqual(expected_buy_now_total(unit, 1), unit_total)
        self.assertEqual(expected_buy_now_total(unit, 3), (unit_total * 3).quantize(Decimal('0.01')))

    def test_affiliate_amounts_never_negative_total(self):
        amounts = affiliate_checkout_amounts(Decimal('100.00'))
        self.assertGreaterEqual(amounts['total'], amounts['base'])
        self.assertGreaterEqual(amounts['buyer_fee'], Decimal('0.00'))
        for key in ('buyer_discount', 'affiliate_commission', 'platform_net_fee'):
            self.assertGreaterEqual(amounts[key], Decimal('0.00'), msg=key)

    def test_live_fee_rates_are_bounded(self):
        rates = get_fee_rates()
        self.assertGreaterEqual(rates.base_buyer_fee_rate, Decimal('0'))
        self.assertLessEqual(rates.base_buyer_fee_rate, Decimal('1'))
        self.assertGreaterEqual(rates.base_seller_fee_rate, Decimal('0'))
        self.assertLessEqual(rates.base_seller_fee_rate, Decimal('1'))


@override_settings(DEBUG=False, SECRET_KEY='edge-pricing-secret')
class TicketCreateValidationEdgeTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.seller = User.objects.create_user(
            username='edge_seller',
            email='edge_seller@test.invalid',
            password='x',
            role='seller',
        )
        future = timezone.now() + timedelta(days=45)
        artist = Artist.objects.create(name='Edge Artist')
        self.event = Event.objects.create(
            name='Edge Event',
            artist=artist,
            date=future,
            venue='מקום',
            city='Tel Aviv',
            country='US',
            category='concert',
        )
        self.api.force_authenticate(self.seller)

    def _post(self, **extra):
        pdf = SimpleUploadedFile('t.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        data = {
            'event_id': self.event.id,
            'original_price': '100.00',
            'listing_price': '100.00',
            'available_quantity': '1',
            'pdf_files_count': '1',
            'pdf_file_0': pdf,
            'delivery_method': 'instant',
        }
        data.update(extra)
        return self.api.post('/api/users/tickets/', data, format='multipart')

    def test_negative_listing_price_rejected(self):
        res = self._post(listing_price='-50', original_price='-50')
        self.assertIn(res.status_code, (400, 422))
        body = res.json()
        raw = str(body).lower()
        self.assertNotIn('traceback', raw)

    def test_zero_listing_price_rejected(self):
        res = self._post(listing_price='0', original_price='0')
        self.assertIn(res.status_code, (400, 422))

    def test_non_numeric_price_rejected(self):
        res = self._post(listing_price='abc', original_price='abc')
        self.assertIn(res.status_code, (400, 422))

    def test_quantity_mismatch_files_rejected(self):
        pdf = SimpleUploadedFile('t.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        res = self.api.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '100.00',
                'listing_price': '100.00',
                'available_quantity': '3',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        # Auto-split needs matching page count; single blank page vs qty 3 → 400
        self.assertEqual(res.status_code, 400)

    def test_missing_event_rejected(self):
        res = self._post(event_id='999999')
        self.assertIn(res.status_code, (400, 404))


@override_settings(DEBUG=False, SECRET_KEY='edge-pricing-secret')
class EscrowGateEdgeTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.admin = User.objects.create_superuser(
            username='edge_admin',
            email='edge_admin@test.invalid',
            password='x',
        )
        self.seller = User.objects.create_user(
            username='edge_escrow_seller',
            email='edge_escrow_seller@test.invalid',
            password='x',
            role='seller',
            account_holder_name='Seller',
            bank_name='Bank',
            branch_number='001',
            account_number='123',
        )
        self.buyer = User.objects.create_user(
            username='edge_escrow_buyer',
            email='edge_escrow_buyer@test.invalid',
            password='x',
            role='buyer',
        )
        # Event still in the future → escrow threshold not met
        event = Event.objects.create(
            name='Escrow Edge Event',
            artist=Artist.objects.create(name='Escrow Artist'),
            date=timezone.now() + timedelta(days=10),
            venue='מקום',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        self.ticket = Ticket.objects.create(
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
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='paid',
            total_amount=Decimal('112.00'),
            total_paid_by_buyer=Decimal('112.00'),
            final_negotiated_price=Decimal('100.00'),
            buyer_service_fee=Decimal('12.00'),
            seller_service_fee=Decimal('0.00'),
            net_seller_revenue=Decimal('100.00'),
            quantity=1,
            event_name=event.name,
            payout_status='locked',
            payout_eligible_date=timezone.now() + timedelta(days=5),
        )
        self.payout = ensure_seller_payout_for_order(self.order)

    def test_mark_paid_blocked_while_locked(self):
        self.api.force_authenticate(self.admin)
        res = self.api.post(f'/api/users/admin/payouts/{self.payout.pk}/mark-paid/', {}, format='json')
        self.assertEqual(res.status_code, 400)
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.payout_status, SellerPayout.PayoutStatus.PENDING)
        body = res.json()
        self.assertIn('error', body)
        self.assertNotIn('traceback', str(body).lower())

    def test_eligible_date_is_after_event(self):
        eligible = compute_payout_eligible_date(self.ticket)
        self.assertIsNotNone(eligible)
        self.assertGreater(eligible, self.ticket.event_date)


@override_settings(DEBUG=False, SECRET_KEY='edge-pricing-secret')
class ConcurrentReserveTests(TransactionTestCase):
    """Two buyers racing to reserve the last ticket — only one should win."""

    def setUp(self):
        self.seller = User.objects.create_user(
            username='race_seller',
            email='race_seller@test.invalid',
            password='x',
            role='seller',
        )
        self.buyer_a = User.objects.create_user(
            username='race_a',
            email='race_a@test.invalid',
            password='x',
            role='buyer',
        )
        self.buyer_b = User.objects.create_user(
            username='race_b',
            email='race_b@test.invalid',
            password='x',
            role='buyer',
        )
        event = Event.objects.create(
            name='Race Event',
            artist=Artist.objects.create(name='Race Artist'),
            date=timezone.now() + timedelta(days=20),
            venue='מקום',
            city='Tel Aviv',
            country='US',
            category='concert',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='active',
            available_quantity=1,
        )

    def test_only_one_concurrent_reserve_succeeds(self):
        results = []

        def reserve(user):
            client = APIClient()
            client.force_authenticate(user)
            try:
                res = client.post(f'/api/users/tickets/{self.ticket.pk}/reserve/', {}, format='json')
                results.append(res.status_code)
            except Exception:
                results.append(500)

        t1 = threading.Thread(target=reserve, args=(self.buyer_a,))
        t2 = threading.Thread(target=reserve, args=(self.buyer_b,))
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        self.assertEqual(len(results), 2)
        successes = [s for s in results if s in (200, 201)]
        failures = [s for s in results if s >= 400]
        self.assertEqual(len(successes), 1, msg=f'results={results}')
        self.assertEqual(len(failures), 1, msg=f'results={results}')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'reserved')
        self.assertIsNotNone(self.ticket.reserved_by_id)
