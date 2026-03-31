"""
Option A QA: IL → pending_approval + receipt + price cap; global → active + open pricing.

Run:
  cd backend
  python il_global_ticket_approval_qa.py
# or
  python manage.py test users.tests.test_il_global_approval_qa -v 2
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

from users.models import Artist, Event, Ticket

User = get_user_model()


def _pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


class IlGlobalApprovalQATest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        future = timezone.now() + timedelta(days=120)
        self.artist = Artist.objects.create(name='QA Geo Artist')
        self.event_il = Event.objects.create(
            name='QA IL Concert',
            artist=self.artist,
            date=future,
            venue='אחר',
            city='Tel Aviv',
            country='IL',
        )
        self.event_us = Event.objects.create(
            name='QA US Show',
            artist=self.artist,
            date=future,
            venue='אחר',
            city='New York',
            country='US',
        )
        self.seller = User.objects.create_user(
            username='qa_geoseller',
            password='testpass123',
            email='geoseller@qa.test',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='qa_geobuyer',
            password='testpass123',
            email='geobuyer@qa.test',
            role='buyer',
        )
        self.admin = User.objects.create_user(
            username='qa_geoadmin',
            password='testpass123',
            email='geoadmin@qa.test',
            is_staff=True,
        )

    def test_case_a_il_price_above_face_rejected(self):
        b = _pdf_bytes()
        pdf = SimpleUploadedFile('ticket.pdf', b, content_type='application/pdf')
        receipt = SimpleUploadedFile('rcpt.pdf', b, content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event_il.id,
                'original_price': '100',
                'listing_price': '200',
                'il_legal_declaration': 'true',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'receipt_file': receipt,
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r.content))

    def test_case_a_il_missing_receipt_rejected(self):
        b = _pdf_bytes()
        pdf = SimpleUploadedFile('ticket.pdf', b, content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event_il.id,
                'original_price': '100',
                'listing_price': '100',
                'il_legal_declaration': 'true',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 400, getattr(r, 'data', r.content))

    def test_case_a_il_valid_then_approve_and_offer(self):
        b = _pdf_bytes()
        pdf = SimpleUploadedFile('ticket.pdf', b, content_type='application/pdf')
        receipt = SimpleUploadedFile('rcpt.pdf', b, content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event_il.id,
                'original_price': '100',
                'listing_price': '95',
                'il_legal_declaration': 'true',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'receipt_file': receipt,
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', r.content))
        tid = r.data['id']
        ticket = Ticket.objects.get(pk=tid)
        self.assertEqual(ticket.status, 'pending_approval')

        pub = self.client.get(f'/api/users/events/{self.event_il.id}/tickets/')
        self.assertEqual(pub.status_code, 200)
        pub_ids = [x['id'] for x in pub.data] if isinstance(pub.data, list) else []
        self.assertNotIn(tid, pub_ids)

        self.client.force_authenticate(self.admin)
        appr = self.client.post(f'/api/users/admin/tickets/{tid}/approve/', {}, format='json')
        self.assertEqual(appr.status_code, 200, getattr(appr, 'data', appr.content))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')

        pub2 = self.client.get(f'/api/users/events/{self.event_il.id}/tickets/')
        self.assertEqual(pub2.status_code, 200)
        pub_ids2 = [x['id'] for x in pub2.data] if isinstance(pub2.data, list) else []
        self.assertIn(tid, pub_ids2)

        self.client.force_authenticate(self.buyer)
        off = self.client.post(
            '/api/users/offers/',
            {'ticket': tid, 'amount': '95.00', 'quantity': 1},
            format='json',
        )
        self.assertEqual(off.status_code, 201, getattr(off, 'data', off.content))

    def test_case_b_us_open_pricing_active_no_receipt(self):
        b = _pdf_bytes()
        pdf = SimpleUploadedFile('ticket.pdf', b, content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event_us.id,
                'original_price': '100',
                'listing_price': '250',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', r.content))
        tid = r.data['id']
        ticket = Ticket.objects.get(pk=tid)
        self.assertEqual(ticket.status, 'active')
        self.assertGreater(ticket.asking_price, ticket.original_price)

        pub = self.client.get(f'/api/users/events/{self.event_us.id}/tickets/')
        self.assertEqual(pub.status_code, 200)
        pub_ids = [x['id'] for x in pub.data] if isinstance(pub.data, list) else []
        self.assertIn(tid, pub_ids)
