"""
Payme webhook → order finalization (mocked HTTP to Payme init is optional).
Run: cd backend && python manage.py test tests.test_payme_flow -v 2
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket

User = get_user_model()


@override_settings(
    PAYME_API_KEY='test_key',
    PAYME_MERCHANT_ID='test_merchant',
    PAYME_WEBHOOK_SECRET='',
)
class PaymeWebhookFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        future = timezone.now() + timedelta(days=30)
        self.seller = User.objects.create_user(
            username='payme_seller',
            email='payme_seller@test.invalid',
            password='x',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='payme_buyer',
            email='payme_buyer@test.invalid',
            password='x',
            role='buyer',
        )
        artist = Artist.objects.create(name='Payme Artist')
        self.event = Event.objects.create(
            name='Payme Event',
            artist=artist,
            date=future,
            venue='מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        pdf = SimpleUploadedFile('t.pdf', b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n', content_type='application/pdf')
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=1,
            status='reserved',
            reserved_by=self.buyer,
            reserved_at=timezone.now(),
            pdf_file=pdf,
            verification_status='מאומת',
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='pending_payment',
            total_amount=Decimal('110.00'),
            currency='ILS',
            quantity=1,
            event_name=self.event.name,
            ticket_ids=[self.ticket.id],
            guest_email=None,
        )

    @patch('users.payme_views.post_generate_sale')
    def test_payme_init_returns_redirect(self, mock_post):
        mock_post.return_value = (
            200,
            {'redirect_url': 'https://testpay.payme.io/hosted/test', 'transaction_id': 'txn_123'},
        )
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            '/api/users/payments/payme/init/',
            {
                'order_id': self.order.id,
                'success_url': 'http://localhost:5173/checkout/success',
                'failure_url': 'http://localhost:5173/checkout/failure',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIn('redirect_url', res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payme_transaction_id, 'txn_123')

    def test_webhook_marks_paid_via_finalize(self):
        """Webhook success + merchant_order_id runs finalize (inventory + paid)."""
        payload = {
            'merchant_order_id': str(self.order.id),
            'status': 'success',
            'transaction_id': 'webhook_txn_1',
        }
        res = self.client.post('/api/payments/webhook/', payload, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertTrue(res.data.get('finalized'), res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.payme_status, 'success')
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'sold')
