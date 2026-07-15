"""
Affiliate coupon apply/redeem service.

Industry pattern:
- Coupon holds campaign rates / windows
- CouponRedemption is the ledger with UNIQUE(coupon, buyer_key) WHERE status IN (pending, redeemed)
- Claim uses transaction.atomic + IntegrityError catch (DB is the referee under race)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from users.models import AffiliatePartner, Coupon, CouponRedemption, Order, User
from users.pricing import (
    affiliate_checkout_amounts,
    buyer_charge_from_base_amount,
    decimal_money,
)


class CouponError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def normalize_coupon_code(raw: Any) -> str:
    return ''.join(str(raw or '').strip().upper().split())


def buyer_key_for(*, user: Optional[User] = None, guest_email: str = '') -> str:
    if user is not None and getattr(user, 'pk', None):
        return f'user:{int(user.pk)}'
    email = (guest_email or '').strip().lower()
    if not email:
        raise CouponError('identity_required', 'נדרשת הזדהות (משתמש מחובר או אימייל אורח) לשימוש בקופון.')
    return f'guest:{email}'


def get_active_coupon(code: str) -> Coupon:
    normalized = normalize_coupon_code(code)
    if not normalized:
        raise CouponError('invalid_code', 'קוד קופון לא תקין.')
    coupon = (
        Coupon.objects.select_related('affiliate')
        .filter(code__iexact=normalized)
        .first()
    )
    if coupon is None:
        raise CouponError('invalid_code', 'קוד קופון לא נמצא.')
    if not coupon.is_active or not coupon.affiliate.is_active:
        raise CouponError('inactive', 'קוד הקופון אינו פעיל.')
    now = timezone.now()
    if coupon.starts_at and now < coupon.starts_at:
        raise CouponError('not_started', 'קוד הקופון עדיין לא בתוקף.')
    if coupon.ends_at and now > coupon.ends_at:
        raise CouponError('expired', 'קוד הקופון פג תוקף.')
    if coupon.max_redemptions_total is not None and coupon.redemption_count >= coupon.max_redemptions_total:
        raise CouponError('exhausted', 'הגיעו למכסת השימוש של קוד זה.')
    return coupon


def has_active_redemption(coupon: Coupon, buyer_key: str) -> bool:
    return CouponRedemption.objects.filter(
        coupon=coupon,
        buyer_key=buyer_key,
        status__in=[CouponRedemption.STATUS_PENDING, CouponRedemption.STATUS_REDEEMED],
    ).exists()


@dataclass(frozen=True)
class CouponPreview:
    code: str
    base: Decimal
    buyer_fee: Decimal
    buyer_discount: Decimal
    affiliate_commission: Decimal
    platform_net_fee: Decimal
    total: Decimal
    affiliate_name: str

    def as_dict(self) -> dict:
        return {
            'code': self.code,
            'base_amount': str(self.base),
            'buyer_service_fee': str(self.buyer_fee),
            'buyer_fee_discount': str(self.buyer_discount),
            'affiliate_commission': str(self.affiliate_commission),
            'platform_net_fee': str(self.platform_net_fee),
            'total_amount': str(self.total),
            'affiliate_name': self.affiliate_name,
            'fee_percent_charged': '10',
            'discount_percent': '5',
            'affiliate_percent': '5',
            'platform_percent': '5',
        }


def preview_coupon_for_base(
    code: str,
    base: Any,
    *,
    user: Optional[User] = None,
    guest_email: str = '',
) -> CouponPreview:
    coupon = get_active_coupon(code)
    key = buyer_key_for(user=user, guest_email=guest_email)
    if has_active_redemption(coupon, key):
        raise CouponError('already_used', 'כבר השתמשת בקוד קופון זה. ניתן להשתמש בכל קוד פעם אחת בלבד.')
    b = decimal_money(base)
    if b <= 0:
        raise CouponError('invalid_base', 'סכום בסיס לא תקין לקופון.')
    amounts = affiliate_checkout_amounts(
        b,
        buyer_discount_rate=coupon.buyer_discount_rate,
        affiliate_rate=coupon.affiliate_commission_rate,
        platform_rate=coupon.platform_net_rate,
    )
    return CouponPreview(
        code=coupon.code.upper(),
        base=amounts['base'],
        buyer_fee=amounts['buyer_fee'],
        buyer_discount=amounts['buyer_discount'],
        affiliate_commission=amounts['affiliate_commission'],
        platform_net_fee=amounts['platform_net_fee'],
        total=amounts['total'],
        affiliate_name=coupon.affiliate.name,
    )


def expected_total_with_optional_coupon(
    unit_asking: Any,
    quantity: int,
    coupon_code: str | None,
) -> Decimal:
    """Server authority for order total (list price)."""
    q = max(1, int(quantity or 1))
    unit = decimal_money(unit_asking)
    base = (unit * Decimal(q)).quantize(QUANT)
    if not coupon_code:
        _, _, total = buyer_charge_from_base_amount(base)
        return total
    coupon = get_active_coupon(coupon_code)
    amounts = affiliate_checkout_amounts(
        base,
        buyer_discount_rate=coupon.buyer_discount_rate,
        affiliate_rate=coupon.affiliate_commission_rate,
        platform_rate=coupon.platform_net_rate,
    )
    return amounts['total']


@transaction.atomic
def claim_coupon_for_order(
    *,
    order: Order,
    coupon_code: str,
    user: Optional[User] = None,
    guest_email: str = '',
    base_amount: Any,
) -> CouponRedemption:
    """
    Atomically claim a one-time coupon for this buyer on this order.
    Relies on UniqueConstraint + IntegrityError under concurrent tabs.
    """
    coupon = get_active_coupon(coupon_code)
    # Serialize global count updates
    coupon = Coupon.objects.select_for_update().get(pk=coupon.pk)
    key = buyer_key_for(user=user, guest_email=guest_email)
    if has_active_redemption(coupon, key):
        raise CouponError('already_used', 'כבר השתמשת בקוד קופון זה. ניתן להשתמש בכל קוד פעם אחת בלבד.')
    if coupon.max_redemptions_total is not None and coupon.redemption_count >= coupon.max_redemptions_total:
        raise CouponError('exhausted', 'הגיעו למכסת השימוש של קוד זה.')

    amounts = affiliate_checkout_amounts(
        base_amount,
        buyer_discount_rate=coupon.buyer_discount_rate,
        affiliate_rate=coupon.affiliate_commission_rate,
        platform_rate=coupon.platform_net_rate,
    )
    try:
        redemption = CouponRedemption.objects.create(
            coupon=coupon,
            user=user if user and getattr(user, 'is_authenticated', False) else None,
            guest_email=(guest_email or '').strip().lower(),
            buyer_key=key,
            order=order,
            status=CouponRedemption.STATUS_PENDING,
            discount_amount=amounts['buyer_discount'],
            affiliate_commission=amounts['affiliate_commission'],
            platform_net_fee=amounts['platform_net_fee'],
            buyer_fee_paid=amounts['buyer_fee'],
        )
    except IntegrityError as exc:
        raise CouponError(
            'already_used',
            'כבר השתמשת בקוד קופון זה. ניתן להשתמש בכל קוד פעם אחת בלבד.',
        ) from exc

    Coupon.objects.filter(pk=coupon.pk).update(redemption_count=F('redemption_count') + 1)
    order.coupon = coupon
    order.coupon_code_snapshot = coupon.code.upper()
    order.buyer_fee_discount = amounts['buyer_discount']
    order.affiliate_commission = amounts['affiliate_commission']
    order.platform_net_fee = amounts['platform_net_fee']
    order.buyer_service_fee = amounts['buyer_fee']
    order.total_amount = amounts['total']
    order.total_paid_by_buyer = amounts['total']
    order.save(
        update_fields=[
            'coupon',
            'coupon_code_snapshot',
            'buyer_fee_discount',
            'affiliate_commission',
            'platform_net_fee',
            'buyer_service_fee',
            'total_amount',
            'total_paid_by_buyer',
            'updated_at',
        ]
    )
    return redemption


@transaction.atomic
def finalize_coupon_redemption(order: Order) -> None:
    redemption = (
        CouponRedemption.objects.select_for_update()
        .filter(order=order, status=CouponRedemption.STATUS_PENDING)
        .first()
    )
    if not redemption:
        return
    redemption.status = CouponRedemption.STATUS_REDEEMED
    redemption.redeemed_at = timezone.now()
    redemption.save(update_fields=['status', 'redeemed_at', 'updated_at'])


@transaction.atomic
def release_coupon_redemption(order: Order) -> None:
    """Free the one-use slot if checkout is cancelled / expired."""
    redemption = (
        CouponRedemption.objects.select_for_update()
        .filter(order=order, status=CouponRedemption.STATUS_PENDING)
        .first()
    )
    if not redemption:
        return
    coupon_id = redemption.coupon_id
    redemption.status = CouponRedemption.STATUS_RELEASED
    redemption.released_at = timezone.now()
    redemption.save(update_fields=['status', 'released_at', 'updated_at'])
    Coupon.objects.filter(pk=coupon_id, redemption_count__gt=0).update(
        redemption_count=F('redemption_count') - 1
    )
    if order.coupon_id:
        order.coupon = None
        order.coupon_code_snapshot = ''
        order.save(update_fields=['coupon', 'coupon_code_snapshot', 'updated_at'])


def seed_demo_affiliate_coupon(
    *,
    code: str = 'AFFILIATE5',
    partner_name: str = 'TradeTix Demo Affiliate',
) -> Coupon:
    partner, _ = AffiliatePartner.objects.get_or_create(
        name=partner_name,
        defaults={'email': 'affiliate@tradetix.local', 'is_active': True},
    )
    coupon, _ = Coupon.objects.update_or_create(
        code=normalize_coupon_code(code),
        defaults={
            'affiliate': partner,
            'is_active': True,
            'buyer_discount_rate': Decimal('0.0500'),
            'affiliate_commission_rate': Decimal('0.0500'),
            'platform_net_rate': Decimal('0.0500'),
        },
    )
    return coupon
