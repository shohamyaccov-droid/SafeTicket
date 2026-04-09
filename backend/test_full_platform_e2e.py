"""
Full platform E2E (Django integration): CORS allowlist, registration, sell listing,
public browse, Buy Now checkout, guest checkout, negotiation → pay, ticket download.

Run: cd backend && python manage.py test test_full_platform_e2e -v 2
"""
from __future__ import annotations

import json
import uuid
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.test import APIClient

from users.models import Artist, Event, Offer, Order, Ticket
from users.pricing import buyer_charge_from_base_amount, expected_buy_now_total, expected_negotiated_total_from_offer_base

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
        self.api = APIClient()
        self.api.enforce_csrf_checks = False
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

    def _guest_csrf_post(self, path: str, payload: dict):
        """Guest POST with session CSRF (mobile / SPA parity)."""
        r0 = self.api.get('/api/users/csrf/')
        self.assertEqual(r0.status_code, 200, r0.content)
        token = r0.cookies.get('csrftoken')
        self.assertIsNotNone(token)
        return self.api.post(
            path,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token.value,
        )

    def _guest_csrf_confirm(self, order_id: int, guest_email: str):
        r0 = self.api.get('/api/users/csrf/')
        self.assertEqual(r0.status_code, 200)
        token = r0.cookies.get('csrftoken')
        self.assertIsNotNone(token)
        return self.api.post(
            f'/api/users/orders/{order_id}/confirm-payment/',
            data=json.dumps({'mock_payment_ack': True, 'guest_email': guest_email}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token.value,
        )

    def test_cors_allows_production_spa_origin_on_health(self):
        r = self.api.get(
            '/api/health/',
            HTTP_ORIGIN='https://safeticket-web.onrender.com',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            r.headers.get('Access-Control-Allow-Origin'),
            'https://safeticket-web.onrender.com',
        )

    def test_cors_allows_local_vite_origin(self):
        r = self.api.get('/api/health/', HTTP_ORIGIN='http://localhost:5173')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get('Access-Control-Allow-Origin'), 'http://localhost:5173')

    def test_full_platform_register_sell_browse_buy_confirm_download(self):
        suffix = uuid.uuid4().hex[:10]

        seller_reg = self.api.post(
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

        buyer_reg = self.api.post(
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
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {seller_access}')
        r_list = self.api.post(
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

        self.api.credentials()
        pub = self.api.get(f'/api/users/events/{self.event.id}/tickets/')
        self.assertEqual(pub.status_code, 200, pub.content)
        raw = pub.json()
        rows = raw if isinstance(raw, list) else raw.get('results', [])
        self.assertTrue(any(int(x.get('id', 0)) == tid for x in rows), 'New ticket visible on event')
        row = next(x for x in rows if int(x.get('id', 0)) == tid)
        price_field = row.get('asking_price') or row.get('original_price') or row.get('price')
        self.assertIsNotNone(price_field)

        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {buyer_access}')
        ticket.refresh_from_db()
        qty = 1
        expected_total = expected_buy_now_total(ticket.asking_price, qty)

        pay_r = self.api.post(
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

        order_r = self.api.post(
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

        conf = self.api.post(
            f'/api/users/orders/{oid}/confirm-payment/',
            {'mock_payment_ack': True, 'payment_confirm_token': tok},
            format='json',
        )
        self.assertEqual(conf.status_code, 200, conf.content)

        order = Order.objects.get(pk=oid)
        self.assertIn(order.status, ('paid', 'completed'))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'sold')

        dl = self.api.get(f'/api/users/tickets/{tid}/download_pdf/')
        self.assertEqual(dl.status_code, 200, dl.content[:200])
        ct = (dl.get('Content-Type') or '').split(';')[0].strip().lower()
        self.assertIn(
            ct,
            ('application/pdf', 'application/octet-stream', 'image/jpeg', 'image/png'),
        )

    def test_registered_seller_guest_buyer_buy_now_csrf_checkout(self):
        """FLOW A: seller JWT listing; anonymous guest CSRF checkout + confirm (simulated card path)."""
        suffix = uuid.uuid4().hex[:10]
        reg = self.api.post(
            '/api/users/register/',
            {
                'username': f'e2e_guest_flow_s_{suffix}',
                'email': f'e2e_guest_flow_s_{suffix}@platform.test',
                'password': 'SecurePlatformE2E1!',
                'password2': 'SecurePlatformE2E1!',
                'role': 'seller',
            },
            format='json',
        )
        self.assertEqual(reg.status_code, 201, reg.content)
        seller_access = reg.json()['access']

        pdf = SimpleUploadedFile('g.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {seller_access}')
        r_list = self.api.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '100.00',
                'listing_price': '100.00',
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
        guest_email = f'guest_buyer_{suffix}@platform.test'
        expected_total = expected_buy_now_total(ticket.asking_price, 1)

        self.api.credentials()
        gc = self._guest_csrf_post(
            '/api/users/orders/guest/',
            {
                'guest_email': guest_email,
                'guest_phone': '0501234567',
                'ticket_id': tid,
                'total_amount': str(expected_total),
                'quantity': 1,
                'event_name': self.event.name,
            },
        )
        self.assertEqual(gc.status_code, 201, gc.content)
        oid = gc.json()['id']
        self.assertTrue(gc.json().get('payment_confirm_token'))

        cf = self._guest_csrf_confirm(oid, guest_email)
        self.assertEqual(cf.status_code, 200, cf.content)
        self.assertIn(cf.json().get('status'), ('paid', 'completed'))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'sold')

    def test_negotiation_counter_accept_registered_checkout(self):
        """FLOW B: offer → seller counter → buyer accept → simulate payment → order → confirm."""
        suffix = uuid.uuid4().hex[:10]
        seller = User.objects.create_user(
            username=f'e2e_neg_s_{suffix}',
            email=f'e2e_neg_s_{suffix}@platform.test',
            password='SecurePlatformE2E1!',
            role='seller',
        )
        buyer = User.objects.create_user(
            username=f'e2e_neg_b_{suffix}',
            email=f'e2e_neg_b_{suffix}@platform.test',
            password='SecurePlatformE2E1!',
            role='buyer',
        )
        pdf = SimpleUploadedFile('neg.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        self.api.force_authenticate(seller)
        r_list = self.api.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '200.00',
                'listing_price': '200.00',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r_list.status_code, 201, r_list.content)
        tid = r_list.json()['id']

        self.api.force_authenticate(buyer)
        r_off = self.api.post(
            '/api/users/offers/',
            {'ticket': tid, 'amount': '150.00', 'quantity': 1},
            format='json',
        )
        self.assertEqual(r_off.status_code, 201, r_off.content)
        oid0 = r_off.json()['id']

        self.api.force_authenticate(seller)
        r_co = self.api.post(
            f'/api/users/offers/{oid0}/counter/',
            {'amount': '180.00'},
            format='json',
        )
        self.assertEqual(r_co.status_code, 201, r_co.content)
        oid1 = r_co.json()['id']

        self.api.force_authenticate(buyer)
        r_acc = self.api.post(f'/api/users/offers/{oid1}/accept/', {}, format='json')
        self.assertEqual(r_acc.status_code, 200, r_acc.content)
        self.assertEqual(Offer.objects.filter(pk=oid1, status='accepted').count(), 1)

        ticket = Ticket.objects.get(pk=tid)
        # Listings from API always get listing_group_id; accept() may keep status active until checkout.
        self.assertIn(ticket.status, ('active', 'reserved'))

        neg_total = expected_negotiated_total_from_offer_base(Decimal('180.00'))
        pay_r = self.api.post(
            '/api/users/payments/simulate/',
            {
                'ticket_id': tid,
                'amount': str(neg_total),
                'quantity': 1,
                'offer_id': oid1,
            },
            format='json',
        )
        self.assertEqual(pay_r.status_code, 200, pay_r.content)

        order_r = self.api.post(
            '/api/users/orders/',
            {
                'ticket': tid,
                'quantity': 1,
                'total_amount': str(neg_total),
                'event_name': self.event.name,
                'offer_id': oid1,
            },
            format='json',
        )
        self.assertEqual(order_r.status_code, 201, order_r.content)
        order_id = order_r.json()['id']
        tok = order_r.json().get('payment_confirm_token')
        conf = self.api.post(
            f'/api/users/orders/{order_id}/confirm-payment/',
            {'mock_payment_ack': True, 'payment_confirm_token': tok},
            format='json',
        )
        self.assertEqual(conf.status_code, 200, conf.content)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'sold')
        _, fee, total = buyer_charge_from_base_amount(Decimal('180.00'))
        self.assertEqual(total, neg_total)
        self.assertEqual(fee, Decimal('18.00'))
