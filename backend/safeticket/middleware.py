"""
Global API error surface: return JSON instead of Django HTML for unhandled exceptions.

When DEBUG=False, never expose exception messages or tracebacks to clients.
"""
from __future__ import annotations

import logging
import traceback

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class GlobalExceptionJSONMiddleware:
    """Catch unhandled exceptions and return a safe JsonResponse(500)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        tb = traceback.format_exc()
        msg = str(exception) if exception else repr(exception)
        logger.exception('Unhandled exception (GlobalExceptionJSONMiddleware): %s', msg)
        if settings.DEBUG:
            payload = {
                'error': msg,
                'traceback': tb,
                'path': request.path,
            }
        else:
            payload = {
                'error': 'Internal server error',
                'detail': 'אירעה שגיאה בשרת. אנא נסו שוב מאוחר יותר.',
            }
        return JsonResponse(payload, status=500)
