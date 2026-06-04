"""
Grow payment gateway webhooks.
POST /api/payments/webhook/ — configure this URL in the Grow dashboard.
"""
from __future__ import annotations

import logging

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def grow_payment_webhook(request):
    """Accept Grow PSP status callbacks; log payload for integration discovery."""
    logger.info('grow_payment_webhook payload: %s', request.data)
    return Response({'status': 'received'})
