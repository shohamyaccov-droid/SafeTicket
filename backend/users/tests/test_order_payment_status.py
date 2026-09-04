"""Lightweight GET /api/users/orders/<id>/status/ for PayMe return-page polling."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket

User = get_user_model()

STATUS_URL = '/api/users/orders/{}/status/'


class OrderPaymentStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='status-seller',
            email='status-seller@example.test',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='status-buyer',
            email='status-buyer@example.test',
            password='pass',
            role='buyer',
        )
        artist = Artist.objects.create(name='Status Artist')
        event = Event.objects.create(
            artist=artist,
            name='Status Show',
            date=timezone.now() + timedelta(days=10),
            venue='ישראל',
            city='תל אביב',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            status='reserved',
            available_quantity=1,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            quantity=1,
            total_amount=Decimal('107.00'),
            status='pending_payment',
            payme_status='pending',
            ticket_ids=[self.ticket.pk],
            event_name=event.name,
        )
        self.guest_order = Order.objects.create(
            user=None,
            guest_email='guest-status@example.test',
            ticket=self.ticket,
            quantity=1,
            total_amount=Decimal('107.00'),
            status='pending_payment',
            payme_status='initialized',
            ticket_ids=[self.ticket.pk],
            event_name=event.name,
        )

    def test_owner_gets_status_without_sending_email(self):
        self.client.force_authenticate(self.buyer)
        with patch('users.utils.emails.dispatch_paid_order_receipt_email') as send_mail:
            res = self.client.get(STATUS_URL.format(self.order.pk))
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['order_id'], self.order.pk)
        self.assertEqual(res.data['status'], 'pending_payment')
        self.assertEqual(res.data['payme_status'], 'pending')
        self.assertNotIn('download_token', res.data)
        send_mail.assert_not_called()

    def test_paid_status_includes_download_token(self):
        self.order.status = 'paid'
        self.order.save(update_fields=['status'])
        self.client.force_authenticate(self.buyer)
        res = self.client.get(STATUS_URL.format(self.order.pk))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('download_token'))
        self.assertEqual(res.data.get('ticket_count'), 1)

    def test_guest_with_matching_email_can_poll(self):
        with patch('users.utils.emails.send_receipt_with_pdf') as send_pdf:
            res = self.client.get(
                STATUS_URL.format(self.guest_order.pk),
                {'email': 'guest-status@example.test'},
            )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['status'], 'pending_payment')
        send_pdf.assert_not_called()

    def test_anonymous_without_email_returns_404_not_401(self):
        res = self.client.get(STATUS_URL.format(self.guest_order.pk))
        self.assertEqual(res.status_code, 404)
        self.assertNotEqual(res.status_code, 401)

    def test_stranger_cannot_read_another_buyers_order(self):
        other = User.objects.create_user(
            username='status-other',
            email='status-other@example.test',
            password='pass',
            role='buyer',
        )
        self.client.force_authenticate(other)
        res = self.client.get(STATUS_URL.format(self.order.pk))
        self.assertEqual(res.status_code, 404)

    def test_wrong_guest_email_is_404(self):
        res = self.client.get(
            STATUS_URL.format(self.guest_order.pk),
            {'email': 'not-the-buyer@example.test'},
        )
        self.assertEqual(res.status_code, 404)

    def test_pending_status_poll_reconciles_when_payme_already_captured(self):
        """Success-page poll must finalize if IPN is late but PayMe API says success."""
        self.order.payme_transaction_id = 'SALE-STATUS-POLL-1'
        self.order.payme_status = 'pending'
        self.order.save(update_fields=['payme_transaction_id', 'payme_status'])

        def _fake_finalize(order_id, **kwargs):
            Order.objects.filter(pk=order_id).update(status='paid', payme_status='success')
            return True, None, 'claimed'

        with patch(
            'services.payme_service.confirm_payme_sale_status',
            return_value={
                'ok': True,
                'found': True,
                'status': 'success',
                'raw': {'status': 'success', 'payme_sale_id': 'SALE-STATUS-POLL-1'},
            },
        ) as mock_confirm, patch(
            'users.payments.finalize_payme_webhook_once',
            side_effect=_fake_finalize,
        ) as mock_finalize:
            self.client.force_authenticate(self.buyer)
            res = self.client.get(STATUS_URL.format(self.order.pk))

        self.assertEqual(res.status_code, 200, res.content)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(res.data['status'], 'paid')
        self.assertTrue(res.data.get('download_token'))
        mock_confirm.assert_called()
        mock_finalize.assert_called()
