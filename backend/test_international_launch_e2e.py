"""
Launch QA: international listing (no receipt), offer idempotency, fast confirm-payment (receipt in background).

Run: cd backend && python manage.py test test_international_launch_e2e -v 2

Note: receipt timing test uses TransactionTestCase so a worker thread can open its own DB connection (SQLite-safe).
"""
from __future__ import annotations

import time
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from datetime import timedelta
from pypdf import PdfWriter
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket, Order, Offer
from users.pricing import buyer_charge_from_base_amount

User = get_user_model()


def _pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


class InternationalLaunchE2ETest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        self.starts = timezone.now() + timedelta(days=90)
        self.ends = self.starts + timedelta(hours=3)
        self.artist = Artist.objects.create(name='US QA Artist')
        self.event = Event.objects.create(
            name='USA Arena NYC',
            artist=self.artist,
            date=self.starts,
            ends_at=self.ends,
            venue='אחר',
            city='New York',
            country='US',
            category='concert',
        )
        self.seller = User.objects.create_user(
            username='us_seller_launch',
            password='pass12345',
            email='usseller@launch.test',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='us_buyer_launch',
            password='pass12345',
            email='usbuyer@launch.test',
            role='buyer',
        )

    def test_us_listing_without_receipt_and_buyer_offer(self):
        pdf = SimpleUploadedFile('tix.pdf', _pdf_bytes(), content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r_list = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '120',
                'listing_price': '120',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r_list.status_code, 201, r_list.content)
        tid = r_list.json()['id']
        ticket = Ticket.objects.get(pk=tid)
        self.assertIsNone(ticket.receipt_file.name if ticket.receipt_file else None)

        self.client.force_authenticate(self.buyer)
        r_off = self.client.post(
            '/api/users/offers/',
            {'ticket': tid, 'amount': '100.00', 'quantity': 1},
            format='json',
        )
        self.assertEqual(r_off.status_code, 201, r_off.content)
        self.assertEqual(Offer.objects.filter(buyer=self.buyer, ticket_id=tid).count(), 1)

    def test_duplicate_initial_offer_within_five_seconds_rejected(self):
        pdf = SimpleUploadedFile('tix.pdf', _pdf_bytes(), content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r_list = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '80',
                'listing_price': '80',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r_list.status_code, 201, r_list.content)
        tid = r_list.json()['id']

        self.client.force_authenticate(self.buyer)
        payload = {'ticket': tid, 'amount': '70.00', 'quantity': 1}
        r1 = self.client.post('/api/users/offers/', payload, format='json')
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self.client.post('/api/users/offers/', payload, format='json')
        self.assertEqual(r2.status_code, 400, r2.content)
        self.assertEqual(
            Offer.objects.filter(buyer=self.buyer, ticket_id=tid, offer_round_count=0).count(),
            1,
        )

    def test_usd_full_negotiation_counter_accept_pay_and_fee_breakdown(self):
        """International (USD): list → offer → seller counter → buyer accept → checkout → pay; verify 10%+5% fees."""
        pdf = SimpleUploadedFile('tix_us.pdf', _pdf_bytes(), content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r_list = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '150',
                'listing_price': '150',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r_list.status_code, 201, r_list.content)
        tid = r_list.json()['id']

        self.client.force_authenticate(self.buyer)
        r_off = self.client.post(
            '/api/users/offers/',
            {'ticket': tid, 'amount': '100.00', 'quantity': 1},
            format='json',
        )
        self.assertEqual(r_off.status_code, 201, r_off.content)
        oid0 = r_off.json()['id']
        self.assertEqual(r_off.json().get('currency'), 'USD')

        self.client.force_authenticate(self.seller)
        r_co = self.client.post(
            f'/api/users/offers/{oid0}/counter/',
            {'amount': '120.00'},
            format='json',
        )
        self.assertEqual(r_co.status_code, 201, r_co.content)
        counter = r_co.json()
        oid1 = counter['id']
        self.assertEqual(counter.get('currency'), 'USD')
        self.assertEqual(counter.get('offer_round_count'), 1)

        self.client.force_authenticate(self.buyer)
        r_acc1 = self.client.post(f'/api/users/offers/{oid1}/accept/', {}, format='json')
        r_acc2 = self.client.post(f'/api/users/offers/{oid1}/accept/', {}, format='json')
        r_acc3 = self.client.post(f'/api/users/offers/{oid1}/accept/', {}, format='json')
        self.assertEqual(r_acc1.status_code, 200, r_acc1.content)
        self.assertEqual(r_acc2.status_code, 400, r_acc2.content)
        self.assertEqual(r_acc3.status_code, 400, r_acc3.content)

        self.assertEqual(
            Offer.objects.filter(pk=oid1, status='accepted', ticket_id=tid).count(),
            1,
        )
        pending_accepted = Offer.objects.filter(ticket_id=tid, status='accepted').count()
        self.assertEqual(pending_accepted, 1)

        base = Decimal('120.00')
        _, fee_buyer, total = buyer_charge_from_base_amount(base)
        self.assertEqual(fee_buyer, Decimal('12.00'))
        self.assertEqual(total, Decimal('132.00'))

        r_ord = self.client.post(
            '/api/users/orders/',
            {
                'ticket': tid,
                'quantity': 1,
                'total_amount': str(total),
                'event_name': self.event.name,
                'offer_id': oid1,
            },
            format='json',
        )
        self.assertEqual(r_ord.status_code, 201, r_ord.content)
        order_id = r_ord.json()['id']
        tok = r_ord.json().get('payment_confirm_token')
        self.assertTrue(tok)

        r_pay = self.client.post(
            f'/api/users/orders/{order_id}/confirm-payment/',
            {'mock_payment_ack': True, 'payment_confirm_token': tok},
            format='json',
        )
        self.assertEqual(r_pay.status_code, 200, r_pay.content)

        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.currency, 'USD')
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.final_negotiated_price, base)
        self.assertEqual(order.buyer_service_fee, Decimal('12.00'))
        self.assertEqual(order.seller_service_fee, Decimal('6.00'))
        self.assertEqual(order.net_seller_revenue, Decimal('114.00'))
        self.assertEqual(order.total_paid_by_buyer, total)
        self.assertEqual(Order.objects.filter(user=self.buyer, ticket_id=tid).count(), 1)


