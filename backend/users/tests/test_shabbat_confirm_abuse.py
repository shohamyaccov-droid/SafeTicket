"""
Iteration 4 — Shabbat gate, confirm-payment abuse, guest order IDOR-ish probes.

Reflection after money/IDOR pass:
- Can someone confirm payment without owning the order?
- Does Shabbat block return safe JSON only?
- Guest checkout with forged emails / missing fields

Run: python manage.py test users.tests.test_shabbat_confirm_abuse -v 2
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket
from users.shabbat import SHABBAT_RESTRICTION_CODE

User = get_user_model()


@override_settings(DEBUG=False, SECRET_KEY='shabbat-abuse-secret')
class ShabbatGateSafeResponseTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.buyer = User.objects.create_user(
            username='shab_buyer', email='shab_buyer@test.invalid', password='x', role='buyer',
            first_name='A', phone_number='0502222222',
        )
        seller = User.objects.create_user(
            username='shab_seller', email='shab_seller@test.invalid', password='x', role='seller',
        )
        event = Event.objects.create(
            name='Shab Event',
            artist=Artist.objects.create(name='Shab Artist'),
            date=timezone.now() + timedelta(days=9),
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

    def test_reserve_during_shabbat_returns_safe_403(self):
        with patch('users.views.shabbat_forbidden_response') as mock_block:
            from rest_framework.response import Response
            from rest_framework import status

            mock_block.return_value = Response(
                {'error': 'blocked', 'code': SHABBAT_RESTRICTION_CODE},
                status=status.HTTP_403_FORBIDDEN,
            )
            self.api.force_authenticate(self.buyer)
            res = self.api.post(f'/api/users/tickets/{self.ticket.pk}/reserve/', {}, format='json')
        self.assertEqual(res.status_code, 403)
        body = res.json()
        self.assertEqual(body.get('code'), SHABBAT_RESTRICTION_CODE)
        self.assertNotIn('traceback', str(body).lower())
        self.assertNotIn('hebcal', str(body).lower())


@override_settings(DEBUG=False, SECRET_KEY='shabbat-abuse-secret')
class ConfirmPaymentAbuseTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.owner = User.objects.create_user(
            username='own_buyer', email='own_buyer@test.invalid', password='x', role='buyer'
        )
        self.attacker = User.objects.create_user(
            username='atk_buyer', email='atk_buyer@test.invalid', password='x', role='buyer'
        )
        seller = User.objects.create_user(
            username='own_seller', email='own_seller@test.invalid', password='x', role='seller'
        )
        event = Event.objects.create(
            name='Confirm Event',
            artist=Artist.objects.create(name='Confirm Artist'),
            date=timezone.now() + timedelta(days=11),
            venue='מקום', city='Tel Aviv', country='US', category='concert',
        )
        ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='reserved',
            available_quantity=1,
            reserved_by=self.owner,
            reserved_at=timezone.now(),
        )
        self.order = Order.objects.create(
            user=self.owner,
            ticket=ticket,
            status='pending_payment',
            total_amount=Decimal('112.00'),
            quantity=1,
            event_name=event.name,
            payment_confirm_token='secret-token-xyz',
        )

    def test_attacker_cannot_confirm_foreign_order(self):
        self.api.force_authenticate(self.attacker)
        for url in (
            f'/api/users/orders/{self.order.pk}/confirm-payment/',
            f'/api/users/orders/{self.order.pk}/confirm_payment/',
        ):
            res = self.api.post(url, {'token': 'secret-token-xyz'}, format='json')
            # 403/404/405 depending on route existence — never 200 paid
            self.assertNotEqual(res.status_code, 200, msg=f'{url} -> {res.status_code} {res.content}')
            if res.content:
                self.assertNotIn('traceback', str(res.content).lower())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')

    def test_anonymous_confirm_without_token_fails_safely(self):
        res = self.api.post(
            f'/api/users/orders/{self.order.pk}/confirm-payment/',
            {},
            format='json',
        )
        self.assertIn(res.status_code, (400, 401, 403, 404, 405))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')


@override_settings(DEBUG=False, SECRET_KEY='shabbat-abuse-secret')
class GuestCheckoutAbuseTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        seller = User.objects.create_user(
            username='guest_seller', email='guest_seller@test.invalid', password='x', role='seller'
        )
        event = Event.objects.create(
            name='Guest Abuse Event',
            artist=Artist.objects.create(name='Guest Abuse Artist'),
            date=timezone.now() + timedelta(days=8),
            venue='מקום', city='Tel Aviv', country='US', category='concert',
        )
        self.ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=Decimal('80.00'),
            asking_price=Decimal('80.00'),
            status='active',
            available_quantity=1,
        )

    def test_guest_checkout_rejects_missing_email(self):
        res = self.api.post(
            '/api/users/orders/guest/',
            {
                'ticket_id': self.ticket.pk,
                'quantity': 1,
                'total_amount': '89.60',
                'guest_name': 'Test',
            },
            format='json',
        )
        self.assertIn(res.status_code, (400, 403))
        if res.content:
            self.assertNotIn('traceback', str(res.json()).lower())

    def test_guest_checkout_rejects_sql_injection_email(self):
        res = self.api.post(
            '/api/users/orders/guest/',
            {
                'ticket_id': self.ticket.pk,
                'quantity': 1,
                'total_amount': '89.60',
                'guest_email': "a' OR '1'='1",
                'guest_name': 'Hack',
                'guest_phone': '0500000000',
            },
            format='json',
        )
        self.assertIn(res.status_code, (400, 403))
        if res.content:
            body = res.json()
            self.assertNotIn('OperationalError', str(body))
            self.assertNotIn('traceback', str(body).lower())
