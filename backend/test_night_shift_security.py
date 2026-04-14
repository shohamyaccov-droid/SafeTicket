"""
Night-shift security & edge-case regression tests.

Run: cd backend && python manage.py test test_night_shift_security -v 2
"""
from __future__ import annotations

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
from users.pricing import expected_buy_now_total
from users.ticket_download_tokens import build_ticket_download_token

User = get_user_model()


def _minimal_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


@override_settings(DEBUG=False)
class NightShiftSecurityTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.api.enforce_csrf_checks = False
        future = timezone.now() + timedelta(days=60)
        self.artist = Artist.objects.create(name='NightShift Artist')
        self.event = Event.objects.create(
            name='NightShift Event',
            artist=self.artist,
            date=future,
            venue='מנורה מבטחים',
            city='Tel Aviv',
            country='US',
            category='concert',
        )

    def test_anonymous_download_pdf_forbidden_without_token(self):
        seller = User.objects.create_user(
            username='ns_seller_dl',
            email='ns_seller_dl@test.invalid',
            password='x',
            role='seller',
        )
        pdf = SimpleUploadedFile('t.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        self.api.force_authenticate(seller)
        r = self.api.post(
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
        self.assertEqual(r.status_code, 201, r.content)
        tid = r.json()['id']
        self.api.force_authenticate(None)
        r0 = self.api.get(f'/api/users/tickets/{tid}/download_pdf/')
        self.assertEqual(r0.status_code, 403, r0.content)

    def test_guest_email_query_does_not_grant_download(self):
        seller = User.objects.create_user(
            username='ns_seller_em',
            email='ns_seller_em@test.invalid',
            password='x',
            role='seller',
        )
        buyer = User.objects.create_user(
            username='ns_buyer_em',
            email='ns_buyer_em@test.invalid',
            password='x',
            role='buyer',
        )
        pdf = SimpleUploadedFile('t2.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        self.api.force_authenticate(seller)
        r = self.api.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '80.00',
                'listing_price': '80.00',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, r.content)
        tid = r.json()['id']
        ticket = Ticket.objects.get(pk=tid)
        Order.objects.create(
            ticket=ticket,
            user=buyer,
            status='paid',
            total_amount=Decimal('100.00'),
            currency='ILS',
            quantity=1,
            event_name=self.event.name,
        )
        self.api.force_authenticate(None)
        r_bad = self.api.get(
            f'/api/users/tickets/{tid}/download_pdf/',
            {'email': buyer.email},
        )
        self.assertEqual(r_bad.status_code, 403, r_bad.content)

    def test_signed_dl_token_allows_anonymous_download(self):
        seller = User.objects.create_user(
            username='ns_seller_tok',
            email='ns_seller_tok@test.invalid',
            password='x',
            role='seller',
        )
        buyer = User.objects.create_user(
            username='ns_buyer_tok',
            email='ns_buyer_tok@test.invalid',
            password='x',
            role='buyer',
        )
        pdf = SimpleUploadedFile('t3.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        self.api.force_authenticate(seller)
        r = self.api.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '50.00',
                'listing_price': '50.00',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, r.content)
        tid = r.json()['id']
        ticket = Ticket.objects.get(pk=tid)
        order = Order.objects.create(
            ticket=ticket,
            user=buyer,
            status='paid',
            total_amount=Decimal('55.00'),
            currency='ILS',
            quantity=1,
            event_name=self.event.name,
        )
        tok = build_ticket_download_token(tid, order.id)
        self.api.force_authenticate(None)
        r_ok = self.api.get(f'/api/users/tickets/{tid}/download_pdf/', {'dl': tok})
        self.assertEqual(r_ok.status_code, 200, r_ok.content[:200])

    def test_cannot_reserve_others_active_cart_lock(self):
        a = User.objects.create_user(username='ns_a', email='ns_a@test.invalid', password='x', role='buyer')
        b = User.objects.create_user(username='ns_b', email='ns_b@test.invalid', password='x', role='buyer')
        seller = User.objects.create_user(
            username='ns_seller_r',
            email='ns_seller_r@test.invalid',
            password='x',
            role='seller',
        )
        pdf = SimpleUploadedFile('r.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        self.api.force_authenticate(seller)
        r = self.api.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '120.00',
                'listing_price': '120.00',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, r.content)
        tid = r.json()['id']

        self.api.force_authenticate(a)
        r1 = self.api.post(f'/api/users/tickets/{tid}/reserve/', {}, format='json')
        self.assertEqual(r1.status_code, 200, r1.content)

        self.api.force_authenticate(b)
        r2 = self.api.post(f'/api/users/tickets/{tid}/reserve/', {}, format='json')
        self.assertEqual(r2.status_code, 400, r2.content)

    def test_cannot_accept_offer_past_expires_at(self):
        seller = User.objects.create_user(
            username='ns_seller_o',
            email='ns_seller_o@test.invalid',
            password='SecureNs1!',
            role='seller',
        )
        buyer = User.objects.create_user(
            username='ns_buyer_o',
            email='ns_buyer_o@test.invalid',
            password='SecureNs1!',
            role='buyer',
        )
        pdf = SimpleUploadedFile('o.pdf', _minimal_pdf_bytes(), content_type='application/pdf')
        self.api.force_authenticate(seller)
        r = self.api.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '90.00',
                'listing_price': '90.00',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, r.content)
        tid = r.json()['id']

        self.api.force_authenticate(buyer)
        r_off = self.api.post('/api/users/offers/', {'ticket': tid, 'amount': '70.00', 'quantity': 1}, format='json')
        self.assertEqual(r_off.status_code, 201, r_off.content)
        oid = r_off.json()['id']
        off = Offer.objects.get(pk=oid)
        off.expires_at = timezone.now() - timedelta(hours=25)
        off.save(update_fields=['expires_at'])

        self.api.force_authenticate(seller)
        r_acc = self.api.post(f'/api/users/offers/{oid}/accept/', {}, format='json')
        self.assertEqual(r_acc.status_code, 400, r_acc.content)
