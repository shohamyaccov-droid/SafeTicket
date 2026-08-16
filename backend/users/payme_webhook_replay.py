"""Replay a captured PayMeWebhookLog through the live webhook view."""
from __future__ import annotations

from typing import Any

from rest_framework.test import APIRequestFactory

from users.payme_views import payme_webhook

WEBHOOK_PATH = '/api/payments/webhook/payme/'
MAX_ADMIN_REPLAY_BATCH = 20
_SKIP_HEADER_NAMES = frozenset(
    {
        'content-type',
        'content-length',
        'host',
        'connection',
        'transfer-encoding',
    }
)


def content_type_for_webhook_log(log) -> str:
    headers = log.headers if isinstance(getattr(log, 'headers', None), dict) else {}
    header_ct = str(headers.get('Content-Type') or headers.get('content-type') or '').strip()
    if header_ct:
        return header_ct
    raw = (getattr(log, 'raw_body', None) or '').lstrip()
    if raw.startswith('{') or raw.startswith('['):
        return 'application/json'
    return 'application/x-www-form-urlencoded'


def build_payme_webhook_replay_request(log):
    """Build a RequestFactory POST that matches the original PayMe notify."""
    raw_text = getattr(log, 'raw_body', None) or ''
    raw_body = raw_text.encode('utf-8')
    content_type = content_type_for_webhook_log(log)
    request = APIRequestFactory().post(
        WEBHOOK_PATH,
        data=raw_body,
        content_type=content_type,
    )
    headers = log.headers if isinstance(getattr(log, 'headers', None), dict) else {}
    for key, value in headers.items():
        key_s = str(key)
        if key_s.lower() in _SKIP_HEADER_NAMES:
            continue
        request.META['HTTP_' + key_s.upper().replace('-', '_')] = str(value)
    request.META['REMOTE_ADDR'] = '127.0.0.1'
    request.META['HTTP_X_PAYME_WEBHOOK_REPLAY'] = f'log:{getattr(log, "pk", "")}'
    return request


def format_payme_webhook_replay_summary(log_id: int, response) -> str:
    status_code = getattr(response, 'status_code', None)
    data = getattr(response, 'data', None)
    parts = [f'Log #{log_id}: HTTP {status_code}']
    if isinstance(data, dict):
        for key in (
            'received',
            'finalized',
            'order_status',
            'reason',
            'error',
            'http_status',
        ):
            value = data.get(key)
            if value not in (None, ''):
                parts.append(f'{key}={value}')
    elif data not in (None, ''):
        parts.append(f'data={data}')
    return ' '.join(parts)


def replay_payme_webhook_log(log) -> dict[str, Any]:
    """
    Re-run a saved IPN through ``payme_webhook``.

    Hits PayMe get-sales / get-transactions. Already-paid orders stay paid
    (idempotent finalize); they still exercise the live API lookup.
    """
    log_id = getattr(log, 'pk', None)
    raw_text = (getattr(log, 'raw_body', None) or '').strip()
    if not raw_text:
        return {
            'ok': False,
            'log_id': log_id,
            'status_code': None,
            'data': None,
            'summary': f'Log #{log_id}: empty raw_body — nothing to replay',
        }

    request = build_payme_webhook_replay_request(log)
    response = payme_webhook(request)
    status_code = int(getattr(response, 'status_code', 0) or 0)
    data = getattr(response, 'data', None)
    data_dict = data if isinstance(data, dict) else {}
    finalized = bool(data_dict.get('finalized'))
    reason = str(data_dict.get('reason') or '')
    http_ok = 200 <= status_code < 400
    passed = finalized or reason == 'already_paid'
    return {
        'ok': bool(http_ok and passed),
        'log_id': log_id,
        'status_code': status_code,
        'data': data,
        'summary': format_payme_webhook_replay_summary(log_id, response),
        'response': response,
    }
