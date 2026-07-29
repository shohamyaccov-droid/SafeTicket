"""HTTP endpoints for coupon preview / validation and public pricing settings."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from users.coupons import CouponError, preview_coupon_for_base
from users.fee_settings import get_fee_rates
from users.models import AnnouncementBanner, Coupon, SellerBonusCampaign
from users.serializers import AnnouncementBannerSerializer


def _csrf_passthrough(view):
    """Match users.views.csrf_required: JWT SPA; CSRF not applied as session form POST."""
    view.csrf_exempt = True
    return view


class CouponValidateThrottle(UserRateThrottle):
    rate = '30/min'


class CouponValidateAnonThrottle(AnonRateThrottle):
    rate = '20/min'


@_csrf_passthrough
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([CouponValidateThrottle, CouponValidateAnonThrottle])
def validate_coupon(request):
    """
    Preview a coupon against a checkout base subtotal.

    Does NOT redeem — redemption is atomic at order create.
    Identity (user / guest_email) is optional so guests can preview before entering email.
    Body: { "code": "SAFE20", "base_amount": "100.00", "guest_email": "..."? }
    """
    code = request.data.get('code') or request.data.get('coupon_code') or ''
    raw_base = request.data.get('base_amount', request.data.get('base'))
    try:
        base = Decimal(str(raw_base))
    except (InvalidOperation, TypeError, ValueError):
        return Response(
            {'error': 'סכום בסיס לא תקין.', 'code': 'invalid_base'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = request.user if getattr(request.user, 'is_authenticated', False) else None
    guest_email = (request.data.get('guest_email') or '').strip() if not user else ''

    try:
        preview = preview_coupon_for_base(code, base, user=user, guest_email=guest_email)
    except CouponError as exc:
        return Response({'error': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'valid': True, **preview.as_dict()}, status=status.HTTP_200_OK)


@_csrf_passthrough
@api_view(['GET'])
@permission_classes([AllowAny])
def pricing_settings_view(request):
    """
    Public platform fee settings for SPA checkout display.

    Source of truth: GlobalFeeSettings singleton (Django Admin).
    """
    rates = get_fee_rates()

    def rate_to_percent(rate: Decimal) -> str:
        return str((Decimal(str(rate)) * Decimal('100')).quantize(Decimal('0.01')))

    buyer_pct = rate_to_percent(rates.base_buyer_fee_rate)
    discount_pct = rate_to_percent(rates.buyer_coupon_discount_rate)
    affiliate_pct = rate_to_percent(rates.affiliate_commission_rate)
    platform_aff_pct = rate_to_percent(rates.affiliate_platform_net_rate)
    with_coupon_pct = rate_to_percent(
        max(rates.base_buyer_fee_rate - rates.buyer_coupon_discount_rate, Decimal('0'))
    )
    return Response(
        {
            'service_fee_percentage': buyer_pct,
            'base_buyer_fee_percent': buyer_pct,
            'base_seller_fee_percent': rate_to_percent(rates.base_seller_fee_rate),
            'buyer_coupon_discount_percent': discount_pct,
            'affiliate_commission_percent': affiliate_pct,
            'affiliate_platform_net_percent': platform_aff_pct,
            'buyer_fee_percent_with_coupon': with_coupon_pct,
        },
        status=status.HTTP_200_OK,
    )


@_csrf_passthrough
@api_view(['GET'])
@permission_classes([AllowAny])
def launch_promotion_status_view(request):
    """Public, cache-friendly launch-promo status for marketing banners."""
    campaign = SellerBonusCampaign.load()
    coupon = Coupon.objects.filter(code__iexact='TIX15', is_active=True).first()
    banner_text = (campaign.banner_text or '').strip() or '🎁 20 ₪ בונוס למוכרים!'
    banner_coupon = (campaign.banner_coupon_code or '').strip().upper()
    return Response(
        {
            'seller_bonus': {
                'is_active': bool(campaign.is_active and campaign.remaining_sales > 0),
                'show_banner': bool(campaign.is_active and campaign.show_on_site),
                'banner_text': banner_text,
                'banner_coupon_code': banner_coupon,
                'bonus_amount': str(campaign.bonus_amount),
                'max_sales': campaign.max_sales,
                'claimed_sales': campaign.claimed_sales_count,
                'remaining_sales': campaign.remaining_sales,
            },
            'buyer_coupon': {
                'is_active': bool(coupon),
                'code': coupon.code.upper() if coupon else 'TIX15',
                'discount_amount': str(coupon.discount_amount) if coupon else '15.00',
            },
        },
        status=status.HTTP_200_OK,
    )


@_csrf_passthrough
@api_view(['GET'])
@permission_classes([AllowAny])
def announcement_banner_view(request):
    """Public singleton announcement banner config for the site header."""
    banner = AnnouncementBanner.load()
    payload = AnnouncementBannerSerializer(
        {
            'banner_text': (banner.banner_text or '').strip(),
            'is_active': bool(banner.is_active and (banner.banner_text or '').strip()),
        }
    ).data
    return Response(payload, status=status.HTTP_200_OK)
