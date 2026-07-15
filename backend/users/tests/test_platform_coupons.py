"""
Platform-owned coupons (TRADETIX5) against GlobalFeeSettings defaults (12% → 7/0/7).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.coupons import (
    CouponError,
    claim_coupon_for_order,
    get_active_coupon,
    preview_coupon_for_base,
    seed_platform_coupon,
)
from users.fee_settings import checkout_split_rates_for_coupon, clear_fee_settings_cache
from users.models import Artist, Coupon, CouponRedemption, Event, GlobalFeeSettings, Order, Ticket
from users.pricing import affiliate_checkout_amounts

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


class PlatformPricingMathTests(TestCase):
    def setUp(self):
        _reset_default_fees()

    def test_platform_split_is_exactly_7_0_7(self):
        """Buyer fee 7%, affiliate 0%, platform net 7% of base."""
        coupon = seed_platform_coupon(code='TRADETIX5')
        disc, aff, plat = checkout_split_rates_for_coupon(coupon)
        amounts = affiliate_checkout_amounts(
            Decimal('100'),
            buyer_discount_rate=disc,
            affiliate_rate=aff,
            platform_rate=plat,
        )
        self.assertEqual(amounts['buyer_fee'], Decimal('7.00'))
        self.assertEqual(amounts['buyer_discount'], Decimal('5.00'))
        self.assertEqual(amounts['affiliate_commission'], Decimal('0.00'))
        self.assertEqual(amounts['platform_net_fee'], Decimal('7.00'))
        self.assertEqual(amounts['total'], Decimal('107.00'))
        self.assertEqual(
            amounts['buyer_discount']
            + amounts['affiliate_commission']
            + amounts['platform_net_fee'],
            Decimal('12.00'),
        )


class PlatformCouponModelTests(TestCase):
    def setUp(self):
        _reset_default_fees()

    def test_seed_tradetix5_has_no_affiliate(self):
        coupon = seed_platform_coupon(code='TRADETIX5')
        self.assertEqual(coupon.code, 'TRADETIX5')
        self.assertEqual(coupon.coupon_type, Coupon.TYPE_PLATFORM)
        self.assertIsNone(coupon.affiliate_id)
        self.assertEqual(coupon.affiliate_commission_rate, Decimal('0.0000'))
        self.assertEqual(coupon.platform_net_rate, Decimal('0.0700'))
        self.assertEqual(coupon.buyer_discount_rate, Decimal('0.0500'))

    def test_get_active_platform_coupon_without_affiliate(self):
        seed_platform_coupon(code='TRADETIX5')
        coupon = get_active_coupon('tradetix5')
        self.assertEqual(coupon.code, 'TRADETIX5')
        self.assertIsNone(coupon.affiliate_id)

    def test_db_rejects_platform_with_non_zero_affiliate_rate(self):
        coupon = Coupon(
            code='BADPLATFORM',
            coupon_type=Coupon.TYPE_PLATFORM,
            affiliate=None,
            buyer_discount_rate=Decimal('0.0500'),
            affiliate_commission_rate=Decimal('0.0500'),
            platform_net_rate=Decimal('0.0500'),
        )
        with self.assertRaises(ValidationError):
            coupon.save()

    def test_db_rejects_affiliate_type_without_partner(self):
        coupon = Coupon(
            code='MISSINGPARTNER',
            coupon_type=Coupon.TYPE_AFFILIATE,
            affiliate=None,
            buyer_discount_rate=Decimal('0.0500'),
            affiliate_commission_rate=Decimal('0.0500'),
            platform_net_rate=Decimal('0.0500'),
        )
        with self.assertRaises(Exception):
            coupon.save()


class PlatformCouponFlowApiTests(TestCase):
    def setUp(self):
        _reset_default_fees()
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='plat_seller',
            email='plat_seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='plat_buyer',
            email='plat_buyer@example.test',
            password='SafePass123!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Platform Coupon Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Platform Coupon Show',
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
            pdf_file='tickets/pdfs/platform-coupon-test.pdf',
        )
        self.coupon = seed_platform_coupon(code='TRADETIX5')

    def test_validate_preview_is_7_0_7(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'TRADETIX5', 'base_amount': '100'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data.get('coupon_type'), 'platform')
        self.assertEqual(Decimal(res.data['buyer_service_fee']), Decimal('7.00'))
        self.assertEqual(Decimal(res.data['buyer_fee_discount']), Decimal('5.00'))
        self.assertEqual(Decimal(res.data['affiliate_commission']), Decimal('0.00'))
        self.assertEqual(Decimal(res.data['platform_net_fee']), Decimal('7.00'))
        self.assertEqual(Decimal(res.data['total_amount']), Decimal('107.00'))
        self.assertEqual(res.data.get('affiliate_percent'), '0')
        self.assertEqual(res.data.get('platform_percent'), '7')
        self.assertEqual(res.data.get('discount_percent'), '5')
        self.assertEqual(res.data.get('fee_percent_charged'), '7')
        self.assertEqual(res.data.get('affiliate_name'), 'TradeTix')

    def test_validate_then_already_used(self):
        preview = preview_coupon_for_base('TRADETIX5', Decimal('100'), user=self.buyer)
        self.assertEqual(preview.affiliate_commission, Decimal('0.00'))
        self.assertEqual(preview.platform_net_fee, Decimal('7.00'))

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
            coupon_code='TRADETIX5',
            user=self.buyer,
            base_amount=Decimal('100'),
        )
        self.client.force_authenticate(user=self.buyer)
        again = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'TRADETIX5', 'base_amount': '100'},
            format='json',
        )
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data.get('code'), 'already_used')

    def test_create_order_with_platform_coupon_checkout(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'total_amount': '107.00',
                'quantity': 1,
                'event_name': self.event.name,
                'coupon_code': 'TRADETIX5',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        order = Order.objects.get(pk=res.data['id'])
        self.assertEqual(order.total_amount, Decimal('107.00'))
        self.assertEqual(order.coupon_code_snapshot, 'TRADETIX5')
        self.assertEqual(order.buyer_service_fee, Decimal('7.00'))
        self.assertEqual(order.buyer_fee_discount, Decimal('5.00'))
        self.assertEqual(order.affiliate_commission, Decimal('0.00'))
        self.assertEqual(order.platform_net_fee, Decimal('7.00'))
        self.assertEqual(order.coupon.coupon_type, Coupon.TYPE_PLATFORM)
        self.assertIsNone(order.coupon.affiliate_id)
        redemption = CouponRedemption.objects.get(order=order)
        self.assertEqual(redemption.status, CouponRedemption.STATUS_PENDING)
        self.assertEqual(redemption.affiliate_commission, Decimal('0.00'))
        self.assertEqual(redemption.platform_net_fee, Decimal('7.00'))
        self.assertEqual(redemption.buyer_key, f'user:{self.buyer.id}')

    def test_create_order_rejects_wrong_total_with_platform_coupon(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'total_amount': '112.00',
                'quantity': 1,
                'event_name': self.event.name,
                'coupon_code': 'TRADETIX5',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)


class PlatformCouponOneUseTests(TestCase):
    def setUp(self):
        _reset_default_fees()
        self.seller = User.objects.create_user(
            username='plat_race_seller',
            email='plat_race_seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='plat_race_buyer',
            email='plat_race_buyer@example.test',
            password='SafePass123!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Plat Race Artist')
        event = Event.objects.create(
            artist=artist,
            name='Plat Race Show',
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
            pdf_file='tickets/pdfs/plat-race.pdf',
        )
        self.coupon = seed_platform_coupon(code='TRADETIX5')

    def test_second_claim_same_buyer_fails(self):
        order1 = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            total_amount=Decimal('214.00'),
            quantity=1,
            status='pending_payment',
            event_name='Plat Race Show',
        )
        order2 = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            total_amount=Decimal('214.00'),
            quantity=1,
            status='pending_payment',
            event_name='Plat Race Show',
        )
        claim_coupon_for_order(
            order=order1,
            coupon_code='TRADETIX5',
            user=self.buyer,
            base_amount=Decimal('200'),
        )
        order1.refresh_from_db()
        self.assertEqual(order1.affiliate_commission, Decimal('0.00'))
        self.assertEqual(order1.platform_net_fee, Decimal('14.00'))
        self.assertEqual(order1.buyer_service_fee, Decimal('14.00'))

        with self.assertRaises(CouponError) as ctx:
            claim_coupon_for_order(
                order=order2,
                coupon_code='TRADETIX5',
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


class GlobalFeeSettingsAdminMathTests(TestCase):
    def setUp(self):
        _reset_default_fees()

    def test_admin_change_updates_checkout_math(self):
        from users.pricing import buyer_charge_from_base_amount

        settings = GlobalFeeSettings.load()
        settings.base_buyer_fee_percent = Decimal('15.00')
        settings.buyer_coupon_discount_percent = Decimal('5.00')
        settings.affiliate_commission_percent = Decimal('5.00')
        settings.save()
        clear_fee_settings_cache()

        _base, fee, total = buyer_charge_from_base_amount(Decimal('100'))
        self.assertEqual(fee, Decimal('15.00'))
        self.assertEqual(total, Decimal('115.00'))

        amounts = affiliate_checkout_amounts(Decimal('100'))
        self.assertEqual(amounts['buyer_fee'], Decimal('10.00'))
        self.assertEqual(amounts['affiliate_commission'], Decimal('5.00'))
        self.assertEqual(amounts['platform_net_fee'], Decimal('5.00'))
        self.assertEqual(amounts['total'], Decimal('110.00'))
