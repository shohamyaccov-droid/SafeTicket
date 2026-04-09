"""
Full platform E2E (Django integration): CORS allowlist, registration, sell listing,
public browse, Buy Now checkout, ticket download.

Run: cd backend && python manage.py test test_full_platform_e2e -v 2
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket
from users.pricing import expected_buy_now_total

User = get_user_model()


def _minimal_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


@override_settings(DEBUG=False)
class FullPlatformE2ETest(TestCase):
    """Regression guard for CORS + core marketplace APIs (mirrors production DEBUG=False)."""

    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        future = timezone.now() + timedelta(days=90)
        self.artist = Artist.objects.create(name='E2E Full Platform Artist')
        self.event = Event.objects.create(
            name='E2E Full Platform Event',
            artist=self.artist,
            date=future,
            venue='אחר',
            city='Tel Aviv',
            country='US',
            category='concert',
        )

    def test_cors_allows_production_spa_origin_on_health(self):
        r = self.client.get(
            '/api/health/',
            HTTP_ORIGIN='https://safeticket-web.onrender.com',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            r.headers.get('Access-Control-Allow-Origin'),
            'https://safeticket-web.onrender.com',
        )

    def test_cors_allows_local_vite_origin(self):
        r = self.client.get('/api/health/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get('Access-Control-Allow-Origin'), 'http://localhost:5173')

    def test_full_platform_register_sell_browse_buy_confirm_download(self):
        suffix = uuid.uuid4().hex[:10]

        seller_reg = self.client.post(
            '/api/users/register/',
            {
                'username': f'e2e_seller_{suffix}',
                'email': f'e2e_seller_{suffix}@platform.test',
                'password': 'SecurePlatformE2E1!',
                'password2': 'SecurePlatformE2E1!',
                'role': 'seller',
            },
            format='json',
        )
        self.assertEqual(seller_reg.status_code, 201, seller_reg.content)
        seller_access = seller_reg.json().get('access')
        self.assertTrue(seller_access)

        buyer_reg = self.client.post(
            '/api/users/register/',
            {
                'username': f'e2e_buyer_{suffix}',
                'email': f'e2e_buyer_{suffix}@platform.test',
                'password': 'SecurePlatformE2E1!',
                'password2': 'SecurePlatformE2E1!',
                'role': 'buyer',
            },
            format='json',
        )
        self.assertEqual(buyer_reg.status_code, 201, buyer_reg.content)
        buyer_access = buyer_reg.json().get('access')
        self.assertTrue(buyer_access)

        pdf = SimpleUploadedFile(
            'listing.pdf',
            _minimal_pdf_bytes(),
            content_type='application/pdf',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {seller_access}')
        r_list = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '150.00',
                'listing_price': '150.00',
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

        self.client.credentials()
        pub = self.client.get(f'/api/users/events/{self.event.id}/tickets/')
        self.assertEqual(pub.status_code, 200, pub.content)
        raw = pub.json()
        rows = raw if isinstance(raw, list) else raw.get('results', [])
        self.assertTrue(any(int(x.get('id', 0)) == tid for x in rows), 'New ticket visible on event')
        row = next(x for x in rows if int(x.get('id', 0)) == tid)
        price_field = row.get('asking_price') or row.get('original_price') or row.get('price')
        self.assertIsNotNone(price_field)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {buyer_access}')
        ticket.refresh_from_db()
        qty = 1
        expected_total = expected_buy_now_total(ticket.asking_price, qty)

        pay_r = self.client.post(
            '/api/users/payments/simulate/',
            {
                'ticket_id': tid,
                'amount': str(expected_total),
                'quantity': qty,
            },
            format='json',
        )
        self.assertEqual(pay_r.status_code, 200, pay_r.content)
        self.assertTrue(pay_r.json().get('success'))

        order_r = self.client.post(
            '/api/users/orders/',
            {
                'ticket': tid,
                'total_amount': str(expected_total),
                'quantity': qty,
                'event_name': self.event.name,
            },
            format='json',
        )
        self.assertEqual(order_r.status_code, 201, order_r.content)
        body = order_r.json()
        oid = body['id']
        tok = body.get('payment_confirm_token')
        self.assertTrue(tok)

        conf = self.client.post(
            f'/api/users/orders/{oid}/confirm-payment/',
            {'mock_payment_ack': True, 'payment_confirm_token': tok},
            format='json',
        )
        self.assertEqual(conf.status_code, 200, conf.content)

        order = Order.objects.get(pk=oid)
        self.assertIn(order.status, ('paid', 'completed'))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'sold')

        dl = self.client.get(f'/api/users/tickets/{tid}/download_pdf/')
        self.assertEqual(dl.status_code, 200, dl.content[:200])
        ct = (dl.get('Content-Type') or '').split(';')[0].strip().lower()
        self.assertIn(
            ct,
            ('application/pdf', 'application/octet-stream', 'image/jpeg', 'image/png'),
        )
