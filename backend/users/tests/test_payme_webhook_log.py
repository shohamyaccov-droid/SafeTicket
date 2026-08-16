"""PayMeWebhookLog capture + raw-body IPN verification + replay command."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import StringIO
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from users.admin import PayMeWebhookLogAdmin
from users.models import Artist, Event, Order, PayMeWebhookLog, Ticket, User
from users.payme_webhook_replay import replay_payme_webhook_log
from users.payments import (
    extract_payme_raw_sign_fields,
    parse_payme_raw_body_fields,
)
from users.tests.payme_ipn_test_helpers import (
    MOCK_PAYME_SALE_FAILED,
    MOCK_PAYME_SALE_SUCCESS,
    PAYME_IPN_TEST_SETTINGS,
    MockPayMeSaleConfirmMixin,
    sign_payme_ipn_payload,
)


class ParsePaymeRawBodyFieldsTests(TestCase):
    def test_parse_qsl_keeps_blank_values(self):
        body = 'buyer_card_mask=&buyer_card_exp=&sale_price=110.50&is_token_sale=true'
        fields = parse_payme_raw_body_fields(body.encode('utf-8'))
        self.assertEqual(fields.get('buyer_card_mask'), '')
        self.assertEqual(fields.get('buyer_card_exp'), '')
        self.assertEqual(fields.get('sale_price'), '110.50')
        self.assertEqual(fields.get('is_token_sale'), 'true')

    def test_extract_sign_fields_ignores_request_post(self):
        """HMAC source must be raw body, not a mutated QueryDict."""
        raw = urlencode(
            {
                'currency': 'ILS',
                'sale_price': '110.50',
                'is_token_sale': 'true',
                'buyer_card_mask': '',
                'payme_sale_id': 'txn_1',
            }
        )
        request = APIRequestFactory().post(
            '/api/payments/webhook/payme/',
            data=raw,
            content_type='application/x-www-form-urlencoded',
        )
        # Poison POST if present — raw body must still win.
        if hasattr(request, 'POST') and request.POST is not None:
            try:
                request.POST = request.POST.copy()
                request.POST['sale_price'] = '999'
                request.POST['is_token_sale'] = 'True'
            except Exception:
                pass

        fields = extract_payme_raw_sign_fields(request)
        self.assertEqual(fields.get('sale_price'), '110.50')
        self.assertEqual(fields.get('is_token_sale'), 'true')
        self.assertEqual(fields.get('buyer_card_mask'), '')
        self.assertNotIn('payme_signature', fields)


@override_settings(**PAYME_IPN_TEST_SETTINGS)
class PayMeWebhookLogCaptureTests(MockPayMeSaleConfirmMixin, TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller_wh', password='x', role='seller')
        self.order = Order.objects.create(
            user=self.seller,
            status='pending_payment',
            total_amount=Decimal('110.50'),
            total_paid_by_buyer=Decimal('110.50'),
            currency='ILS',
            payme_transaction_id='txn_log_capture_1',
        )

    def test_webhook_persists_log_before_rejection(self):
        client = APIClient()
        body = urlencode(
            {
                'payme_sale_id': 'txn_log_capture_1',
                'payme_transaction_id': 'txn_log_capture_1',
                'notify_type': 'sale-complete',
                'currency': 'ILS',
                'sale_price': '110.50',
                'status': '0',
                'buyer_card_mask': '',
                'payme_signature': 'deadbeefdeadbeefdeadbeefdeadbeef',
            }
        )
        before = PayMeWebhookLog.objects.count()
        self.mock_confirm_payme_sale_status.return_value = dict(MOCK_PAYME_SALE_FAILED)
        response = client.post(
            '/api/payments/webhook/payme/',
            data=body,
            content_type='application/x-www-form-urlencoded',
        )
        self.assertEqual(PayMeWebhookLog.objects.count(), before + 1)
        log = PayMeWebhookLog.objects.latest('id')
        self.assertIn('payme_sale_id=txn_log_capture_1', log.raw_body)
        self.assertIn('buyer_card_mask=', log.raw_body)
        self.assertFalse(log.is_valid)
        self.assertEqual(log.error_message, 'api_status_failed')
        self.assertEqual(response.status_code, 200)


@override_settings(**PAYME_IPN_TEST_SETTINGS)
class ReplayPaymeWebhookCommandTests(MockPayMeSaleConfirmMixin, TestCase):
    def test_dry_run_and_replay_command(self):
        raw_fields = {
            'currency': 'ILS',
            'notify_type': 'sale-complete',
            'payme_sale_id': 'txn_replay_1',
            'payme_transaction_id': 'txn_replay_1',
            'sale_price': '50.00',
            'status': '0',
            'buyer_card_mask': '',
        }
        signed = sign_payme_ipn_payload(raw_fields)
        raw_body = urlencode(signed)
        log = PayMeWebhookLog.objects.create(
            raw_body=raw_body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            is_valid=False,
            error_message='seed',
        )

        out = StringIO()
        call_command('replay_payme_webhook', str(log.pk), '--dry-run', stdout=out)
        self.assertIn('payme_transaction_id=', out.getvalue())
        self.assertIn('[DRY RUN]', out.getvalue())

        # Full replay hits the view (order may 404 — still exercises the command path).
        out2 = StringIO()
        call_command('replay_payme_webhook', str(log.pk), stdout=out2)
        self.assertIn('Replay response status=', out2.getvalue())


def _admin_request(user):
    request = RequestFactory().post('/admin/users/paymewebhooklog/')
    request.user = user
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


@override_settings(**PAYME_IPN_TEST_SETTINGS)
class ReplayPayMeWebhookAdminActionTests(MockPayMeSaleConfirmMixin, TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(
            username='admin_replay',
            email='admin-replay@example.com',
            password='pass',
        )
        self.seller = User.objects.create_user(
            username='seller_replay',
            email='seller-replay@example.com',
            password='pass',
            role='seller',
        )
        artist = Artist.objects.create(name='Replay Artist')
        event = Event.objects.create(
            artist=artist,
            name='Replay Show',
            date=timezone.now() + timedelta(days=30),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file='tickets/pdfs/replay.pdf',
            status='reserved',
            verification_status='מאומת',
            available_quantity=1,
            reserved_by=self.staff,
            reserved_at=timezone.now(),
        )
        self.order = Order.objects.create(
            user=self.staff,
            ticket=self.ticket,
            ticket_ids=[self.ticket.id],
            status='pending_payment',
            total_amount=Decimal('110.50'),
            total_paid_by_buyer=Decimal('110.50'),
            currency='ILS',
            quantity=1,
            payme_transaction_id='txn_admin_replay_1',
        )
        raw_fields = {
            'currency': 'ILS',
            'notify_type': 'sale-complete',
            'payme_sale_id': 'txn_admin_replay_1',
            'payme_transaction_id': 'txn_admin_replay_1',
            'sale_price': '110.50',
            'status': '0',
            'buyer_card_mask': '',
        }
        self.log = PayMeWebhookLog.objects.create(
            raw_body=urlencode(sign_payme_ipn_payload(raw_fields)),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            is_valid=False,
            error_message='seed',
        )
        self.model_admin = PayMeWebhookLogAdmin(PayMeWebhookLog, AdminSite())

    def test_replay_webhook_action_is_registered(self):
        self.assertEqual(PayMeWebhookLogAdmin.actions, ['replay_webhook'])
        self.assertEqual(
            PayMeWebhookLogAdmin.replay_webhook.short_description,
            'Replay Selected Webhooks',
        )

    def test_replay_selected_webhooks_runs_payme_validation_and_messages(self):
        self.mock_confirm_payme_sale_status.return_value = dict(MOCK_PAYME_SALE_SUCCESS)
        request = _admin_request(self.staff)
        self.model_admin.replay_webhook(
            request,
            PayMeWebhookLog.objects.filter(pk=self.log.pk),
        )
        stored = [m.message for m in messages.get_messages(request)]
        self.assertTrue(stored)
        self.assertIn(f'Log #{self.log.pk}:', stored[0])
        self.assertIn('HTTP', stored[0])
        self.mock_confirm_payme_sale_status.assert_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertTrue(any('finalized=True' in str(m) for m in stored))

    def test_replay_already_paid_order_still_calls_payme_and_stays_paid(self):
        self.order.status = 'paid'
        self.order.save(update_fields=['status'])
        self.mock_confirm_payme_sale_status.reset_mock()
        self.mock_confirm_payme_sale_status.return_value = dict(MOCK_PAYME_SALE_SUCCESS)
        result = replay_payme_webhook_log(self.log)
        self.mock_confirm_payme_sale_status.assert_called()
        self.assertTrue(result['ok'])
        self.assertEqual(result['status_code'], 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIn('finalized=True', result['summary'])

    def test_replay_empty_body_reports_error(self):
        empty = PayMeWebhookLog.objects.create(raw_body='   ', headers={})
        request = _admin_request(self.staff)
        self.model_admin.replay_webhook(request, PayMeWebhookLog.objects.filter(pk=empty.pk))
        stored = [str(m.message) for m in messages.get_messages(request)]
        self.assertTrue(any('empty raw_body' in m for m in stored))

    def test_replay_payme_api_error_is_shown_in_admin_message(self):
        self.mock_confirm_payme_sale_status.return_value = {
            'ok': False,
            'found': False,
            'status': None,
            'error': 'unauthorized',
            'http_status': 401,
            'url': 'https://live.payme.io/api/get-transactions',
            'response_text': '{"error":"unauthorized"}',
        }
        request = _admin_request(self.staff)
        self.model_admin.replay_webhook(
            request,
            PayMeWebhookLog.objects.filter(pk=self.log.pk),
        )
        stored = [str(m.message) for m in messages.get_messages(request)]
        blob = ' '.join(stored)
        self.assertIn('payme_api_unavailable', blob)
        self.assertIn('401', blob)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending_payment')
