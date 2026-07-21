"""
Iteration 3 — checkout price tampering, IDOR, admin gate, coupon claim race.

Reflection: after pricing/escrow pass, attackers often:
- POST a lower total_amount than the server expects
- Access another user's order / payout
- Hit admin APIs as a normal user
- Double-claim the same affiliate coupon concurrently

Run: python manage.py test users.tests.test_checkout_idor_tamper -v 2
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
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


def _pdf():
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return SimpleUploadedFile('t.pdf', buf.getvalue(), content_type='application/pdf')


@override_settings(DEBUG=False, SECRET_KEY='tamper-secret-key')
class CheckoutPriceTamperTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.seller = User.objects.create_user(
            username='tamper_seller', email='tamper_seller@test.invalid', password='x', role='seller'
        )
        self.buyer = User.objects.create_user(
            username='tamper_buyer', email='tamper_buyer@test.invalid', password='x', role='buyer',
            first_name='B', phone_number='0501111111',
        )
        event = Event.objects.create(
            name='Tamper Event',
            artist=Artist.objects.create(name='Tamper Artist'),
            date=timezone.now() + timedelta(days=14),
            venue='מקום', city='Tel Aviv', country='US', category='concert',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=Decimal('200.00'),
            asking_price=Decimal('200.00'),
            status='active',
            available_quantity=1,
        )
        self.expected = expected_buy_now_total(self.ticket.asking_price, 1)

    def test_underpay_total_rejected(self):
        self.api.force_authenticate(self.buyer)
        # Reserve first (many flows require it)
        self.api.post(f'/api/users/tickets/{self.ticket.pk}/reserve/', {}, format='json')
        under = (self.expected - Decimal('50.00')).quantize(Decimal('0.01'))
        res = self.api.post(
            '/api/users/orders/',
            {
                'ticket_id': self.ticket.pk,
                'quantity': 1,
                'total_amount': str(under),
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertIn(res.status_code, (400, 403, 409), msg=res.content)
        self.assertFalse(Order.objects.filter(ticket=self.ticket, status='pending_payment', total_amount=under).exists())
        body = res.json()
        self.assertNotIn('traceback', str(body).lower())

    def test_wrong_type_total_rejected(self):
        self.api.force_authenticate(self.buyer)
        self.api.post(f'/api/users/tickets/{self.ticket.pk}/reserve/', {}, format='json')
        res = self.api.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.pk,
                'quantity': 1,
                'total_amount': ['not', 'a', 'number'],
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertIn(res.status_code, (400, 403, 415))
        if res.content:
            self.assertNotIn('traceback', str(res.json()).lower())


@override_settings(DEBUG=False, SECRET_KEY='tamper-secret-key')
class IdorAndAdminGateTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.seller = User.objects.create_user(
            username='idor_seller', email='idor_seller@test.invalid', password='x', role='seller'
        )
        self.buyer = User.objects.create_user(
            username='idor_buyer', email='idor_buyer@test.invalid', password='x', role='buyer'
        )
        self.other = User.objects.create_user(
            username='idor_other', email='idor_other@test.invalid', password='x', role='buyer'
        )
        event = Event.objects.create(
            name='IDOR Event',
            artist=Artist.objects.create(name='IDOR Artist'),
            date=timezone.now() + timedelta(days=21),
            venue='מקום', city='Tel Aviv', country='US', category='concert',
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
            pdf_file=_pdf(),
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='paid',
            total_amount=Decimal('112.00'),
            quantity=1,
            event_name=event.name,
        )

    def test_other_user_cannot_download_buyer_pdf(self):
        self.api.force_authenticate(self.other)
        res = self.api.get(f'/api/users/tickets/{self.ticket.pk}/download_pdf/')
        self.assertEqual(res.status_code, 403)
        self.assertNotIn('traceback', str(res.content).lower())

    def test_non_admin_cannot_list_payouts(self):
        self.api.force_authenticate(self.buyer)
        res = self.api.get('/api/users/admin/payouts/')
        self.assertEqual(res.status_code, 403)
        self.assertNotIn('traceback', str(res.json()).lower())

    def test_anonymous_admin_payouts_forbidden(self):
        res = self.api.get('/api/users/admin/payouts/')
        self.assertIn(res.status_code, (401, 403))


@override_settings(DEBUG=False, SECRET_KEY='tamper-secret-key')
class CouponValidateAbuseTests(TestCase):
    def test_validate_malicious_payloads_safe(self):
        client = APIClient()
        for payload in (
            {'code': 'NOPE', 'base_amount': -100},
            {'code': 'NOPE', 'base_amount': 'NaN'},
            {'code': {'$gt': ''}, 'base_amount': 100},
            {'code': 'NOPE', 'base_amount': 100, 'guest_email': 'a' * 10000},
            {'code': None, 'base_amount': None},
        ):
            res = client.post('/api/users/coupons/validate/', payload, format='json')
            self.assertIn(res.status_code, (200, 400, 404, 429), msg=payload)
            if res.content:
                body = res.json()
                self.assertNotIn('traceback', str(body).lower())
                self.assertNotIn('IntegrityError', str(body))
