"""Profile listing quantity for sold multi-seat orders (seller dashboard)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket

User = get_user_model()


class ProfileListingQuantityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='qty-seller',
            email='qty-seller@example.com',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='qty-buyer',
            email='qty-buyer@example.com',
            password='pass',
        )
        artist = Artist.objects.create(name='Qty Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Qty Show',
            date=timezone.now(),
            venue='Arena',
            city='TLV',
            country='IL',
        )
        self.t1 = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('299'),
            asking_price=Decimal('299'),
            pdf_file='tickets/pdfs/t1.pdf',
            status='sold',
            verification_status='מאומת',
            available_quantity=0,
            listing_group_id='qty-group-1',
        )
        self.t2 = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('299'),
            asking_price=Decimal('299'),
            pdf_file='tickets/pdfs/t2.pdf',
            status='sold',
            verification_status='מאומת',
            available_quantity=0,
            listing_group_id='qty-group-1',
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.t1,
            ticket_ids=[self.t1.id, self.t2.id],
            status='paid',
            total_amount=Decimal('688'),
            currency='ILS',
            quantity=2,
            final_negotiated_price=Decimal('598'),
            net_seller_revenue=Decimal('598'),
        )

    def test_sold_listings_report_order_quantity_not_available_quantity(self):
        self.client.force_authenticate(user=self.seller)
        res = self.client.get('/api/users/dashboard/')
        self.assertEqual(res.status_code, 200)
        sold = res.data.get('listings', {}).get('sold', [])
        self.assertEqual(len(sold), 2)
        for row in sold:
            self.assertEqual(row.get('available_quantity'), 0)
            self.assertEqual(row.get('quantity'), 2)
            self.assertEqual(row.get('order_id'), self.order.id)
            self.assertEqual(float(row.get('expected_payout')), 598.0)

        # Summary must not double-count the same order payout.
        payout = res.data['summary']['expected_payout_by_currency'].get('ILS')
        self.assertEqual(float(payout), 598.0)
