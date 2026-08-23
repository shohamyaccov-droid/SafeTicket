"""Staff-only probe for GA4 last-7-days totals (ADC)."""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.ga4_service import Ga4ApiError, Ga4AuthError, Ga4ConfigError, fetch_ga4_last_7_days
from users.offer_admin_views import _is_admin


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_ga4_overview(request):
    if not _is_admin(request.user):
        return Response(
            {'error': 'Permission denied. Admin access required.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        payload = fetch_ga4_last_7_days()
    except Ga4ConfigError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Ga4AuthError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Ga4ApiError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    return Response(payload)
