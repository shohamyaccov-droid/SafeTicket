"""
Affiliate coupon + dynamic GlobalFeeSettings (defaults: 12% base, 7/5/2 with coupon).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.coupons import (
    CouponError,
    claim_coupon_for_order,
    seed_demo_affiliate_coupon,
)
from users.fee_settings import clear_fee_settings_cache
from users.models import Artist, CouponRedemption, Event, GlobalFeeSettings, Order, Ticket
from users.pricing import affiliate_checkout_amounts, buyer_charge_from_base_amount, expected_buy_now_total

User = get_user_model()


def _reset_default_fees():
    clear_fee_settings_cache()
    settings = GlobalFeeSettings.load()
    settings.base_buyer_fee_percent = Decimal('12.00')
    settings.base_seller_fee_percent = Decimal('0.00')
    settings.buyer_coupon_discount_percent = Decimal('5.00')
    settings.affiliate_commission_percent = Decimal('5.00')
    settings.save()
    clear_fee_settings_cache()


class AffiliatePricingMathTests(TestCase):
    def setUp(self):
        _reset_default_fees()

    def test_base_fee_is_twelve_percent(self):
        base, fee, total = buyer_charge_from_base_amount(Decimal('100'))
        self.assertEqual(base, Decimal('100.00'))
        self.assertEqual(fee, Decimal('12.00'))
        self.assertEqual(total, Decimal('112.00'))
        self.assertEqual(expected_buy_now_total(Decimal('100'), 1), Decimal('112.00'))

    def test_affiliate_split_is_exactly_7_5_2(self):
        amounts = affiliate_checkout_amounts(Decimal('100'))
        self.assertEqual(amounts['buyer_fee'], Decimal('7.00'))
        self.assertEqual(amounts['buyer_discount'], Decimal('5.00'))
        self.assertEqual(amounts['affiliate_commission'], Decimal('5.00'))
        self.assertEqual(amounts['platform_net_fee'], Decimal('2.00'))
        self.assertEqual(amounts['total'], Decimal('107.00'))
        self.assertEqual(
            amounts['buyer_discount'] + amounts['affiliate_commission'] + amounts['platform_net_fee'],
            Decimal('12.00'),
        )


class CouponFlowApiTests(TestCase):
    def setUp(self):
        _reset_default_fees()
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='coupon_seller',
            email='coupon_seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='coupon_buyer',
            email='coupon_buyer@example.test',
            password='SafePass123!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Coupon Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Coupon Show',
            date=timezone.now() + timedelta(days=40),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/coupon-test.pdf',
        )
        self.coupon = seed_demo_affiliate_coupon(code='PARTNER15')

    def test_validate_invalid_code(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'NOPE', 'base_amount': '100'},
            format='json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data.get('code'), 'invalid_code')

    def test_validate_ok_then_already_used(self):
        self.client.force_authenticate(user=self.buyer)
        ok = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'PARTNER15', 'base_amount': '100'},
            format='json',
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(Decimal(ok.data['total_amount']), Decimal('107.00'))
        self.assertEqual(ok.data.get('affiliate_percent'), '5')
        self.assertEqual(ok.data.get('platform_percent'), '2')
        self.assertEqual(ok.data.get('fee_percent_charged'), '7')

        order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            total_amount=Decimal('107.00'),
            quantity=1,
            status='pending_payment',
            event_name=self.event.name,
        )
        claim_coupon_for_order(
            order=order,
            coupon_code='PARTNER15',
            user=self.buyer,
            base_amount=Decimal('100'),
        )
        again = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'PARTNER15', 'base_amount': '100'},
            format='json',
        )
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data.get('code'), 'already_used')

    def test_create_order_with_coupon_total(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'total_amount': '107.00',
                'accepted_terms': True,
                'quantity': 1,
                'event_name': self.event.name,
                'coupon_code': 'PARTNER15',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        order = Order.objects.get(pk=res.data['id'])
        self.assertEqual(order.total_amount, Decimal('107.00'))
        self.assertEqual(order.coupon_code_snapshot, 'PARTNER15')
        self.assertEqual(order.affiliate_commission, Decimal('5.00'))
        self.assertEqual(order.buyer_fee_discount, Decimal('5.00'))
        self.assertEqual(order.platform_net_fee, Decimal('2.00'))
        self.assertEqual(order.buyer_service_fee, Decimal('7.00'))
        self.assertTrue(
            CouponRedemption.objects.filter(
                order=order,
                buyer_key=f'user:{self.buyer.id}',
                status=CouponRedemption.STATUS_PENDING,
            ).exists()
        )

    def test_create_order_rejects_wrong_total_with_coupon(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'total_amount': '112.00',  # full fee — should fail when coupon present
                'accepted_terms': True,
                'quantity': 1,
                'event_name': self.event.name,
                'coupon_code': 'PARTNER15',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)


class CouponRaceConditionTests(TestCase):
    def setUp(self):
        _reset_default_fees()
        self.seller = User.objects.create_user(
            username='race_seller',
            email='race_seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='race_buyer',
            email='race_buyer@example.test',
            password='SafePass123!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Race Artist')
        event = Event.objects.create(
            artist=artist,
            name='Race Show',
            date=timezone.now() + timedelta(days=20),
            venue='V',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('200'),
            asking_price=Decimal('200'),
            available_quantity=2,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/race.pdf',
        )
        self.coupon = seed_demo_affiliate_coupon(code='RACETHIS')

    def test_second_claim_same_buyer_fails(self):
        order1 = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            total_amount=Decimal('214.00'),
            quantity=1,
            status='pending_payment',
            event_name='Race Show',
        )
        order2 = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            total_amount=Decimal('214.00'),
            quantity=1,
            status='pending_payment',
            event_name='Race Show',
        )
        claim_coupon_for_order(
            order=order1,
            coupon_code='RACETHIS',
            user=self.buyer,
            base_amount=Decimal('200'),
        )
        with self.assertRaises(CouponError) as ctx:
            claim_coupon_for_order(
                order=order2,
                coupon_code='RACETHIS',
                user=self.buyer,
                base_amount=Decimal('200'),
            )
        self.assertEqual(ctx.exception.code, 'already_used')
        self.assertEqual(
            CouponRedemption.objects.filter(
                coupon=self.coupon,
                buyer_key=f'user:{self.buyer.id}',
                status__in=[CouponRedemption.STATUS_PENDING, CouponRedemption.STATUS_REDEEMED],
            ).count(),
            1,
        )
