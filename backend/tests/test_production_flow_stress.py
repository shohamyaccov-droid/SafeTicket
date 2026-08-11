"""
Production-flow stress QA:
seller listing -> buyer discovery/reservation/order -> PayMe init -> webhook fulfillment
-> receipt email -> wallet ledger.
"""
from __future__ import annotations

import json
import logging
import random
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, SellerPayout, Ticket
from users.pricing import buyer_charge_from_base_amount, expected_buy_now_total
from users.tests.payme_ipn_test_helpers import sign_payme_ipn_payload
from wallets.models import WalletTransaction

logger = logging.getLogger(__name__)
User = get_user_model()

WEBHOOK_URL = '/api/payments/webhook/payme/'
INIT_URL = '/api/users/payments/payme/init/'
ORDERS_URL = '/api/users/orders/'
TICKETS_URL = '/api/users/tickets/'
RESERVE_URL = '/api/users/tickets/{ticket_id}/reserve/'


def _pdf_bytes(label: str) -> bytes:
    return (
        b'%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n'
        b'2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n'
        b'3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>endobj\n'
        + f'% {label}\n'.encode('utf-8')
        + b'%%EOF\n'
    )


def _fresh_pdf(name: str = 'ticket.pdf') -> SimpleUploadedFile:
    return SimpleUploadedFile(name, _pdf_bytes(name), content_type='application/pdf')


def _sign_payme_payload(payload: dict, secret: str = 'whsec_stress') -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return body, signature


