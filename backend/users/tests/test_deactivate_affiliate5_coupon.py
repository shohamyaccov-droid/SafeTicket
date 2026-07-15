"""Tests for AFFILIATE5 deactivation management command."""
from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from users.coupons import seed_demo_affiliate_coupon
from users.fee_settings import clear_fee_settings_cache
from users.models import Coupon, GlobalFeeSettings


class DeactivateAffiliate5CouponTests(TestCase):
    def setUp(self):
        clear_fee_settings_cache()
        GlobalFeeSettings.load()
        self.coupon = seed_demo_affiliate_coupon(code='AFFILIATE5')
        self.assertTrue(self.coupon.is_active)

    def test_deactivate_sets_inactive(self):
        call_command('deactivate_affiliate5_coupon')
        coupon = Coupon.objects.get(code='AFFILIATE5')
        self.assertFalse(coupon.is_active)

    def test_idempotent_when_missing(self):
        Coupon.objects.filter(code='AFFILIATE5').delete()
        call_command('deactivate_affiliate5_coupon')  # should not raise

    def test_delete_flag(self):
        call_command('deactivate_affiliate5_coupon', delete=True)
        self.assertFalse(Coupon.objects.filter(code__iexact='AFFILIATE5').exists())
