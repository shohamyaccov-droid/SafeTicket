"""
Replay a saved PayMeWebhookLog through the live webhook handler (offline IPN debug).

Usage (from backend/):

  python manage.py replay_payme_webhook 42
  python manage.py replay_payme_webhook 42 --dry-run

Requires the log's raw_body (exact wire bytes as text). Creates a new PayMeWebhookLog
row for the replay request as well.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from rest_framework.test import APIRequestFactory

from users.models import PayMeWebhookLog
from users.payme_views import payme_webhook
from users.payments import (
    compute_payme_ipn_md5_signature,
    extract_payme_raw_sign_fields,
    get_payme_config,
    parse_payme_raw_body_fields,
)


class Command(BaseCommand):
    help = 'Replay a saved PayMeWebhookLog through /api/payments/webhook/payme/ locally.'

    def add_arguments(self, parser):
        parser.add_argument('log_id', type=int, help='PayMeWebhookLog primary key')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only print parsed fields / expected IPN MD5; do not call the webhook view.',
        )

    def handle(self, *args, **options):
        log_id = options['log_id']
        dry_run = bool(options.get('dry_run'))

        try:
            log = PayMeWebhookLog.objects.get(pk=log_id)
        except PayMeWebhookLog.DoesNotExist as exc:
            raise CommandError(f'PayMeWebhookLog id={log_id} not found') from exc

        raw_text = log.raw_body or ''
        raw_body = raw_text.encode('utf-8')
        headers = log.headers if isinstance(log.headers, dict) else {}
        content_type = (
            headers.get('Content-Type')
            or headers.get('content-type')
            or 'application/x-www-form-urlencoded'
        )

        fields = parse_payme_raw_body_fields(raw_body)
        txn = fields.get('payme_transaction_id', '')
        sale = fields.get('payme_sale_id', '')
        cfg = get_payme_config()
        expected = ''
        if (cfg['api_key'] or '').strip() and (cfg['api_password'] or '').strip():
            expected = compute_payme_ipn_md5_signature(
                merchant_key=cfg['api_key'],
                merchant_password=cfg['api_password'],
                payme_transaction_id=txn,
                payme_sale_id=sale,
            )

        self.stdout.write(self.style.NOTICE(f'PayMeWebhookLog#{log.pk} created_at={log.created_at}'))
        self.stdout.write(f'  is_valid={log.is_valid} error_message={log.error_message!r}')
        self.stdout.write(f'  content_type={content_type}')
        self.stdout.write(f'  raw_body_len={len(raw_text)} keys={sorted(fields.keys())}')
        self.stdout.write(f'  payme_transaction_id={txn!r} payme_sale_id={sale!r}')
        if expected:
            self.stdout.write(f'  expected_ipn_md5={expected!r}')
        sig = fields.get('payme_signature') or fields.get('paymeSignature') or fields.get('signature') or ''
        if sig:
            self.stdout.write(f'  payme_signature_prefix={(sig[:16] + "…") if len(sig) > 16 else sig}')

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY RUN] Skipping webhook view call.'))
            self.stdout.write(json.dumps(fields, ensure_ascii=False, indent=2))
            return

        factory = APIRequestFactory()
        request = factory.post(
            '/api/payments/webhook/payme/',
            data=raw_body,
            content_type=content_type,
        )
        for key, value in headers.items():
            key_s = str(key)
            if key_s.lower() in ('content-type', 'content-length', 'host'):
                continue
            meta_key = 'HTTP_' + key_s.upper().replace('-', '_')
            request.META[meta_key] = str(value)

        extracted = extract_payme_raw_sign_fields(request, raw_body=raw_body)
        self.stdout.write(f'  extract_payme_raw_sign_fields keys={sorted(extracted.keys())}')

        response = payme_webhook(request)
        status_code = getattr(response, 'status_code', None)
        data = getattr(response, 'data', None)
        style = self.style.SUCCESS if status_code and int(status_code) < 400 else self.style.ERROR
        self.stdout.write(style(f'Replay response status={status_code} data={data}'))
