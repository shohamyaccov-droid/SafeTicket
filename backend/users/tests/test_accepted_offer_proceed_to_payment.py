"""Accepted-offer Proceed-to-Payment must lock active inventory for 10 minutes."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Offer, Ticket
from users.pricing import expected_negotiated_total_from_offer_base

User = get_user_model()


class AcceptedOfferProceedToPaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='offer_pay_seller',
            email='offer-pay-seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='offer_pay_buyer',
            email='offer-pay-buyer@example.test',
            password='SafePass123!',
            role='buyer',
            phone_number='0501234567',
            first_name='Buyer',
            last_name='Test',
        )
        artist = Artist.objects.create(name='Offer Pay Artist')
        event = Event.objects.create(
            artist=artist,
            name='Offer Pay Event',
            date=timezone.now() + timedelta(days=30),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.group_id = 'offer-pay-group-1'
        self.t1 = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('200.00'),
            asking_price=Decimal('200.00'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/offer-pay-1.pdf',
            listing_group_id=self.group_id,
        )
        self.t2 = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('200.00'),
            asking_price=Decimal('200.00'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/offer-pay-2.pdf',
            listing_group_id=self.group_id,
        )
        now = timezone.now()
        self.offer = Offer.objects.create(
            buyer=self.buyer,
            ticket=self.t1,
            amount=Decimal('360.00'),
            quantity=2,
            status='accepted',
            expires_at=now + timedelta(hours=48),
            accepted_at=now,
            checkout_expires_at=now + timedelta(hours=24),
        )
        self.client.force_authenticate(user=self.buyer)

    def test_accept_leaves_tickets_active(self):
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(self.t1.status, 'active')
        self.assertEqual(self.t2.status, 'active')

    def test_reserve_with_offer_id_locks_group_quantity(self):
        res = self.client.post(
            f'/api/users/tickets/{self.t1.id}/reserve/',
            {'offer_id': self.offer.id},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data.get('quantity'), 2)
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(self.t1.status, 'reserved')
        self.assertEqual(self.t2.status, 'reserved')
        self.assertEqual(self.t1.reserved_by_id, self.buyer.id)
        self.assertEqual(self.t2.reserved_by_id, self.buyer.id)

    def test_create_order_without_listing_group_id_uses_offer_group(self):
        """Dashboard stub often omits listing_group_id — server must resolve from offer."""
        expected = expected_negotiated_total_from_offer_base(self.offer.amount)
        # Client may even send wrong quantity; server uses offer.quantity.
        res = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.t1.id,
                'quantity': 1,
                'offer_id': self.offer.id,
                'total_amount': str(expected),
                'accepted_terms': True,
                'event_name': self.t1.event.name,
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.assertEqual(self.t1.status, 'reserved')
        self.assertEqual(self.t2.status, 'reserved')
        from users.models import Order

        order = Order.objects.get(pk=res.data['id'])
        self.assertEqual(order.quantity, 2)
        self.assertEqual(sorted(order.ticket_ids), sorted([self.t1.id, self.t2.id]))
        self.assertEqual(order.pending_offer_id, self.offer.id)
        self.assertEqual(order.total_amount, expected)
