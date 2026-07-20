"""
DRF exception handler — keep API responses client-safe when DEBUG=False.

Unhandled / unexpected errors are logged in full for operators; clients only
receive generic messages. Validation and auth APIExceptions still pass through
with their intended status codes and user-facing details.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

# Substrings that commonly indicate leaked internals in error payloads.
_LEAK_MARKERS = (
    'traceback',
    'stack trace',
    'file "',
    "file '",
    'django.',
    'psycopg',
    'sqlite3.',
    'operationalerror',
    'integrityerror',
    'programmingerror',
    'doesnotexist',
    'line ',
    '  File ',
    'SITE_PACKAGES',
    'site-packages',
)


def _looks_like_leak(value: Any) -> bool:
    text = str(value or '')
    if len(text) > 800:
        return True
    lower = text.lower()
    return any(marker.lower() in lower or marker in text for marker in _LEAK_MARKERS)


def sanitize_error_payload(data: Any) -> Any:
    """
    Recursively strip leaky keys/values from a DRF error body when DEBUG=False.
    Leaves normal validation dicts/lists alone unless they look technical.
    """
    if settings.DEBUG:
        return data

    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for key, value in data.items():
            key_l = str(key).lower()
            if key_l in ('traceback', 'exception', 'exc_info', 'stack', 'sql', 'query'):
                continue
            if key_l in ('payme_response', 'payme_raw', 'raw', 'upstream'):
                continue
            sanitized = sanitize_error_payload(value)
            if sanitized is None and value is not None:
                continue
            out[key] = sanitized
        return out

    if isinstance(data, list):
        return [sanitize_error_payload(item) for item in data]

    if isinstance(data, str) and _looks_like_leak(data):
        return 'Something went wrong. Please try again later.'

    return data


def custom_exception_handler(exc, context):
    """
    Wrap DRF's default handler:
    - Log every exception with full context for admins.
    - When DEBUG=False, scrub leaky fields from the response body.
    - If DRF returns None (unhandled non-APIException), emit a safe 500 JSON.
    """
    response = drf_exception_handler(exc, context)

    view = context.get('view')
    request = context.get('request')
    path = getattr(request, 'path', None) if request is not None else None
    view_name = view.__class__.__name__ if view is not None else None

    if response is None:
        logger.exception(
            'Unhandled API exception view=%s path=%s: %s',
            view_name,
            path,
            exc,
        )
        if settings.DEBUG:
            return Response(
                {
                    'error': str(exc),
                    'detail': str(exc),
                    'path': path,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                'error': 'Internal server error',
                'detail': 'Something went wrong. Please try again later.',
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Expected APIExceptions still get logged at warning for ops visibility on 5xx.
    if response.status_code >= 500:
        logger.exception(
            'API 5xx view=%s path=%s status=%s: %s',
            view_name,
            path,
            response.status_code,
            exc,
        )
    elif response.status_code >= 400:
        logger.warning(
            'API client error view=%s path=%s status=%s: %s',
            view_name,
            path,
            response.status_code,
            exc,
        )

    if not settings.DEBUG and isinstance(response.data, (dict, list)):
        response.data = sanitize_error_payload(response.data)

    return response
