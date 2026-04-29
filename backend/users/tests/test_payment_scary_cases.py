import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from users.models import Artist, Event, Order, Ticket
from users.payme_views import payme_webhook
from users.views import TicketViewSet, create_order


User = get_user_model()


def _signed_payme_request(payload, secret='whsec_test'):
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return APIRequestFactory().post(
        '/api/payments/webhook/',
        data=body,
        content_type='application/json',
        HTTP_X_PAYME_SIGNATURE=signature,
    )


class PaymentScaryCaseTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.seller = User.objects.create_user(
            username='seller-scary',
            email='seller-scary@example.com',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='buyer-scary',
            email='buyer-scary@example.com',
            password='pass',
        )
        self.other_buyer = User.objects.create_user(
            username='buyer-attacker',
            email='buyer-attacker@example.com',
            password='pass',
        )
        self.artist = Artist.objects.create(name='Scary Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Scary Show',
            date=timezone.now() + timedelta(days=30),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
        )

    def _ticket(self, **overrides):
        base = {
            'seller': self.seller,
            'event': self.event,
            'original_price': Decimal('100'),
            'asking_price': Decimal('100'),
            'pdf_file': 'tickets/pdfs/test.pdf',
            'status': 'reserved',
            'verification_status': 'מאומת',
            'available_quantity': 1,
            'reserved_by': self.buyer,
            'reserved_at': timezone.now(),
        }
        base.update(overrides)
        return Ticket.objects.create(**base)

    @override_settings(PAYME_WEBHOOK_SECRET='whsec_test')
    def test_payme_duplicate_success_webhook_is_idempotent(self):
        ticket = self._ticket()
        order = Order.objects.create(
            user=self.buyer,
            ticket=ticket,
            ticket_ids=[ticket.id],
            status='pending_payment',
            total_amount=Decimal('110.00'),
            currency='ILS',
            quantity=1,
            payme_transaction_id='txn_dup_123',
            payme_status='initialized',
            payment_confirm_token='token',
        )
        payload = {
            'merchant_order_id': str(order.id),
            'transaction_id': 'txn_dup_123',
            'sale_price': 11000,
            'currency': 'ILS',
            'status': 'authorized',
        }

        first = payme_webhook(_signed_payme_request(payload))
        second = payme_webhook(_signed_payme_request(payload))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        order.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertIsNone(order.payment_confirm_token)
        self.assertEqual(ticket.status, 'sold')
        self.assertEqual(Order.objects.filter(pk=order.pk).count(), 1)

    def test_guest_release_attack_does_not_release_reservation(self):
        ticket = self._ticket(
            reserved_by=None,
            reservation_email='victim@example.com',
        )
        view = TicketViewSet.as_view({'post': 'release_reservation'})

        request = self.factory.post(
            f'/tickets/{ticket.id}/release_reservation/',
            {'email': 'attacker@example.com'},
            format='json',
        )
        response = view(request, pk=ticket.id)

        self.assertIn(response.status_code, (401, 403))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertEqual(ticket.reservation_email, 'victim@example.com')

    def test_checkout_double_click_reuses_existing_pending_order(self):
        ticket = self._ticket()
        payload = {
            'ticket': ticket.id,
            'total_amount': '110.00',
            'quantity': 1,
        }

        req1 = self.factory.post('/api/users/orders/', payload, format='json')
        force_authenticate(req1, user=self.buyer)
        res1 = create_order(req1)
        self.assertEqual(res1.status_code, 201)

        req2 = self.factory.post('/api/users/orders/', payload, format='json')
        force_authenticate(req2, user=self.buyer)
        res2 = create_order(req2)

        self.assertEqual(res2.status_code, 201)
        self.assertEqual(res2.data['id'], res1.data['id'])
        self.assertEqual(
            Order.objects.filter(user=self.buyer, status='pending_payment', ticket_ids=[ticket.id]).count(),
            1,
        )
