"""Unit tests for services.payme_service."""
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from services.payme_service import (
    PayMeError,
    PayMeSettings,
    build_standard_generate_sale_body,
    extract_payme_sale_url,
    extract_transaction_id,
    generate_payme_sale,
    get_payme_sandbox_account_email,
    is_payme_sandbox,
    money_to_agorot,
    resolve_payme_customer_email,
)


class PayMeServiceUnitTests(SimpleTestCase):
    @override_settings(
        PAYME_API_URL='https://testpay.payme.io/api',
        PAYME_IS_SANDBOX=True,
        PAYME_SANDBOX_ACCOUNT_EMAIL='tradetix.support+1@gmail.com',
    )
    def test_sandbox_customer_email_resolution(self):
        self.assertTrue(is_payme_sandbox())
        self.assertEqual(get_payme_sandbox_account_email(), 'tradetix.support+1@gmail.com')
        self.assertEqual(
            resolve_payme_customer_email('production@tradetix.com'),
            'tradetix.support+1@gmail.com',
        )

    @override_settings(
        PAYME_API_URL='https://preprod.paymeservice.com/api',
        PAYME_IS_SANDBOX=False,
        PAYME_SANDBOX_ACCOUNT_EMAIL='tradetix.support+1@gmail.com',
    )
    def test_preprod_url_detected_as_sandbox(self):
        self.assertTrue(is_payme_sandbox())
        self.assertEqual(
            resolve_payme_customer_email('buyer@example.com'),
            'tradetix.support+1@gmail.com',
        )

    @override_settings(
        PAYME_API_URL='https://live.payme.io/api',
        PAYME_IS_SANDBOX=False,
    )
    def test_production_customer_email_unchanged(self):
        self.assertFalse(is_payme_sandbox())
        self.assertEqual(resolve_payme_customer_email('buyer@example.com'), 'buyer@example.com')

    def test_money_to_agorot(self):
        self.assertEqual(money_to_agorot('115.00'), 11500)
        self.assertEqual(money_to_agorot(Decimal('99.99')), 9999)
        self.assertEqual(money_to_agorot(50), 5000)

    def test_extract_payme_sale_url_prefers_payme_sale_url(self):
        data = {
            'payme_sale_url': 'https://testpay.payme.io/sale/abc',
            'redirect_url': 'https://other.example/ignored',
        }
        self.assertEqual(extract_payme_sale_url(data), 'https://testpay.payme.io/sale/abc')

    def test_extract_payme_sale_url_nested(self):
        data = {'data': {'sale_url': 'https://testpay.payme.io/nested'}}
        self.assertEqual(extract_payme_sale_url(data), 'https://testpay.payme.io/nested')

    def test_extract_transaction_id(self):
        self.assertEqual(extract_transaction_id({'payme_sale_id': 'sale_99'}), 'sale_99')
        self.assertEqual(extract_transaction_id({'transaction_id': 'txn_1'}), 'txn_1')

    @override_settings(
        PAYME_SELLER_ID='MPL-TEST-SELLER',
        PAYME_API_URL='https://testpay.payme.io/api',
        PAYME_IS_SANDBOX=True,
        PAYME_SANDBOX_ACCOUNT_EMAIL='tradetix.support+1@gmail.com',
        API_PUBLIC_ORIGIN='http://127.0.0.1:8000',
        FRONTEND_ORIGIN='http://localhost:5173',
    )
    def test_build_standard_generate_sale_body(self):
        body = build_standard_generate_sale_body(
            amount=Decimal('115.00'),
            ticket_name='Section 5 Ticket',
            customer_email='buyer@example.com',
            order_id='42',
            success_url='http://localhost/success',
            failure_url='http://localhost/failure',
        )
        self.assertEqual(body['seller_payme_id'], 'MPL-TEST-SELLER')
        self.assertEqual(body['sale_price'], 11500)
        self.assertEqual(body['currency'], 'ILS')
        self.assertEqual(body['product_name'], 'Section 5 Ticket')
        self.assertEqual(body['buyer_email'], 'tradetix.support+1@gmail.com')
        self.assertEqual(body['merchant_order_id'], '42')
        self.assertEqual(body['sale_return_url'], 'http://localhost/success')
        self.assertEqual(body['sale_cancel_url'], 'http://localhost/failure')
        self.assertEqual(body['sale_callback_url'], 'http://127.0.0.1:8000/api/payments/webhook/payme/')
        self.assertEqual(body['sale_payment_method'], 'multi')

    @override_settings(
        PAYME_SELLER_ID='MPL-TEST-SELLER',
        PAYME_API_URL='https://testpay.payme.io/api',
        API_PUBLIC_ORIGIN='http://127.0.0.1:8000',
        FRONTEND_ORIGIN='http://localhost:5173',
    )
    def test_build_standard_generate_sale_body_includes_buyer_identity(self):
        body = build_standard_generate_sale_body(
            amount=Decimal('115.00'),
            ticket_name='Section 5 Ticket',
            customer_email='buyer@example.com',
            order_id='42',
            buyer_name='Israel Israeli',
            buyer_phone='0501234567',
        )
        self.assertEqual(body['buyer_name'], 'Israel Israeli')
        self.assertEqual(body['buyer_phone'], '972501234567')

    @override_settings(PAYME_SELLER_ID='')
    def test_generate_payme_sale_requires_seller_id(self):
        with self.assertRaises(PayMeError) as ctx:
            generate_payme_sale(100, 'Ticket', 'a@b.com', '1')
        self.assertIn('PAYME_SELLER_ID', str(ctx.exception))

    @override_settings(
        PAYME_SELLER_ID='MPL-TEST',
        PAYME_GENERATE_SALE_URL='https://testpay.payme.io/api/generate-sale',
    )
    @patch('services.payme_service.requests.post')
    def test_generate_payme_sale_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status_code': 0,
            'payme_sale_url': 'https://testpay.payme.io/hosted/xyz',
            'payme_sale_id': 'sale_xyz',
            'transaction_id': 'txn_xyz',
        }
        mock_post.return_value = mock_response

        result = generate_payme_sale(
            amount=115.0,
            ticket_name='VIP Ticket',
            customer_email='buyer@test.invalid',
            order_id='99',
        )

        self.assertEqual(result['payme_sale_url'], 'https://testpay.payme.io/hosted/xyz')
        self.assertEqual(result['transaction_id'], 'txn_xyz')
        self.assertEqual(result['payme_sale_id'], 'sale_xyz')
        mock_post.assert_called_once()
        sent_body = mock_post.call_args.kwargs['json']
        self.assertEqual(sent_body['sale_price'], 11500)
        self.assertEqual(sent_body['seller_payme_id'], 'MPL-TEST')

    @override_settings(
        PAYME_SELLER_ID='MPL-TEST',
        PAYME_GENERATE_SALE_URL='https://testpay.payme.io/api/generate-sale',
    )
    @patch('services.payme_service.requests.post')
    def test_generate_payme_sale_api_error_status_code(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'status_code': 1,
            'status_error_details': 'Invalid seller',
        }
        mock_post.return_value = mock_response

        with self.assertRaises(PayMeError) as ctx:
            generate_payme_sale(10, 'T', 'a@b.com', '1')
        self.assertIn('Invalid seller', str(ctx.exception))

    @override_settings(
        PAYME_SELLER_ID='MPL-TEST',
        PAYME_GENERATE_SALE_URL='https://testpay.payme.io/api/generate-sale',
    )
    @patch('services.payme_service.requests.post')
    def test_generate_payme_sale_missing_checkout_url(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status_code': 0}
        mock_post.return_value = mock_response

        with self.assertRaises(PayMeError) as ctx:
            generate_payme_sale(10, 'T', 'a@b.com', '1')
        self.assertIn('payme_sale_url', str(ctx.exception))

    @override_settings(
        PAYME_SELLER_ID='MPL-TEST',
        PAYME_GENERATE_SALE_URL='https://testpay.payme.io/api/generate-sale',
    )
    @patch('services.payme_service.requests.post')
    def test_generate_payme_sale_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'error': 'server error'}
        mock_post.return_value = mock_response

        with self.assertRaises(PayMeError) as ctx:
            generate_payme_sale(10, 'T', 'a@b.com', '1')
        self.assertEqual(ctx.exception.http_status, 500)

    @override_settings(
        PAYME_SELLER_ID='MPL-TEST',
        PAYME_GENERATE_SALE_URL='https://testpay.payme.io/api/generate-sale',
    )
    @patch('services.payme_service.requests.post')
    def test_generate_payme_sale_timeout(self, mock_post):
        import requests

        mock_post.side_effect = requests.Timeout('timed out')
        with self.assertRaises(PayMeError) as ctx:
            generate_payme_sale(10, 'T', 'a@b.com', '1')
        self.assertIn('timed out', str(ctx.exception))

    @override_settings(PAYME_SELLER_ID='seller-1', PAYME_MERCHANT_ID='merchant-legacy')
    def test_payme_settings_from_django(self):
        cfg = PayMeSettings.from_django()
        self.assertEqual(cfg.seller_id, 'seller-1')
        self.assertTrue(cfg.is_configured)


