"""
Deploy-readiness smoke pass: critical checkout/payment API paths and bad-input guards.

Run before production launch:
  python manage.py test users.tests.test_deploy_smoke_pass
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from users.models import Artist, Event, Order, Ticket
from users.payme_views import payme_webhook
from users.pricing import expected_buy_now_total
from users.tests.payme_ipn_test_helpers import MockPayMeSaleConfirmMixin

User = get_user_model()


def _signed_payme_request(payload, secret='whsec_smoke'):
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return APIRequestFactory().post(
        '/api/payments/webhook/payme/',
        data=body,
        content_type='application/json',
        HTTP_X_PAYME_SIGNATURE=signature,
    )


class DeployReadinessSmokeTests(MockPayMeSaleConfirmMixin, TestCase):
    """End-to-end smoke coverage for launch-critical marketplace flows."""

    def setUp(self):
        self.client = APIClient()
        self.factory = APIRequestFactory()
        self.seller = User.objects.create_user(
            username='smoke_seller',
            email='smoke-seller@example.test',
            password='pass-12345',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='smoke_buyer',
            email='smoke-buyer@example.test',
            password='pass-12345',
        )
        self.artist = Artist.objects.create(name='Smoke Artist')
        self.event = Event.objects.create(
            name='Smoke Show',
            artist=self.artist,
            date=timezone.now() + timedelta(days=21),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        self.price = Decimal('200.00')
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=self.price,
            asking_price=self.price,
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/smoke-test.pdf',
        )

    def test_smoke_reserve_create_order_happy_path(self):
        self.client.force_authenticate(user=self.buyer)
        reserve = self.client.post(f'/api/users/tickets/{self.ticket.id}/reserve/', {}, format='json')
        self.assertEqual(reserve.status_code, 200, reserve.data)
        self.assertTrue(reserve.data.get('success'))

        checkout_total = expected_buy_now_total(self.price, 1)
        order_res = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'total_amount': str(checkout_total),
                'accepted_terms': True,
                'quantity': 1,
                'event_name': self.event.name,
            },
            format='json',
        )
        self.assertEqual(order_res.status_code, 201, order_res.data)
        self.assertEqual(order_res.data['status'], 'pending_payment')

    def test_smoke_guest_checkout_happy_path(self):
        guest_email = 'smoke-guest@example.test'
        reserve = self.client.post(
            f'/api/users/tickets/{self.ticket.id}/reserve/',
            {'email': guest_email},
            format='json',
        )
        self.assertEqual(reserve.status_code, 200, reserve.data)

        checkout_total = expected_buy_now_total(self.price, 1)
        guest_res = self.client.post(
            '/api/users/orders/guest/',
            {
                'guest_first_name': 'Smoke',
                'guest_last_name': 'Guest',
                'guest_email': guest_email,
                'guest_phone': '0501234567',
                'ticket_id': self.ticket.id,
                'total_amount': str(checkout_total),
                'quantity': 1,
                'event_name': self.event.name,
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertEqual(guest_res.status_code, 201, guest_res.data)
        order = Order.objects.get(pk=guest_res.data['id'])
        self.assertEqual(order.guest_email, guest_email)
        self.assertEqual(order.status, 'pending_payment')

    @override_settings(DEBUG=True, PAYME_IS_SANDBOX=True, PAYME_WEBHOOK_SECRET='whsec_smoke')
    def test_smoke_payme_webhook_success_and_duplicate_idempotent(self):
        self.ticket.status = 'reserved'
        self.ticket.reserved_by = self.buyer
        self.ticket.reserved_at = timezone.now()
        self.ticket.save(update_fields=['status', 'reserved_by', 'reserved_at', 'updated_at'])

        checkout_total = expected_buy_now_total(self.price, 1)
        order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            ticket_ids=[self.ticket.id],
            status='pending_payment',
            total_amount=checkout_total,
            currency='ILS',
            quantity=1,
            payme_transaction_id='txn_smoke_001',
            payme_status='initialized',
            payment_confirm_token='smoke-token',
        )
        payload = {
            'merchant_order_id': str(order.id),
            'transaction_id': 'txn_smoke_001',
            'sale_price': int(checkout_total * 100),
            'currency': 'ILS',
            'status': 'authorized',
        }

        first = payme_webhook(_signed_payme_request(payload))
        second = payme_webhook(_signed_payme_request(payload))
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(self.ticket.status, 'sold')

    def test_smoke_bad_input_does_not_500(self):
        missing_ticket = self.client.post(
            '/api/users/orders/',
            {'total_amount': '100', 'accepted_terms': True},
            format='json',
        )
        self.assertIn(missing_ticket.status_code, (400, 401))

        bad_guest = self.client.post(
            '/api/users/orders/guest/',
            {
                'guest_email': 'not-an-email',
                'ticket_id': self.ticket.id,
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertIn(bad_guest.status_code, (400, 401))

        bad_reserve = self.client.post('/api/users/tickets/999999/reserve/', {}, format='json')
        self.assertEqual(bad_reserve.status_code, 404)

        empty_webhook = payme_webhook(self.factory.post('/api/payments/webhook/payme/', {}, format='json'))
        self.assertIn(empty_webhook.status_code, (400, 403))

    def test_smoke_concurrent_reserve_second_buyer_blocked(self):
        from users.views import HE_TICKET_HELD_BY_OTHER, TicketViewSet

        reserve_view = TicketViewSet.as_view({'post': 'reserve'})
        req1 = self.factory.post(f'/tickets/{self.ticket.id}/reserve/', {})
        force_authenticate(req1, user=self.buyer)
        self.assertEqual(reserve_view(req1, pk=self.ticket.id).status_code, 200)

        other = User.objects.create_user(username='smoke_other', email='other@example.test', password='pass')
        req2 = self.factory.post(f'/tickets/{self.ticket.id}/reserve/', {})
        force_authenticate(req2, user=other)
        res2 = reserve_view(req2, pk=self.ticket.id)
        self.assertEqual(res2.status_code, 400)
        self.assertEqual(res2.data['error'], HE_TICKET_HELD_BY_OTHER)
