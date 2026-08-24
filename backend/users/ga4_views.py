"""Staff-only GA4 analytics (ADC)."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.ga4_service import (
    Ga4ApiError,
    Ga4AuthError,
    Ga4ConfigError,
    fetch_ga4_behavior_dashboard,
    fetch_ga4_last_7_days,
)
from users.offer_admin_views import _is_admin


def _staff_or_error(request):
    if not _is_admin(request.user):
        return Response(
            {'error': 'Permission denied. Admin access required.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _ga4_error_response(exc):
    if isinstance(exc, Ga4ConfigError):
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, Ga4AuthError):
        return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_ga4_overview(request):
    denied = _staff_or_error(request)
    if denied:
        return denied
    try:
        payload = fetch_ga4_last_7_days()
    except (Ga4ConfigError, Ga4AuthError, Ga4ApiError) as exc:
        return _ga4_error_response(exc)
    return Response(payload)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_ga4_behavior(request):
    denied = _staff_or_error(request)
    if denied:
        return denied
    try:
        payload = fetch_ga4_behavior_dashboard()
    except (Ga4ConfigError, Ga4AuthError, Ga4ApiError) as exc:
        return _ga4_error_response(exc)
    return Response(payload)
