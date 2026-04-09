"""
Global API error surface: return JSON (+ traceback) instead of Django HTML for unhandled exceptions.

Useful when DEBUG is False or when crashes occur inside parser/storage before DRF formats a Response.
Revisit / tighten before production (traceback may leak internals).
"""
from __future__ import annotations

import logging
import traceback

from django.http import JsonResponse

logger = logging.getLogger(__name__)


class GlobalExceptionJSONMiddleware:
    """Catch unhandled exceptions and return JsonResponse(500) with error + traceback text."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        tb = traceback.format_exc()
        msg = str(exception) if exception else repr(exception)
        logger.exception('Unhandled exception (GlobalExceptionJSONMiddleware): %s', msg)
        payload = {
            'error': msg,
            'traceback': tb,
            'path': request.path,
        }
        return JsonResponse(payload, status=500)
