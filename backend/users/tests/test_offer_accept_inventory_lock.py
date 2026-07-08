from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from users.models import Artist, Event, Offer, Ticket
from users.pricing import expected_buy_now_total
from users.views import OfferViewSet, create_order

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

    def test_accept_offer_reserves_inventory_blocks_competing_buy_now(self):
        accept_view = OfferViewSet.as_view({'post': 'accept'})
        req = self.factory.post(f'/offers/{self.offer.id}/accept/', {})
        force_authenticate(req, user=self.seller)

        res = accept_view(req, pk=self.offer.id)
        self.assertEqual(res.status_code, 200, res.data)

        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(self.t1.status, 'reserved')
        self.assertEqual(self.t2.status, 'reserved')
        self.assertEqual(self.t1.reserved_by_id, self.offer_buyer.id)
        self.assertEqual(self.t2.reserved_by_id, self.offer_buyer.id)

        buy_payload = {
            # create_order requires `ticket`; when listing_group_id is provided it ignores ticket's
            # active status and purchases from the group.
            'ticket': self.t1.id,
            'listing_group_id': self.listing_group_id,
            'quantity': 2,
            'total_amount': str(expected_buy_now_total(self.t1.asking_price, 2)),
        }
        buy_req = self.factory.post('/api/users/orders/', buy_payload, format='json')
        force_authenticate(buy_req, user=self.other_buyer)

        buy_res = create_order(buy_req)
        self.assertEqual(buy_res.status_code, 400, getattr(buy_res, 'data', buy_res))
        self.assertIn(
            'Not enough tickets available',
            str(getattr(buy_res, 'data', buy_res)),
        )

