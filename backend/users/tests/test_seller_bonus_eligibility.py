"""
Tests for the seller bonus eligibility flag on Ticket and its effect on payout.

1. Ticket with eligible_for_bonus=True → 20 NIS bonus awarded via SellerPayout.
2. Ticket with eligible_for_bonus=False → no bonus even when campaign is active.
3. Campaign inactive → no bonus even for eligible ticket.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from users.models import Event, Order, SellerBonusCampaign, SellerPayout, Ticket
from users.payout_ledger import claim_launch_seller_bonus, ensure_seller_payout_for_order

User = get_user_model()


class SellerBonusEligibilityTest(TestCase):
    """Verify that the 20 NIS seller bonus only applies to eligible tickets."""

    def setUp(self):
        # Reset campaign to active with plenty of slots
        self.campaign = SellerBonusCampaign.load()
        self.campaign.is_active = True
        self.campaign.bonus_amount = Decimal('20.00')
        self.campaign.max_sales = 100
        self.campaign.claimed_sales_count = 0
        self.campaign.save()

        self.seller = User.objects.create_user(
            username='bonus_seller',
            email='bonus_seller@test.com',
            password='test-pass-123',
            role='seller',
            account_holder_name='Bonus Seller',
            bank_name='10',
            branch_number='100',
            account_number='111111',
        )
        self.buyer = User.objects.create_user(
            username='bonus_buyer',
            email='bonus_buyer@test.com',
            password='test-pass-123',
        )
        self.event = Event.objects.create(
            name='Bonus Test Event',
            date=timezone.now() + timedelta(days=30),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
        )

    def _create_ticket(self, eligible_for_bonus=False):
        return Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='sold',
            available_quantity=0,
            eligible_for_bonus=eligible_for_bonus,
        )

    def _paid_order(self, ticket):
        return Order.objects.create(
            user=self.buyer,
            ticket=ticket,
            status='paid',
            total_amount=Decimal('107.00'),
            total_paid_by_buyer=Decimal('107.00'),
            final_negotiated_price=Decimal('100.00'),
            buyer_service_fee=Decimal('7.00'),
            seller_service_fee=Decimal('0.00'),
            net_seller_revenue=Decimal('100.00'),
            quantity=1,
            event_name=self.event.name,
        )

    # ------------------------------------------------------------------ #
    # Test 1: eligible ticket → bonus awarded
    # ------------------------------------------------------------------ #
    def test_eligible_ticket_receives_bonus(self):
        ticket = self._create_ticket(eligible_for_bonus=True)
        order = self._paid_order(ticket)
        payout = ensure_seller_payout_for_order(order)

        self.assertIsNotNone(payout)
        self.assertEqual(payout.seller_bonus_amount, Decimal('20.00'))
        self.assertEqual(payout.total_seller_payout, Decimal('120.00'))

        # Campaign counter incremented
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.claimed_sales_count, 1)

    # ------------------------------------------------------------------ #
    # Test 2: ineligible ticket → no bonus
    # ------------------------------------------------------------------ #
    def test_ineligible_ticket_gets_no_bonus(self):
        ticket = self._create_ticket(eligible_for_bonus=False)
        order = self._paid_order(ticket)
        payout = ensure_seller_payout_for_order(order)

        self.assertIsNotNone(payout)
        self.assertEqual(payout.seller_bonus_amount, Decimal('0.00'))
        self.assertEqual(payout.net_payout, Decimal('100.00'))

        # Campaign counter NOT incremented
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.claimed_sales_count, 0)

    # ------------------------------------------------------------------ #
    # Test 3: campaign inactive → no bonus even if eligible
    # ------------------------------------------------------------------ #
    def test_inactive_campaign_no_bonus(self):
        self.campaign.is_active = False
        self.campaign.save(update_fields=['is_active'])

        ticket = self._create_ticket(eligible_for_bonus=True)
        order = self._paid_order(ticket)
        payout = ensure_seller_payout_for_order(order)

        self.assertIsNotNone(payout)
        self.assertEqual(payout.seller_bonus_amount, Decimal('0.00'))

    # ------------------------------------------------------------------ #
    # Test 4: campaign fully claimed → no bonus even if eligible
    # ------------------------------------------------------------------ #
    def test_exhausted_campaign_no_bonus(self):
        self.campaign.claimed_sales_count = self.campaign.max_sales
        self.campaign.save(update_fields=['claimed_sales_count'])

        ticket = self._create_ticket(eligible_for_bonus=True)
        order = self._paid_order(ticket)
        payout = ensure_seller_payout_for_order(order)

        self.assertIsNotNone(payout)
        self.assertEqual(payout.seller_bonus_amount, Decimal('0.00'))

    # ------------------------------------------------------------------ #
    # Test 5: bonus amount is exactly 20 NIS (campaign default)
    # ------------------------------------------------------------------ #
    def test_bonus_amount_is_exactly_20_nis(self):
        ticket = self._create_ticket(eligible_for_bonus=True)
        order = self._paid_order(ticket)
        payout = ensure_seller_payout_for_order(order)

        self.assertEqual(payout.seller_bonus_amount, Decimal('20.00'))

    # ------------------------------------------------------------------ #
    # Test 6: claim_launch_seller_bonus is idempotent
    # ------------------------------------------------------------------ #
    def test_bonus_claim_idempotent(self):
        ticket = self._create_ticket(eligible_for_bonus=True)
        order = self._paid_order(ticket)
        payout = ensure_seller_payout_for_order(order)

        # Try to claim again
        second = claim_launch_seller_bonus(payout)
        self.assertFalse(second)  # Already claimed, must return False

        payout.refresh_from_db()
        self.assertEqual(payout.seller_bonus_amount, Decimal('20.00'))

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.claimed_sales_count, 1)