class GeneratePaymeSaleForOrderTests(TestCase):
    @override_settings(PAYME_SELLER_ID='MPL-TEST')
    @patch('services.payme_service.generate_payme_sale')
    def test_generate_payme_sale_for_order_uses_order_totals(self, mock_generate):
        from django.contrib.auth import get_user_model

        from users.models import Event, Order, Ticket

        User = get_user_model()
        seller = User.objects.create_user(username='s', email='s@test.invalid', password='x', role='seller')
        buyer = User.objects.create_user(username='b', email='b@test.invalid', password='x')
        event = Event.objects.create(
            name='Test Event',
            date=timezone.now() + timedelta(days=10),
            venue='Arena',
            city='TLV',
            country='IL',
        )
        ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            asking_price=Decimal('100.00'),
            original_price=Decimal('100.00'),
            status='reserved',
            available_quantity=1,
        )
        order = Order.objects.create(
            user=buyer,
            ticket=ticket,
            status='pending_payment',
            total_amount=Decimal('115.00'),
            total_paid_by_buyer=Decimal('115.00'),
            currency='ILS',
            quantity=2,
            event_name='Test Event',
            ticket_ids=[ticket.id],
        )
        mock_generate.return_value = {'payme_sale_url': 'https://pay.me/x', 'transaction_id': 't1', 'raw': {}}

        from services.payme_service import generate_payme_sale_for_order

        generate_payme_sale_for_order(
            order,
            buyer_email='b@test.invalid',
            success_url='http://ok',
            failure_url='http://fail',
        )

        mock_generate.assert_called_once()
        kwargs = mock_generate.call_args.kwargs
        self.assertEqual(kwargs['amount'], Decimal('115.00'))
        self.assertIn('×2', kwargs['ticket_name'])
        self.assertEqual(kwargs['order_id'], str(order.id))
