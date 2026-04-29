from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket


User = get_user_model()


class AdminPendingTicketFileUrlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin-files',
            email='admin-files@example.com',
            password='pass',
            is_staff=True,
        )
        self.seller = User.objects.create_user(
            username='seller-files',
            email='seller-files@example.com',
            password='pass',
            role='seller',
        )
        artist = Artist.objects.create(name='Admin Files Artist')
        event = Event.objects.create(
            artist=artist,
            name='Admin Files Show',
            date=timezone.now(),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            pdf_file='tickets/pdfs/admin-file.pdf',
            receipt_file='tickets/receipts/admin-receipt.pdf',
            status='pending_approval',
            verification_status='ממתין לאישור',
            available_quantity=1,
        )

    @patch('users.admin_pdf_url.get_ticket_pdf_admin_url', return_value='https://signed.example/ticket.pdf')
    @patch('users.admin_pdf_url.get_ticket_receipt_admin_url', return_value='https://signed.example/receipt.pdf')
    def test_staff_pending_tickets_include_signed_file_urls(self, _receipt_url, _pdf_url):
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/users/admin/pending-tickets/')

        self.assertEqual(response.status_code, 200)
        ticket = next(t for t in response.data['tickets'] if t['id'] == self.ticket.id)
        self.assertEqual(ticket['id'], self.ticket.id)
        self.assertEqual(ticket['ticket_file_url'], 'https://signed.example/ticket.pdf')
        self.assertEqual(ticket['receipt_file_url'], 'https://signed.example/receipt.pdf')
