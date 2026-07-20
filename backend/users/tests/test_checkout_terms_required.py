"""Buyer checkout must require TOS acceptance before order creation."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket
from users.pricing import expected_buy_now_total

User = get_user_model()


@override_settings(DEBUG=False, SECRET_KEY='tos-checkout-secret')
class CheckoutTermsRequiredTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        seller = User.objects.create_user(
            username='tos_seller', email='tos_seller@test.invalid', password='x', role='seller'
        )
        self.buyer = User.objects.create_user(
            username='tos_buyer', email='tos_buyer@test.invalid', password='x', role='buyer',
            first_name='B', phone_number='0501111111',
        )
        event = Event.objects.create(
            name='TOS Event',
            artist=Artist.objects.create(name='TOS Artist'),
            date=timezone.now() + timedelta(days=12),
            venue='מקום', city='Tel Aviv', country='US', category='concert',
        )
        self.ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='active',
            available_quantity=1,
        )
        self.total = expected_buy_now_total(self.ticket.asking_price, 1)

    def test_create_order_rejects_without_accepted_terms(self):
        self.api.force_authenticate(self.buyer)
        self.api.post(f'/api/users/tickets/{self.ticket.pk}/reserve/', {}, format='json')
        res = self.api.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.pk,
                'quantity': 1,
                'total_amount': str(self.total),
                'accepted_terms': False,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('תקנון', str(res.json()))

    def test_guest_checkout_rejects_without_accepted_terms(self):
        res = self.api.post(
            '/api/users/orders/guest/',
            {
                'guest_first_name': 'ישראל',
                'guest_last_name': 'ישראלי',
                'guest_email': 'guest_tos@test.invalid',
                'guest_phone': '0501234567',
                'ticket_id': self.ticket.pk,
                'quantity': 1,
                'total_amount': str(self.total),
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        body = res.json()
        raw = str(body)
        self.assertTrue('accepted_terms' in raw or 'תקנון' in raw)
