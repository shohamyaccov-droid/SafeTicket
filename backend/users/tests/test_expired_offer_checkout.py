"""
Regression: accepted offers past checkout_expires_at must be rejected at checkout.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from users.models import Artist, Event, Offer, Ticket
from users.pricing import expected_negotiated_total_from_offer_base
from users.views import create_order

User = get_user_model()


class ExpiredOfferCheckoutTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='seller_exp',
            email='seller_exp@test.local',
            password='Pass12345!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='buyer_exp',
            email='buyer_exp@test.local',
            password='Pass12345!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Expiry Artist')
        self.event = Event.objects.create(
            name='Expiry Event',
            artist=artist,
            date=timezone.now() + timedelta(days=14),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            category='concert',
            status='פעיל',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            original_price=Decimal('200.00'),
            asking_price=Decimal('200.00'),
            status='active',
            available_quantity=1,
            delivery_method='instant',
        )
        now = timezone.now()
        self.offer = Offer.objects.create(
            buyer=self.buyer,
            ticket=self.ticket,
            amount=Decimal('180.00'),
            quantity=1,
            status='accepted',
            expires_at=now + timedelta(hours=48),
            accepted_at=now - timedelta(hours=25),
            checkout_expires_at=now - timedelta(minutes=5),
        )
        self.factory = APIRequestFactory()

    def test_authenticated_checkout_rejects_expired_accepted_offer(self):
        expected_total = expected_negotiated_total_from_offer_base(self.offer.amount)
        req = self.factory.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'quantity': 1,
                'offer_id': self.offer.id,
                'total_amount': str(expected_total),
                'accepted_terms': True,
            },
            format='json',
        )
        force_authenticate(req, user=self.buyer)
        resp = create_order(req)
        self.assertEqual(resp.status_code, 400, getattr(resp, 'data', resp))
        err = str(resp.data.get('error') if hasattr(resp, 'data') else resp)
        self.assertTrue('פגה' in err or 'expir' in err.lower() or 'אישור' in err, err)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, 'expired')
