"""
UK (GBP) negotiation E2E: listing → offer → counter → accept → checkout → confirm payment.
Run: cd backend && python manage.py test test_uk_negotiation_currency_e2e -v 2
"""
from __future__ import annotations

from io import BytesIO
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
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


class UkNegotiationCurrencyE2ETest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        self.starts = timezone.now() + timedelta(days=60)
        self.ends = self.starts + timedelta(hours=3)
        self.artist = Artist.objects.create(name='UK QA Artist')
        self.event = Event.objects.create(
            name='London Arena Show',
            artist=self.artist,
            date=self.starts,
            ends_at=self.ends,
            venue='אחר',
            city='London',
            country='GB',
            category='concert',
        )
        self.seller = User.objects.create_user(
            username='uk_seller_e2e',
            password='pass12345',
            email='ukseller@e2e.test',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='uk_buyer_e2e',
            password='pass12345',
            email='ukbuyer@e2e.test',
            role='buyer',
        )

    def test_uk_full_negotiation_gbp_checkout_and_escrow(self):
        log = []
        def line(msg):
            log.append(msg)
            print(msg)

        line('=== UK Negotiation E2E (GBP) ===')

        # Step A — Sell listing £500 face £100, no receipt (GB)
        pdf = SimpleUploadedFile('tix.pdf', _pdf_bytes(), content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r_list = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '100',
                'listing_price': '500',
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
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.receipt_file.name if ticket.receipt_file else None)
        self.assertEqual(ticket.asking_price, Decimal('500.00'))
        line('[A] Listing created ticket_id=%s asking=500 GBP face=100 GBP status=active no_receipt=OK' % tid)

        # Step B — Buyer offers £420
        self.client.force_authenticate(self.buyer)
        r_off = self.client.post(
            '/api/users/offers/',
            {'ticket': tid, 'amount': '420', 'quantity': 1},
            format='json',
        )
        self.assertEqual(r_off.status_code, 201, r_off.content)
        offer0 = r_off.json()
        oid0 = offer0['id']
        self.assertEqual(offer0.get('currency'), 'GBP')
        line(f'[B] Buyer offer id={oid0} amount=420 GBP currency=GBP')

        # Step C — Seller counters £480
        self.client.force_authenticate(self.seller)
        r_co = self.client.post(
            f'/api/users/offers/{oid0}/counter/',
            {'amount': '480'},
            format='json',
        )
        self.assertEqual(r_co.status_code, 201, r_co.content)
        counter = r_co.json()
        oid1 = counter['id']
        self.assertEqual(counter.get('currency'), 'GBP')
        line(f'[C] Seller counter offer id={oid1} amount=480 GBP currency=GBP')

        # Buyer accepts counter
        self.client.force_authenticate(self.buyer)
        r_acc = self.client.post(f'/api/users/offers/{oid1}/accept/', {}, format='json')
        self.assertEqual(r_acc.status_code, 200, r_acc.content)
        line(f'[C2] Buyer accepted offer {oid1}')

        # Step D — Checkout totals: £480 + 10% = £528
        base, fee, total = buyer_charge_from_base_amount(Decimal('480'))
        self.assertEqual(float(fee), 48.0)
        self.assertEqual(float(total), 528.0)
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
        order_payload = r_ord.json()
        order_id = order_payload['id']
        line(f'[D] Order {order_id} created total={total} GBP (base 480 GBP + fee {fee} GBP)')

        tok = order_payload.get('payment_confirm_token')
        self.assertTrue(tok)
        r_pay = self.client.post(
            f'/api/users/orders/{order_id}/confirm-payment/',
            {'mock_payment_ack': True},
            format='json',
        )
        self.assertEqual(r_pay.status_code, 200, r_pay.content)
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.currency, 'GBP')
        self.assertEqual(order.buyer_service_fee, Decimal('48.00'))
        self.assertEqual(order.total_paid_by_buyer, Decimal('528.00'))
        line(f'[D2] Paid: currency={order.currency} fee={order.buyer_service_fee} total={order.total_paid_by_buyer}')

        # Step E — Escrow: 24h after ends_at
        expected_eligible = self.ends + timedelta(hours=24)
        self.assertIsNotNone(order.payout_eligible_date)
        self.assertEqual(order.payout_eligible_date, expected_eligible)
        line(f'[E] payout_eligible_date={order.payout_eligible_date.isoformat()} (ends_at+24h)')

        line('=== UK E2E PASS ===')
        for ln in log:
            print('LOG:', ln)
