"""Buyer ticket/receipt email after PayMe marks an order paid."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from users.admin import OrderAdmin
from users.models import Artist, Event, Order, Ticket
from users.payments import finalize_pending_order_to_paid
from users.utils.emails import buyer_deliverable_email, dispatch_paid_order_receipt_email

User = get_user_model()


class PaidOrderReceiptEmailTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='receipt-seller',
            email='seller-receipt@example.test',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='receipt-buyer',
            email='buyer-receipt@example.test',
            password='pass',
            role='buyer',
        )
        artist = Artist.objects.create(name='Receipt Artist')
        event = Event.objects.create(
            artist=artist,
            name='Receipt Show',
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
            reserved_by=self.buyer,
            reserved_at=timezone.now(),
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            quantity=1,
            total_amount=Decimal('107.00'),
            status='pending_payment',
            ticket_ids=[self.ticket.pk],
            event_name=event.name,
        )

    def test_buyer_deliverable_email_prefers_registered_user(self):
        self.assertEqual(buyer_deliverable_email(self.order), 'buyer-receipt@example.test')

    def test_finalize_to_paid_sends_receipt_immediately(self):
        with patch('users.utils.emails.send_receipt_with_pdf') as mock_send:
            ok, err = finalize_pending_order_to_paid(self.order.pk, source='payme_webhook')
        self.assertTrue(ok, err)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        mock_send.assert_called_once()
        args, _kwargs = mock_send.call_args
        self.assertEqual(args[0], 'buyer-receipt@example.test')
        self.assertEqual(args[1].pk, self.order.pk)

    def test_receipt_failure_does_not_unpay_the_order(self):
        with patch('users.utils.emails.send_receipt_with_pdf', side_effect=RuntimeError('smtp down')):
            ok, err = finalize_pending_order_to_paid(self.order.pk, source='payme_webhook')
        self.assertTrue(ok, err)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_dispatch_sends_via_django_when_resend_key_missing(self):
        self.order.status = 'paid'
        self.order.save(update_fields=['status'])
        with patch.dict('os.environ', {'RESEND_API_KEY': ''}, clear=False):
            ok = dispatch_paid_order_receipt_email(self.order, source='test')
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('buyer-receipt@example.test', mail.outbox[0].to)
        self.assertIn('הקבלה והכרטיסים', mail.outbox[0].subject)


def _attach_messages(request):
    setattr(request, 'session', {})
    setattr(request, '_messages', FallbackStorage(request))


class ResendTicketEmailAdminActionTests(TestCase):
    def setUp(self):
        self.admin = OrderAdmin(Order, AdminSite())
        self.factory = RequestFactory()
        self.staff = User.objects.create_superuser(
            username='admin-resend-email',
            email='admin-resend@example.test',
            password='x',
        )
        seller = User.objects.create_user(
            username='resend-seller',
            email='resend-seller@example.test',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='resend-buyer',
            email='resend-buyer@example.test',
            password='pass',
            role='buyer',
        )
        artist = Artist.objects.create(name='Resend Artist')
        event = Event.objects.create(
            artist=artist,
            name='Resend Show',
            date=timezone.now() + timedelta(days=10),
            venue='ישראל',
            city='תל אביב',
            country='IL',
        )
        ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            status='sold',
            available_quantity=0,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=ticket,
            quantity=1,
            total_amount=Decimal('107.00'),
            status='paid',
            ticket_ids=[ticket.pk],
            event_name=event.name,
        )

    def test_action_is_registered_as_resend_ticket_email(self):
        self.assertIn('resend_ticket_email', OrderAdmin.actions)
        self.assertEqual(OrderAdmin.resend_ticket_email.short_description, 'Resend Ticket Email')

    def test_resend_shows_success_message(self):
        request = self.factory.post('/admin/users/order/')
        request.user = self.staff
        _attach_messages(request)
        with patch('users.utils.emails.send_receipt_with_pdf') as mock_send:
            self.admin.resend_ticket_email(request, Order.objects.filter(pk=self.order.pk))
        mock_send.assert_called_once()
        texts = [str(m) for m in request._messages]
        self.assertTrue(any('Email sent successfully' in t for t in texts), texts)

    def test_resend_shows_smtp_error_in_admin(self):
        request = self.factory.post('/admin/users/order/')
        request.user = self.staff
        _attach_messages(request)
        with patch(
            'users.utils.emails.send_receipt_with_pdf',
            side_effect=RuntimeError('SMTP AUTH failed'),
        ):
            self.admin.resend_ticket_email(request, Order.objects.filter(pk=self.order.pk))
        texts = [str(m) for m in request._messages]
        self.assertTrue(any('SMTP AUTH failed' in t for t in texts), texts)

    def test_resend_rejects_unpaid_order(self):
        self.order.status = 'pending_payment'
        self.order.save(update_fields=['status'])
        request = self.factory.post('/admin/users/order/')
        request.user = self.staff
        _attach_messages(request)
        with patch('users.utils.emails.send_receipt_with_pdf') as mock_send:
            self.admin.resend_ticket_email(request, Order.objects.filter(pk=self.order.pk))
        mock_send.assert_not_called()
        texts = [str(m) for m in request._messages]
        self.assertTrue(any('pending_payment' in t for t in texts), texts)
