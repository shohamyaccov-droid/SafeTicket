from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Coupon, CouponRedemption, Event, Order, Ticket


User = get_user_model()


class FixedAmountCouponTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='fixed_coupon_seller',
            email='fixed-coupon-seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='fixed_coupon_buyer',
            email='fixed-coupon-buyer@example.test',
            password='SafePass123!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Fixed Coupon Artist')
        event = Event.objects.create(
            artist=artist,
            name='Fixed Coupon Event',
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
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/fixed-coupon-test.pdf',
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

    def test_validate_returns_fixed_discount_and_discounted_total(self):
        response = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'safe20', 'base_amount': '100.00'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['valid'])
        self.assertEqual(response.data['discount_type'], 'fixed')
        self.assertEqual(Decimal(response.data['discount_amount']), Decimal('20.00'))
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('92.00'))

    def test_create_order_recalculates_fixed_discount_on_server(self):
        response = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'total_amount': '92.00',
                'quantity': 1,
                'event_name': self.ticket.event.name,
                'coupon_code': 'SAFE20',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data['id'])
        self.assertEqual(order.total_amount, Decimal('92.00'))
        self.assertEqual(order.buyer_fee_discount, Decimal('20.00'))
        self.assertEqual(order.coupon_code_snapshot, 'SAFE20')
        self.assertTrue(CouponRedemption.objects.filter(order=order).exists())

    def test_create_order_rejects_client_total_bypass(self):
        response = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'total_amount': '1.00',
                'quantity': 1,
                'event_name': self.ticket.event.name,
                'coupon_code': 'SAFE20',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.filter(user=self.buyer).exists())

    def test_inactive_coupon_is_rejected(self):
        self.coupon.is_active = False
        self.coupon.save(update_fields=['is_active'])

        response = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'SAFE20', 'base_amount': '100.00'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'inactive')

    def test_discount_is_clamped_at_zero(self):
        response = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'SAFE20', 'base_amount': '5.00'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data['total_amount']), Decimal('0.00'))
        self.assertEqual(Decimal(response.data['discount_amount']), Decimal('5.60'))
