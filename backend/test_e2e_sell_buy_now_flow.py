"""
E2E: Seller multipart upload -> active listing -> buyer Buy Now -> payment confirm -> ticket sold.

Run: cd backend && python manage.py test test_e2e_sell_buy_now_flow -v 2

Assert: no 4xx/5xx on the happy path; final ticket status is sold (or unavailable to buyers).
"""
from __future__ import annotations

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from pypdf import PdfWriter
from rest_framework.test import APIClient
from users.models import Artist, Event, Ticket, Order
from users.pricing import expected_buy_now_total

User = get_user_model()


def _pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


class SellBuyNowE2EFlowTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        future = timezone.now() + timedelta(days=120)
        self.artist = Artist.objects.create(name='BuyNow E2E Artist')
        self.event = Event.objects.create(
            name='BuyNow Arena (E2E)',
            artist=self.artist,
            date=future,
            venue='אחר',
            city='NYC',
            country='US',
            category='concert',
        )
        self.seller = User.objects.create_user(
            username='e2e_bn_seller',
            password='testpass123',
            email='e2e_bn_seller@test.com',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='e2e_bn_buyer',
            password='testpass123',
            email='e2e_bn_buyer@test.com',
            role='buyer',
        )

    def test_seller_upload_then_buy_now_checkout_ticket_sold(self):
        pdf = SimpleUploadedFile('listing.pdf', _pdf_bytes(), content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r_list = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '200',
                'listing_price': '200',
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

        pub = self.client.get(f'/api/users/events/{self.event.id}/tickets/')
        self.assertEqual(pub.status_code, 200)
        pub_data = pub.json()
        pub_list = pub_data if isinstance(pub_data, list) else pub_data.get('results', [])
        self.assertTrue(any(x.get('id') == tid for x in pub_list), 'New ticket must appear on event listing')

        self.client.force_authenticate(None)
        self.client.force_authenticate(self.buyer)
        expected_total = expected_buy_now_total(ticket.asking_price, 1)

        pay_r = self.client.post(
            '/api/users/payments/simulate/',
            {
                'ticket_id': tid,
                'amount': str(expected_total),
                'quantity': 1,
            },
            format='json',
        )
        self.assertEqual(pay_r.status_code, 200, pay_r.content)

        order_r = self.client.post(
            '/api/users/orders/',
            {
                'ticket': tid,
                'total_amount': str(expected_total),
                'quantity': 1,
                'event_name': self.event.name,
            },
            format='json',
        )
        self.assertEqual(order_r.status_code, 201, order_r.content)
        order_body = order_r.json()
        oid = order_body['id']
        tok = order_body.get('payment_confirm_token')
        self.assertTrue(tok)

        conf = self.client.post(
            f'/api/users/orders/{oid}/confirm-payment/',
            {'mock_payment_ack': True, 'payment_confirm_token': tok},
            format='json',
        )
        self.assertEqual(conf.status_code, 200, conf.content)

        order = Order.objects.get(pk=oid)
        self.assertEqual(order.status, 'paid')
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'sold', 'Buy Now + confirm must mark ticket sold')
