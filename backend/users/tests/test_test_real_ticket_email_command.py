"""python manage.py test_real_ticket_email — signed PDF receipt to a forced recipient."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from users.models import Artist, Event, Order, Ticket

User = get_user_model()

PDF_BYTES = b'%PDF-1.4 test-real-ticket\n%%EOF\n'
RECIPIENT = 'shohamyaccov@gmail.com'


@override_settings(API_PUBLIC_ORIGIN='https://api.example.test')
class TestRealTicketEmailCommandTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            username='real-email-seller',
            email='real-email-seller@example.test',
            password='pass',
            role='seller',
        )
        artist = Artist.objects.create(name='Real Email Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Real Email Show',
            date=timezone.now() + timedelta(days=12),
            venue='ישראל',
            city='תל אביב',
            country='IL',
        )

    def _paid_order_with_pdf(self):
        ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('80'),
            asking_price=Decimal('80'),
            status='sold',
            available_quantity=0,
            pdf_file=SimpleUploadedFile('ticket.pdf', PDF_BYTES, content_type='application/pdf'),
        )
        return Order.objects.create(
            user=None,
            guest_email='buyer@example.test',
            ticket=ticket,
            status='paid',
            quantity=1,
            total_amount=Decimal('80.00'),
            ticket_ids=[ticket.pk],
            event_name=self.event.name,
        )

    def test_uses_latest_paid_order_and_forces_recipient(self):
        older = self._paid_order_with_pdf()
        newer = self._paid_order_with_pdf()
        self.assertGreater(newer.pk, older.pk)

        with patch('users.management.commands.test_real_ticket_email.send_receipt_with_pdf') as send:
            out = StringIO()
            call_command('test_real_ticket_email', stdout=out)

        send.assert_called_once()
        recipient, order = send.call_args.args[:2]
        self.assertEqual(recipient, RECIPIENT)
        self.assertEqual(order.pk, newer.pk)
        self.assertIn(f'order #{newer.pk}', out.getvalue())
        self.assertIn(f'ticket #{newer.ticket_id}', out.getvalue())
        self.assertIn('/download_pdf/?dl=', out.getvalue())

    def test_creates_dummy_ticket_and_order_when_none_exist(self):
        Order.objects.filter(status='paid').update(ticket=None, ticket_ids=[])

        with patch('users.management.commands.test_real_ticket_email.send_receipt_with_pdf') as send:
            call_command('test_real_ticket_email')

        send.assert_called_once()
        recipient, order = send.call_args.args[:2]
        self.assertEqual(recipient, RECIPIENT)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertIsNotNone(order.ticket_id)
        self.assertTrue(order.ticket.pdf_file)
        self.assertTrue(order.ticket.pdf_file.read().startswith(b'%PDF'))
        self.assertEqual(order.ticket_ids, [order.ticket_id])
        self.assertEqual(order.guest_email, RECIPIENT)
