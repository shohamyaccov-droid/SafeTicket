from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket, Venue, VenueSection


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
            first_name='נועה',
            last_name='לוי',
            phone_number='0501234567',
        )
        artist = Artist.objects.create(name='Admin Files Artist')
        venue = Venue.objects.create(name='Admin Files Venue', city='Tel Aviv')
        self.section = VenueSection.objects.create(venue=venue, name='Block 12')
        event = Event.objects.create(
            artist=artist,
            name='Admin Files Show',
            date=timezone.now(),
            venue='Arena',
            venue_place=venue,
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
            venue_section=self.section,
            row='7',
            seat_numbers='22',
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
        self.assertEqual(ticket['section'], 'Block 12')
        self.assertEqual(ticket['row'], '7')
        self.assertEqual(ticket['seat_numbers'], '22')
        self.assertEqual(ticket['seller_full_name'], 'נועה לוי')
        self.assertEqual(ticket['seller_email'], 'seller-files@example.com')
        self.assertEqual(ticket['seller_phone'], '0501234567')
        self.assertEqual(ticket['seller_phone_number'], '0501234567')
        self.assertEqual(ticket['seller_contact']['full_name'], 'נועה לוי')
        self.assertEqual(ticket['seller_contact']['email'], 'seller-files@example.com')
        self.assertEqual(ticket['seller_contact']['phone_number'], '0501234567')

    @patch('users.notifications.notify_ticket_approved')
    def test_approve_ticket_triggers_seller_email_notification(self, mock_notify):
        self.client.force_authenticate(self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/users/admin/tickets/{self.ticket.id}/approve/', {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'active')
        mock_notify.assert_called_once()
        self.assertEqual(mock_notify.call_args.args[0].id, self.ticket.id)

    def test_admin_can_save_section_and_row_without_approving(self):
        self.client.force_authenticate(self.admin)
        blank = Ticket.objects.create(
            seller=self.seller,
            event=self.ticket.event,
            original_price=Decimal('90'),
            asking_price=Decimal('90'),
            pdf_file='tickets/pdfs/ga-pending.pdf',
            status='pending_approval',
            verification_status='ממתין לאישור',
            available_quantity=1,
        )
        response = self.client.post(
            f'/api/users/admin/tickets/{blank.id}/seating/',
            {'section': 'דשא', 'row': '3'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        blank.refresh_from_db()
        self.assertEqual(blank.status, 'pending_approval')
        self.assertEqual(blank.custom_section_text, 'דשא')
        self.assertEqual(blank.get_section_display(), 'דשא')
        self.assertEqual(blank.row, '3')
        self.assertEqual(blank.row_number, '3')
        self.assertEqual(response.data['ticket']['section'], 'דשא')
        self.assertEqual(response.data['ticket']['row'], '3')

    def test_admin_seating_matches_structured_venue_section(self):
        self.client.force_authenticate(self.admin)
        blank = Ticket.objects.create(
            seller=self.seller,
            event=self.ticket.event,
            original_price=Decimal('70'),
            asking_price=Decimal('70'),
            pdf_file='tickets/pdfs/ga-block.pdf',
            status='pending_approval',
            verification_status='ממתין לאישור',
            available_quantity=1,
        )
        response = self.client.post(
            f'/api/users/admin/tickets/{blank.id}/seating/',
            {'section': 'Block 12', 'row': '7'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        blank.refresh_from_db()
        self.assertEqual(blank.venue_section_id, self.section.id)
        self.assertEqual((blank.custom_section_text or '').strip(), '')
        self.assertEqual(blank.get_section_display(), 'Block 12')
        self.assertEqual(blank.row, '7')

    def test_approve_persists_section_and_row_from_request_body(self):
        self.client.force_authenticate(self.admin)
        blank = Ticket.objects.create(
            seller=self.seller,
            event=self.ticket.event,
            original_price=Decimal('80'),
            asking_price=Decimal('80'),
            pdf_file='tickets/pdfs/ga-approve.pdf',
            status='pending_approval',
            verification_status='ממתין לאישור',
            available_quantity=1,
        )
        response = self.client.post(
            f'/api/users/admin/tickets/{blank.id}/approve/',
            {'section': '14', 'row': '8'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        blank.refresh_from_db()
        self.assertEqual(blank.status, 'active')
        self.assertEqual(blank.get_section_display(), '14')
        self.assertEqual(blank.row, '8')
        self.assertEqual(blank.row_number, '8')
