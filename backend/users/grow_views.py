"""
Grow payment gateway webhooks.
POST /api/payments/webhook/ — configure this URL in the Grow dashboard.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# Skip DRF JSONParser so malformed JSON is handled in-view (never 500).
_GROW_WEBHOOK_PARSERS = (FormParser, MultiPartParser)
_LOG_PAYLOAD_MAX_LEN = 4096


def _payload_for_log(payload: Any) -> str:
    """Safe string for logs — never raises; empty payloads log as '(empty)'."""
    if payload is None:
        return '(empty)'
    if isinstance(payload, dict) and not payload:
        return '(empty)'
    if isinstance(payload, (list, tuple)) and len(payload) == 0:
        return '(empty)'
    try:
        text = json.dumps(payload, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        text = repr(payload)
    if not text or text in ('null', '""'):
        return '(empty)'
    if len(text) > _LOG_PAYLOAD_MAX_LEN:
        return f'{text[:_LOG_PAYLOAD_MAX_LEN]}…(truncated)'
    return text


def _normalize_parsed_body(parsed: Any) -> dict[str, Any]:
    """Wrap non-object JSON roots so logging and future handlers stay consistent."""
    if parsed is None:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {'_grow_payload': parsed}


def _safe_parse_grow_body(request) -> tuple[dict[str, Any], str | None]:
    """
    Parse POST body without raising. Returns (payload_dict, parse_note).
    parse_note is set when the body could not be parsed as expected JSON.
    """
    raw = request.body if request.body is not None else b''
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if not raw or not raw.strip():
        return {}, None

    content_type = (getattr(request, 'content_type', None) or '').lower()

    if 'application/json' in content_type or raw[:1] in (b'{', b'['):
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            logger.warning('grow_payment_webhook UTF-8 decode failed: %s', exc)
            return {}, 'invalid_encoding'

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning('grow_payment_webhook invalid JSON: %s', exc)
            return {}, 'invalid_json'

        return _normalize_parsed_body(parsed), None

    if 'multipart/form-data' in content_type or 'application/x-www-form-urlencoded' in content_type:
        try:
            if hasattr(request, 'POST') and request.POST:
                return dict(request.POST), None
            if hasattr(request, 'data') and request.data:
                if hasattr(request.data, 'dict'):
                    return request.data.dict(), None
                return dict(request.data), None
        except Exception as exc:
            logger.warning('grow_payment_webhook form parse failed: %s', exc)
            return {}, 'form_parse_error'

    try:
        parsed = json.loads(raw.decode('utf-8'))
        return _normalize_parsed_body(parsed), None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning('grow_payment_webhook unparsed body (%s bytes): %s', len(raw), exc)
        return {'_raw_preview': raw[:200].decode('utf-8', errors='replace')}, 'unparsed_body'


@csrf_exempt
@api_view(['POST'])
@parser_classes(_GROW_WEBHOOK_PARSERS)
@permission_classes([AllowAny])
def grow_payment_webhook(request):
    """
    Accept Grow PSP status callbacks.

    Always returns HTTP 200 so the gateway does not retry indefinitely on
    malformed or exploratory payloads; errors are logged for ops review.
    """
    try:
        payload, parse_note = _safe_parse_grow_body(request)
        if parse_note:
            logger.info(
                'grow_payment_webhook payload: %s (parse_note=%s)',
                _payload_for_log(payload),
                parse_note,
            )
        else:
            logger.info('grow_payment_webhook payload: %s', _payload_for_log(payload))
    except Exception as exc:
        logger.exception('grow_payment_webhook unexpected error: %s', exc)

    return Response({'status': 'received'})
