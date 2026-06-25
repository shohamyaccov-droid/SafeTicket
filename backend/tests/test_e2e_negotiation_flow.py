"""
End-to-end negotiation checkout audit:
seller upload -> buyer offer -> seller acceptance -> PayMe webhook -> wallet ledger.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Offer, Order, SellerPayout, Ticket
from users.pricing import buyer_charge_from_base_amount
from users.serializers import user_can_access_ticket_pdf
from wallets.models import WalletTransaction

User = get_user_model()

TICKETS_URL = '/api/users/tickets/'
OFFERS_URL = '/api/users/offers/'
ORDERS_URL = '/api/users/orders/'
INIT_PAYME_URL = '/api/users/payments/payme/init/'
WEBHOOK_URL = '/api/payments/webhook/payme/'


def _pdf_file(name='negotiated-ticket.pdf'):
    return SimpleUploadedFile(
        name,
        b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
        content_type='application/pdf',
    )


def _sign_payme_payload(payload: dict, secret: str = 'whsec_negotiation') -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return body, signature


@override_settings(
    DEBUG=True,
    SECRET_KEY='negotiation-e2e-secret',
    PAYME_SELLER_ID='MPL-NEGOTIATION-SELLER',
    PAYME_API_URL='https://testpay.payme.io/api',
    PAYME_IS_SANDBOX=True,
    PAYME_SANDBOX_ACCOUNT_EMAIL='buyer-negotiation@example.test',
    PAYME_WEBHOOK_SECRET='whsec_negotiation',
    FRONTEND_ORIGIN='https://example.test',
    API_PUBLIC_ORIGIN='https://api.example.test',
)
class NegotiatedOfferPayMeWalletE2ETests(TestCase):
    class ImmediateThread:
        def __init__(self, target=None, *args, **kwargs):
            self.target = target

        def start(self):
            if self.target:
                self.target()

    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='negotiation_seller',
            email='seller-negotiation@example.test',
            password='test-pass-123',
            role='seller',
            is_email_verified=True,
            account_holder_name='Negotiation Seller',
            bank_name='12',
            branch_number='345',
            account_number='987654321',
        )
        self.buyer = User.objects.create_user(
            username='negotiation_buyer',
            email='buyer-negotiation@example.test',
            password='test-pass-123',
            role='buyer',
            is_email_verified=True,
        )
        self.artist = Artist.objects.create(name='Negotiation E2E Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Negotiation E2E Concert',
            date=timezone.now() + timedelta(days=45),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )

    def _upload_active_ticket(self) -> Ticket:
        self.client.force_authenticate(self.seller)
        res = self.client.post(
            TICKETS_URL,
            {
                'event_id': str(self.event.id),
                'original_price': '200.00',
                'listing_price': '200.00',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'il_legal_declaration': 'true',
                'delivery_method': 'instant',
                'pdf_file_0': _pdf_file(),
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 201, res.content)
        ticket = Ticket.objects.get(pk=res.data['id'])
        self.assertEqual(ticket.seller_id, self.seller.id)
        self.assertEqual(ticket.asking_price, Decimal('200.00'))

        # Marketplace offers are available for active listings. If upload moderation
        # leaves the row pending, simulate the final approved listing state.
        if ticket.status != 'active':
            ticket.status = 'active'
            ticket.verification_status = 'מאומת'
            ticket.save(update_fields=['status', 'verification_status', 'updated_at'])
        return ticket

    def _post_success_webhook(self, order: Order, transaction_id: str):
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
        body, sig = _sign_payme_payload(payload)
        return self.client.post(
            WEBHOOK_URL,
            body,
            content_type='application/json',
            HTTP_X_PAYME_SIGNATURE=sig,
        )

    def _wait_for_receipt_email(self, mock_resend_send):
        for _ in range(30):
            payloads = [
                call.args[0]
                for call in mock_resend_send.call_args_list
                if self.buyer.email in (call.args[0].get('to') or [])
                and ('קבלה' in (call.args[0].get('subject') or '') or 'Receipt' in (call.args[0].get('subject') or ''))
            ]
            if payloads:
                return payloads[-1]
            time.sleep(0.05)
        self.fail('Receipt email was not sent for negotiated checkout')

    @patch.dict('os.environ', {'RESEND_API_KEY': 're_negotiation_key'})
    @patch('users.payments.threading.Thread', ImmediateThread)
    @patch('users.payments.transaction.on_commit', side_effect=lambda callback: callback())
    @patch('users.payme_views.generate_payme_sale_for_order')
    @patch('users.utils.emails.resend.Emails.send', return_value={'id': 'email_negotiation'})
    def test_counter_offer_acceptance_checkout_payme_wallet_and_receipt_math(
        self,
        mock_resend_send,
        mock_generate_payme_sale,
        _mock_on_commit,
    ):
        ticket = self._upload_active_ticket()

        self.client.force_authenticate(self.buyer)
        offer_res = self.client.post(
            OFFERS_URL,
            {'ticket': ticket.id, 'amount': '150.00', 'quantity': 1},
            format='json',
        )
        self.assertEqual(offer_res.status_code, 201, offer_res.content)
        offer = Offer.objects.get(pk=offer_res.data['id'])
        self.assertEqual(offer.amount, Decimal('150.00'))
        self.assertEqual(offer.buyer_id, self.buyer.id)

        self.client.force_authenticate(self.seller)
        accept_res = self.client.post(f'{OFFERS_URL}{offer.id}/accept/', {}, format='json')
        self.assertEqual(accept_res.status_code, 200, accept_res.content)
        offer.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(offer.status, 'accepted')
        self.assertIn(ticket.status, ('active', 'reserved'))
        if ticket.status == 'reserved':
            self.assertEqual(ticket.reserved_by_id, self.buyer.id)

        negotiated_price, security_fee, expected_total = buyer_charge_from_base_amount(Decimal('150.00'))
        self.assertEqual(negotiated_price, Decimal('150.00'))
        self.assertEqual(security_fee, Decimal('22.50'))
        self.assertEqual(expected_total, Decimal('172.50'))

        self.client.force_authenticate(self.buyer)
        order_res = self.client.post(
            ORDERS_URL,
            {
                'ticket': ticket.id,
                'quantity': 1,
                'total_amount': str(expected_total),
                'offer_id': offer.id,
            },
            format='json',
        )
        self.assertEqual(order_res.status_code, 201, order_res.content)
        order = Order.objects.get(pk=order_res.data['id'])
        self.assertEqual(order.status, 'pending_payment')
        self.assertEqual(order.user_id, self.buyer.id)
        self.assertEqual(order.pending_offer_id, offer.id)
        self.assertEqual(order.total_amount, expected_total)

        transaction_id = f'txn_negotiated_{order.id}'
        mock_generate_payme_sale.return_value = {
            'payme_sale_url': 'https://testpay.payme.io/hosted/negotiated-checkout',
            'transaction_id': transaction_id,
            'payme_sale_id': f'sale_negotiated_{order.id}',
            'raw': {'status_code': 0},
        }
        init_res = self.client.post(
            INIT_PAYME_URL,
            {
                'order_id': order.id,
                'success_url': 'https://example.test/payme/success',
                'failure_url': 'https://example.test/payme/failure',
            },
            format='json',
        )
        self.assertEqual(init_res.status_code, 200, init_res.content)
        order.refresh_from_db()
        self.assertEqual(order.payme_transaction_id, transaction_id)

        with self.captureOnCommitCallbacks(execute=True):
            webhook_res = self._post_success_webhook(order, transaction_id)
        self.assertEqual(webhook_res.status_code, 200, webhook_res.content)
        self.assertTrue(webhook_res.data.get('finalized'), webhook_res.data)

        order.refresh_from_db()
        ticket.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.payme_status, 'success')
        self.assertEqual(order.related_offer_id, offer.id)
        self.assertEqual(order.final_negotiated_price, negotiated_price)
        self.assertEqual(order.buyer_service_fee, security_fee)
        self.assertEqual(order.total_paid_by_buyer, expected_total)
        self.assertEqual(order.net_seller_revenue, negotiated_price)
        self.assertEqual(ticket.status, 'sold')
        self.assertEqual(ticket.available_quantity, 0)
        self.assertTrue(order.covers_ticket(ticket.id))
        self.assertTrue(user_can_access_ticket_pdf(self.buyer, ticket))

        payout = SellerPayout.objects.get(order=order)
        self.assertEqual(payout.seller_id, self.seller.id)
        self.assertEqual(payout.total_paid, expected_total)
        self.assertEqual(payout.platform_fee, security_fee)
        self.assertEqual(payout.net_payout, negotiated_price)
        self.assertEqual(
            WalletTransaction.objects.filter(
                seller_payout=payout,
                transaction_type=WalletTransaction.TransactionType.SALE_CREDIT,
                amount=negotiated_price,
            ).count(),
            1,
        )
        self.seller.wallet.refresh_from_db()
        self.assertEqual(self.seller.wallet.locked_balance, negotiated_price)
        self.assertEqual(self.seller.wallet.available_balance, Decimal('0.00'))

        receipt_res = self.client.get(f'/api/users/orders/{order.id}/receipt/')
        self.assertEqual(receipt_res.status_code, 200, receipt_res.content)
        self.assertEqual(Decimal(receipt_res.data['final_negotiated_price']), negotiated_price)
        self.assertEqual(Decimal(receipt_res.data['buyer_service_fee']), security_fee)
        self.assertEqual(Decimal(receipt_res.data['total_paid_by_buyer']), expected_total)

        receipt_payload = self._wait_for_receipt_email(mock_resend_send)
        self.assertIn('attachments', receipt_payload)
        self.assertGreater(len(receipt_payload['attachments']), 0)