class InternationalLaunchReceiptAsyncE2E(TransactionTestCase):
    """Real DB commits so background receipt thread can query SQLite without 'database is locked'."""

    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        self.starts = timezone.now() + timedelta(days=90)
        self.ends = self.starts + timedelta(hours=3)
        self.artist = Artist.objects.create(name='US QA Artist Receipt')
        self.event = Event.objects.create(
            name='USA Receipt Timing',
            artist=self.artist,
            date=self.starts,
            ends_at=self.ends,
            venue='אחר',
            city='New York',
            country='US',
            category='concert',
        )
        self.seller = User.objects.create_user(
            username='us_seller_receipt',
            password='pass12345',
            email='usseller_rcpt.test',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='us_buyer_receipt',
            password='pass12345',
            email='usbuyer_rcpt.test',
            role='buyer',
        )

    def test_confirm_payment_returns_quickly_while_receipt_email_slow(self):
        pdf = SimpleUploadedFile('tix3.pdf', _pdf_bytes(), content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r_list = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '50',
                'listing_price': '50',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r_list.status_code, 201, r_list.content)
        tid = r_list.json()['id']

        self.client.force_authenticate(self.buyer)
        base = Decimal('50')
        r_ord = self.client.post(
            '/api/users/orders/',
            {
                'ticket': tid,
                'quantity': 1,
                'total_amount': str(base * Decimal('1.10')),
                'event_name': self.event.name,
            },
            format='json',
        )
        self.assertEqual(r_ord.status_code, 201, r_ord.content)
        order_id = r_ord.json()['id']
        tok = r_ord.json().get('payment_confirm_token')
        self.assertTrue(tok)

        def slow_receipt(*args, **kwargs):
            time.sleep(1.5)

        with patch('users.utils.emails.send_receipt_with_pdf', side_effect=slow_receipt):
            t0 = time.perf_counter()
            r_pay = self.client.post(
                f'/api/users/orders/{order_id}/confirm-payment/',
                {'mock_payment_ack': True, 'payment_confirm_token': tok},
                format='json',
            )
            elapsed = time.perf_counter() - t0

        self.assertEqual(r_pay.status_code, 200, r_pay.content)
        self.assertLess(elapsed, 1.0, f'confirm-payment took {elapsed:.2f}s; receipt should be async')
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.status, 'paid')
