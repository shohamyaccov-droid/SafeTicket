from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from users.models import Artist, Event, Offer, Order, Ticket
from users.pricing import expected_buy_now_total
from users.views import OfferViewSet, confirm_order_payment, create_order

User = get_user_model()


def _user(username, role='buyer'):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='pass',
        role=role,
    )


class OfferAcceptInventoryLockTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.seller = _user('seller_lock', role='seller')
        self.offer_buyer = _user('offer_buyer_lock', role='buyer')
        self.other_buyer = _user('other_buyer_lock', role='buyer')

        self.artist = Artist.objects.create(name='Lock Inventory Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Lock Inventory Event',
            date=timezone.now() + timedelta(days=30),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )

        self.listing_group_id = 'lock-inv-group-1'
        self.t1 = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file='tickets/pdfs/test.pdf',
            status='active',
            verification_status='מאומת',
            available_quantity=1,
            listing_group_id=self.listing_group_id,
        )
        self.t2 = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file='tickets/pdfs/test.pdf',
            status='active',
            verification_status='מאומת',
            available_quantity=1,
            listing_group_id=self.listing_group_id,
        )

        self.offer = Offer.objects.create(
            buyer=self.offer_buyer,
            ticket=self.t1,
            amount=Decimal('90.00'),
            quantity=2,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1),
        )

    def test_accept_offer_keeps_listing_active_and_allows_competing_buy_now(self):
        """Accepted offer is a price agreement only — inventory stays marketplace-visible."""
        accept_view = OfferViewSet.as_view({'post': 'accept'})
        req = self.factory.post(f'/offers/{self.offer.id}/accept/', {})
        force_authenticate(req, user=self.seller)

        res = accept_view(req, pk=self.offer.id)
        self.assertEqual(res.status_code, 200, res.data)

        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, 'accepted')
        self.assertEqual(self.t1.status, 'active')
        self.assertEqual(self.t2.status, 'active')
        self.assertIsNone(self.t1.reserved_by_id)
        self.assertIsNone(self.t2.reserved_by_id)

        buy_payload = {
            'ticket': self.t1.id,
            'listing_group_id': self.listing_group_id,
            'quantity': 2,
            'total_amount': str(expected_buy_now_total(self.t1.asking_price, 2)),
            'accepted_terms': True,
        }
        buy_req = self.factory.post('/api/users/orders/', buy_payload, format='json')
        force_authenticate(buy_req, user=self.other_buyer)

        buy_res = create_order(buy_req)
        self.assertEqual(buy_res.status_code, 201, getattr(buy_res, 'data', buy_res))
        order_id = buy_res.data['id']
        token = buy_res.data.get('payment_confirm_token')

        confirm_req = self.factory.post(
            f'/api/users/orders/{order_id}/confirm-payment/',
            {'mock_payment_ack': True, 'payment_confirm_token': token},
            format='json',
        )
        force_authenticate(confirm_req, user=self.other_buyer)
        confirm_res = confirm_order_payment(confirm_req, order_id)
        self.assertIn(confirm_res.status_code, (200, 201), getattr(confirm_res, 'data', confirm_res))

        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.offer.refresh_from_db()
        self.assertEqual(Order.objects.get(pk=order_id).status, 'paid')
        self.assertEqual(self.t1.status, 'sold')
        self.assertEqual(self.t2.status, 'sold')
        self.assertIn(self.offer.status, ('rejected', 'expired'))
