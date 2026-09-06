"""Late PayMe success webhook must override a buyer-cancelled order."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket
from users.order_cleanup import mark_pending_payment_cancelled, release_pending_payment_inventory
from users.payme_views import payme_webhook
from users.pricing import expected_buy_now_total
from users.tests.payme_ipn_test_helpers import (
    PAYME_IPN_TEST_SETTINGS,
    MockPayMeSaleConfirmMixin,
    payme_ipn_json_request,
)

User = get_user_model()


@override_settings(**{**PAYME_IPN_TEST_SETTINGS, 'DEBUG': True, 'PAYME_IS_SANDBOX': True})
class PayMeWebhookCancelledRecoverTests(MockPayMeSaleConfirmMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.seller = User.objects.create_user(
            username='cancel_race_seller',
            email='cancel-race-seller@example.test',
            password='pass-12345',
            role='seller',
        )
        self.artist = Artist.objects.create(name='Cancel Race Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Cancel Race Show',
            date=timezone.now() + timedelta(days=14),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
            status='פעיל',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file=SimpleUploadedFile('cancel-race.pdf', b'%PDF-1.4 cancel-race', content_type='application/pdf'),
            status='reserved',
            verification_status='מאומת',
            available_quantity=1,
            reservation_email='fleshnik2004@example.test',
            reserved_at=timezone.now(),
        )
        self.total = expected_buy_now_total(self.ticket.asking_price, 1)
        self.order = Order.objects.create(
            user=None,
            guest_email='fleshnik2004@example.test',
            ticket=self.ticket,
            ticket_ids=[self.ticket.id],
            status='pending_payment',
            total_amount=self.total,
            total_paid_by_buyer=self.total,
            currency='ILS',
            quantity=1,
            payme_transaction_id='SALE-CANCEL-RACE-1',
            payme_status='initialized',
            payment_confirm_token='tok-cancel-race',
            event_name=self.event.name,
        )
        self.payload = {
            'merchant_order_id': str(self.order.id),
            'payme_sale_id': 'SALE-CANCEL-RACE-1',
            'transaction_id': 'SALE-CANCEL-RACE-1',
            'sale_price': int(self.total * 100),
            'currency': 'ILS',
            'status': 'completed',
        }

    def _buyer_timeout_cancel(self):
        release_pending_payment_inventory(self.order)
        mark_pending_payment_cancelled(self.order, clear_confirm_token=False)
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
        self.assertEqual(self.ticket.status, 'active')

    def test_success_webhook_pays_cancelled_order_sells_ticket_and_emails(self):
        self._buyer_timeout_cancel()
        with patch.dict('os.environ', {'RESEND_API_KEY': ''}, clear=False):
            request, _signed, _body = payme_ipn_json_request(self.payload)
            response = payme_webhook(request)

            self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        self.assertTrue(response.data.get('finalized'), response.data)
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.payme_status, 'success')
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.ticket.status, 'sold')
        self.assertEqual(self.ticket.available_quantity, 0)
        buyer_mail = [m for m in mail.outbox if 'fleshnik2004@example.test' in m.to]
        self.assertTrue(buyer_mail, 'expected a paid-order receipt to the buyer')
        self.assertIn('TradeTix', buyer_mail[0].subject)

    def test_success_webhook_pays_expired_alias_status(self):
        self._buyer_timeout_cancel()
        self.order.status = 'expired'
        self.order.save(update_fields=['status'])
        with patch.dict('os.environ', {'RESEND_API_KEY': ''}, clear=False):
            request, _signed, _body = payme_ipn_json_request(self.payload)
            response = payme_webhook(request)
            self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        self.order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.ticket.status, 'sold')

    def test_cancelled_multi_ticket_order_pays_emails_and_zips_all_pdfs(self):
        extra = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file=SimpleUploadedFile('cancel-race-2.pdf', b'%PDF-1.4 second', content_type='application/pdf'),
            status='reserved',
            verification_status='מאומת',
            available_quantity=1,
            reservation_email='fleshnik2004@example.test',
            reserved_at=timezone.now(),
        )
        third = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file=SimpleUploadedFile('cancel-race-3.pdf', b'%PDF-1.4 third', content_type='application/pdf'),
            status='reserved',
            verification_status='מאומת',
            available_quantity=1,
            reservation_email='fleshnik2004@example.test',
            reserved_at=timezone.now(),
        )
        self.order.quantity = 3
        self.order.ticket_ids = [self.ticket.id, extra.id, third.id]
        self.order.total_amount = expected_buy_now_total(self.ticket.asking_price, 3)
        self.order.total_paid_by_buyer = self.order.total_amount
        self.order.save(update_fields=['quantity', 'ticket_ids', 'total_amount', 'total_paid_by_buyer'])
        self.payload['sale_price'] = int(self.order.total_amount * 100)
        self._buyer_timeout_cancel()

        with patch.dict('os.environ', {'RESEND_API_KEY': ''}, clear=False):
            request, _signed, _body = payme_ipn_json_request(self.payload)
            response = payme_webhook(request)
        self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertTrue(
            any('fleshnik2004@example.test' in m.to for m in mail.outbox),
            'expected buyer receipt after PayMe success',
        )

        from users.ticket_download_tokens import build_order_download_token

        token = build_order_download_token(self.order.pk)
        dl = APIClient().get(
            f'/api/users/orders/{self.order.pk}/tickets/download/',
            {'dl': token},
        )
        self.assertEqual(dl.status_code, 200, dl.content[:200])
        self.assertEqual(dl['Content-Type'], 'application/zip')
        self.assertTrue(dl.content.startswith(b'PK'))
        import zipfile
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(dl.content)) as zf:
            names = zf.namelist()
        self.assertEqual(len(names), 3)
