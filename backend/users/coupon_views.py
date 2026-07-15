"""HTTP endpoints for affiliate coupon preview / validation."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from users.coupons import CouponError, preview_coupon_for_base


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
    Preview an affiliate coupon against a checkout base subtotal.
    Does NOT redeem — redemption is atomic at order create.
    Body: { "code": "AFFILIATE5", "base_amount": "100.00", "guest_email": "..."? }
    """
    code = request.data.get('code') or request.data.get('coupon_code') or ''
    raw_base = request.data.get('base_amount', request.data.get('base'))
    try:
        base = Decimal(str(raw_base))
    except (InvalidOperation, TypeError, ValueError):
        return Response({'error': 'סכום בסיס לא תקין.', 'code': 'invalid_base'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user if request.user.is_authenticated else None
    guest_email = ''
    if not user:
        guest_email = (request.data.get('guest_email') or '').strip()
        if not guest_email:
            return Response(
                {
                    'error': 'לאורחים נדרש אימייל כדי לאמת קופון (שימוש חד-פעמי לכל קונה).',
                    'code': 'identity_required',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        preview = preview_coupon_for_base(code, base, user=user, guest_email=guest_email)
    except CouponError as exc:
        return Response({'error': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'valid': True, **preview.as_dict()}, status=status.HTTP_200_OK)
