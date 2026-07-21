from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.coupons import checkout_amounts_for_coupon
from users.models import Coupon, Event, Order, SellerBonusCampaign, SellerPayout, Ticket
from users.pricing import buyer_charge_from_base_amount
from wallets.models import UserWallet, WalletTransaction


User = get_user_model()


class LaunchLossLeaderPromoTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='promo-seller',
            email='promo-seller@example.com',
            password='test-pass-123',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='promo-buyer',
            email='promo-buyer@example.com',
            password='test-pass-123',
        )
        self.event = Event.objects.create(
            name='Promo Event',
            date=timezone.now() + timedelta(days=30),
            venue='Promo Venue',
            city='Tel Aviv',
            country='IL',
        )
        campaign = SellerBonusCampaign.load()
        campaign.is_active = True
        campaign.bonus_amount = Decimal('20.00')
        campaign.max_sales = 1
        campaign.claimed_sales_count = 0
        campaign.save()

    def _paid_order(self, suffix):
        ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='sold',
            available_quantity=0,
            ticket_type=f'promo-{suffix}',
        )
        return Order.objects.create(
            user=self.buyer,
            ticket=ticket,
            status='paid',
            total_amount=Decimal('112.00'),
            total_paid_by_buyer=Decimal('112.00'),
            final_negotiated_price=Decimal('100.00'),
            buyer_service_fee=Decimal('12.00'),
            seller_service_fee=Decimal('0.00'),
            net_seller_revenue=Decimal('100.00'),
            quantity=1,
            event_name=self.event.name,
        )

    def test_only_first_eligible_sale_receives_platform_bonus(self):
        first = self._paid_order('first')
        second = self._paid_order('second')

        first_payout = SellerPayout.objects.get(order=first)
        second_payout = SellerPayout.objects.get(order=second)
        self.assertEqual(first_payout.net_payout, Decimal('100.00'))
        self.assertEqual(first_payout.seller_bonus_amount, Decimal('20.00'))
        self.assertEqual(first_payout.total_seller_payout, Decimal('120.00'))
        self.assertEqual(second_payout.seller_bonus_amount, Decimal('0.00'))

        campaign = SellerBonusCampaign.load()
        self.assertEqual(campaign.claimed_sales_count, 1)
        self.assertEqual(campaign.remaining_sales, 0)

        wallet = UserWallet.objects.get(user=self.seller)
        self.assertEqual(wallet.locked_balance, Decimal('220.00'))
        first_credit = WalletTransaction.objects.get(seller_payout=first_payout)
        self.assertEqual(first_credit.amount, Decimal('120.00'))

    def test_launch_status_endpoint_hides_exhausted_bonus(self):
        response = self.client.get('/api/users/promotions/launch/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['seller_bonus']['is_active'])
        self.assertEqual(response.data['seller_bonus']['remaining_sales'], 1)

        self._paid_order('exhaust')
        response = self.client.get('/api/users/promotions/launch/')
        self.assertFalse(response.data['seller_bonus']['is_active'])
        self.assertEqual(response.data['seller_bonus']['remaining_sales'], 0)

    def test_tix15_is_reusable_fixed_platform_coupon(self):
        coupon = Coupon.objects.get(code='TIX15')
        self.assertTrue(coupon.is_active)
        self.assertEqual(coupon.coupon_type, Coupon.TYPE_PLATFORM)
        self.assertEqual(coupon.discount_amount, Decimal('15.00'))
        self.assertIsNone(coupon.max_redemptions_total)

        amounts = checkout_amounts_for_coupon(coupon, Decimal('100.00'))
        _base, _fee, standard_total = buyer_charge_from_base_amount(Decimal('100.00'))
        self.assertEqual(
            amounts['total'],
            (standard_total - Decimal('15.00')).quantize(Decimal('0.01')),
        )
        self.assertEqual(amounts['buyer_discount'], Decimal('15.00'))
        self.assertEqual(amounts['base'], Decimal('100.00'))

        response = self.client.post(
            '/api/users/coupons/validate/',
            {'code': 'TIX15', 'base_amount': '100.00'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['discount_amount'], '15.00')
        self.assertEqual(response.data['discount_type'], 'fixed')
