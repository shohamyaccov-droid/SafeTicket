"""
Accepted-offer checkout must accept coupons (e.g. SAFE20) without cutting seller payout.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.coupons import checkout_amounts_for_coupon
from users.models import Artist, Coupon, CouponRedemption, Event, Offer, Order, Ticket
from users.pricing import compute_order_price_breakdown, expected_negotiated_total_from_offer_base


User = get_user_model()


class NegotiatedOfferCouponCheckoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='neg_coupon_seller',
            email='neg-coupon-seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='neg_coupon_buyer',
            email='neg-coupon-buyer@example.test',
            password='SafePass123!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Neg Coupon Artist')
        event = Event.objects.create(
            artist=artist,
            name='Neg Coupon Event',
            date=timezone.now() + timedelta(days=30),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('250.00'),
            asking_price=Decimal('250.00'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/neg-coupon-test.pdf',
        )
        now = timezone.now()
        self.offer = Offer.objects.create(
            buyer=self.buyer,
            ticket=self.ticket,
            amount=Decimal('200.00'),
            quantity=1,
            status='accepted',
            expires_at=now + timedelta(hours=48),
            accepted_at=now,
            checkout_expires_at=now + timedelta(hours=24),
        )
        self.coupon = Coupon.objects.create(
            code='SAFE20',
            coupon_type=Coupon.TYPE_PLATFORM,
            affiliate=None,
            discount_amount=Decimal('20.00'),
            buyer_discount_rate=Decimal('0.0000'),
            affiliate_commission_rate=Decimal('0.0000'),
            platform_net_rate=Decimal('0.0000'),
            is_active=True,
        )
        self.client.force_authenticate(user=self.buyer)

    def test_accepted_offer_without_coupon_still_matches_full_fee_total(self):
        expected = expected_negotiated_total_from_offer_base(self.offer.amount)
        response = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'quantity': 1,
                'offer_id': self.offer.id,
                'total_amount': str(expected),
                'accepted_terms': True,
                'event_name': self.ticket.event.name,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data['id'])
        self.assertEqual(order.total_amount, expected)
        self.assertEqual(order.pending_offer_id, self.offer.id)

    def test_accepted_offer_with_safe20_reduces_buyer_total_only(self):
        amounts = checkout_amounts_for_coupon(self.coupon, self.offer.amount)
        discounted_total = amounts['total']
        full_total = expected_negotiated_total_from_offer_base(self.offer.amount)
        self.assertLess(discounted_total, full_total)

        # Old bug: server expected full fee total and rejected the discounted amount.
        response = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'quantity': 1,
                'offer_id': self.offer.id,
                'total_amount': str(discounted_total),
                'accepted_terms': True,
                'event_name': self.ticket.event.name,
                'coupon_code': 'SAFE20',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data['id'])
        self.assertEqual(order.total_amount, discounted_total)
        self.assertEqual(order.total_paid_by_buyer, discounted_total)
        self.assertEqual(order.buyer_fee_discount, Decimal('20.00'))
        self.assertEqual(order.coupon_code_snapshot, 'SAFE20')
        self.assertTrue(CouponRedemption.objects.filter(order=order).exists())

        # Seller economics: negotiated base stays intact; discount is buyer/platform only.
        breakdown = compute_order_price_breakdown(
            discounted_total,
            self.offer,
            self.ticket,
            1,
        )
        self.assertEqual(breakdown['final_negotiated_price'], Decimal('200.00'))
        self.assertEqual(breakdown['net_seller_revenue'], Decimal('200.00'))
        self.assertEqual(
            breakdown['buyer_service_fee'],
            discounted_total - Decimal('200.00'),
        )

    def test_accepted_offer_rejects_undercut_even_with_coupon(self):
        response = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'quantity': 1,
                'offer_id': self.offer.id,
                'total_amount': '1.00',
                'accepted_terms': True,
                'event_name': self.ticket.event.name,
                'coupon_code': 'SAFE20',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.filter(user=self.buyer).exists())