@override_settings(
    DEBUG=True,
    SECRET_KEY='stress-test-secret',
    PAYME_SELLER_ID='MPL-STRESS-SELLER',
    PAYME_API_URL='https://testpay.payme.io/api',
    PAYME_IS_SANDBOX=True,
    PAYME_SANDBOX_ACCOUNT_EMAIL='stress-buyer@example.test',
    PAYME_WEBHOOK_SECRET='whsec_stress',
    FRONTEND_ORIGIN='https://example.test',
    API_PUBLIC_ORIGIN='https://api.example.test',
)
class ProductionPurchaseLifecycleStressTests(TestCase):
    """
    Runs 10 randomized purchase lifecycles and verifies all durable side effects.
    Duplicate webhook calls are included on every iteration to prove idempotency.
    """

    iterations = 10

    def setUp(self):
        self.client = APIClient()
        self.rng = random.Random(424242)
        self.artist = Artist.objects.create(name='Stress QA Artist')

    class ImmediateThread:
        def __init__(self, target=None, *args, **kwargs):
            self.target = target

        def start(self):
            if self.target:
                self.target()

    def _create_marketplace_fixture(self, iteration: int):
        price = Decimal(str(self.rng.choice(['79.90', '100.00', '123.45', '199.99', '250.50'])))
        seller = User.objects.create_user(
            username=f'stress_seller_{iteration}',
            email=f'stress_seller_{iteration}@example.test',
            password='test-pass-123',
            role='seller',
            is_email_verified=True,
        )
        buyer = User.objects.create_user(
            username=f'stress_buyer_{iteration}',
            email=f'stress_buyer_{iteration}@example.test',
            password='test-pass-123',
            role='buyer',
            is_email_verified=True,
            phone_number=f'050{iteration:07d}'[:10],
        )
        event = Event.objects.create(
            artist=self.artist,
            name=f'Stress QA Event {iteration}',
            date=timezone.now() + timedelta(days=30 + iteration),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=price,
            asking_price=price,
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file=_fresh_pdf(f'stress-ticket-{iteration}.pdf'),
        )
        return seller, buyer, event, ticket, price

    def _assert_ticket_search_finds_listing(self, buyer, ticket):
        self.client.force_authenticate(buyer)
        res = self.client.get(TICKETS_URL, {'search': ticket.event.name})
        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data
        rows = payload.get('results', payload) if isinstance(payload, dict) else payload
        found = any(int(row.get('id')) == ticket.id for row in rows)
        self.assertTrue(found, f'Buyer search did not return ticket_id={ticket.id}; payload={payload}')

    def _reserve_and_order(self, buyer, ticket, expected_total: Decimal) -> Order:
        self.client.force_authenticate(buyer)
        logger.info('stress_flow reserve ticket_id=%s buyer_id=%s', ticket.id, buyer.id)
        reserve = self.client.post(RESERVE_URL.format(ticket_id=ticket.id), {}, format='json')
        self.assertEqual(reserve.status_code, 200, reserve.content)

        logger.info('stress_flow create order ticket_id=%s total=%s', ticket.id, expected_total)
        order_res = self.client.post(
            ORDERS_URL,
            {
                'ticket': ticket.id,
                'total_amount': str(expected_total),
                'quantity': 1,
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertEqual(order_res.status_code, 201, order_res.data)
        order = Order.objects.get(pk=order_res.data['id'])
        self.assertEqual(order.status, 'pending_payment')
        return order

    def _init_payme(self, buyer, order, mock_generate, iteration: int) -> str:
        transaction_id = f'txn_stress_{iteration}_{order.id}'
        mock_generate.return_value = {
            'payme_sale_url': f'https://testpay.payme.io/hosted/stress-{iteration}',
            'transaction_id': transaction_id,
            'payme_sale_id': f'sale_stress_{iteration}',
            'raw': {'status_code': 0},
        }
        self.client.force_authenticate(buyer)
        res = self.client.post(
            INIT_URL,
            {
                'order_id': order.id,
                'success_url': 'https://example.test/payme/success',
                'failure_url': 'https://example.test/payme/failure',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        order.refresh_from_db()
        self.assertEqual(order.payme_transaction_id, transaction_id)
        return transaction_id

    def _post_success_webhook(self, order, transaction_id: str):
        amount = Decimal(order.total_paid_by_buyer or order.total_amount).quantize(Decimal('0.01'))
        payload = {
            'merchant_order_id': str(order.id),
            'status': 'success',
            'transaction_id': transaction_id,
            'payme_transaction_id': transaction_id,
            'payme_sale_id': f'sale_{transaction_id}',
            'payme_sale_code': f'code_{order.id}',
            'sale_price': int(amount * 100),
            'currency': order.currency or 'ILS',
        }
        signed = sign_payme_ipn_payload(payload)
        body = json.dumps(signed, separators=(',', ':')).encode('utf-8')
        return self.client.post(
            WEBHOOK_URL,
            body,
            content_type='application/json',
        )

    def _wait_for_receipt_email(self, mock_resend_send, buyer_email: str):
        for _ in range(30):
            payloads = [
                call.args[0]
                for call in mock_resend_send.call_args_list
                if buyer_email in (call.args[0].get('to') or [])
                and ('קבלה' in (call.args[0].get('subject') or '') or 'Receipt' in (call.args[0].get('subject') or ''))
            ]
            if payloads:
                return payloads[-1]
            time.sleep(0.05)
        self.fail(f'Receipt email was not sent to {buyer_email}')

    @patch.dict('os.environ', {'RESEND_API_KEY': 're_stress_key'})
    @patch('users.payments.threading.Thread', ImmediateThread)
    @patch('users.payments.transaction.on_commit', side_effect=lambda callback: callback())
    @patch('users.payme_views.generate_payme_sale_for_order')
    @patch('users.utils.emails.resend.Emails.send', return_value={'id': 'email_stress'})
    def test_randomized_full_lifecycle_10x_idempotent_webhooks_wallet_receipts_and_fee_math(
        self,
        mock_resend_send,
        mock_generate,
        _mock_on_commit,
    ):
        for iteration in range(self.iterations):
            with self.subTest(iteration=iteration):
                seller, buyer, _event, ticket, price = self._create_marketplace_fixture(iteration)
                ticket.refresh_from_db()
                expected_total = expected_buy_now_total(ticket.asking_price, 1)
                base, security_fee, expected_total_from_breakdown = buyer_charge_from_base_amount(ticket.asking_price)
                self.assertEqual(expected_total, expected_total_from_breakdown)

                logger.info(
                    'stress_flow[%s] start ticket_id=%s base=%s security_fee=%s total=%s',
                    iteration,
                    ticket.id,
                    base,
                    security_fee,
                    expected_total,
                )
                self._assert_ticket_search_finds_listing(buyer, ticket)
                order = self._reserve_and_order(buyer, ticket, expected_total)
                transaction_id = self._init_payme(buyer, order, mock_generate, iteration)

                with self.captureOnCommitCallbacks(execute=True):
                    first = self._post_success_webhook(order, transaction_id)
                second = self._post_success_webhook(order, transaction_id)
                self.assertEqual(first.status_code, 200, first.content)
                self.assertEqual(second.status_code, 200, second.content)

                order.refresh_from_db()
                ticket.refresh_from_db()
                self.assertEqual(order.status, 'paid')
                self.assertEqual(ticket.status, 'sold')
                self.assertEqual(order.final_negotiated_price, base)
                self.assertEqual(order.buyer_service_fee, security_fee)
                self.assertEqual(order.total_paid_by_buyer, expected_total)

                receipt_res = self.client.get(f'/api/users/orders/{order.id}/receipt/')
                self.assertEqual(receipt_res.status_code, 200, receipt_res.content)
                self.assertEqual(Decimal(receipt_res.data['buyer_service_fee']), security_fee)

                payout = SellerPayout.objects.get(order=order)
                self.assertEqual(payout.platform_fee, security_fee)
                self.assertEqual(payout.net_payout, base)
                self.assertEqual(SellerPayout.objects.filter(order=order).count(), 1)
                self.assertEqual(
                    WalletTransaction.objects.filter(
                        seller_payout=payout,
                        transaction_type=WalletTransaction.TransactionType.SALE_CREDIT,
                    ).count(),
                    1,
                )
                seller.wallet.refresh_from_db()
                self.assertEqual(seller.wallet.locked_balance, base)
                self.assertEqual(seller.wallet.available_balance, Decimal('0.00'))

                receipt_payload = self._wait_for_receipt_email(mock_resend_send, buyer.email)
                self.assertIn('attachments', receipt_payload)
                self.assertGreater(len(receipt_payload['attachments']), 0)
                logger.info('stress_flow[%s] complete order_id=%s', iteration, order.id)
