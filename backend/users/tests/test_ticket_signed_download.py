"""Buyer receipt-email signed download must return a real file, not DRF HTML."""
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Event, Order, Ticket
from users.ticket_download_tokens import build_ticket_download_token
from users.utils.emails import _build_download_link_rows

User = get_user_model()

PDF_BYTES = b'%PDF-1.4 buyer-ticket-file\n%%EOF\n'
BROWSER_ACCEPT = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'


@override_settings(DEBUG=True, SECRET_KEY='test-secret-key-for-local', API_PUBLIC_ORIGIN='http://testserver')
class SignedTicketEmailDownloadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(
            username='email-dl-buyer',
            email='email-dl-buyer@example.test',
            password='pass',
            role='buyer',
        )
        self.seller = User.objects.create_user(
            username='email-dl-seller',
            email='email-dl-seller@example.test',
            password='pass',
            role='seller',
        )
        self.event = Event.objects.create(
            name='אייל גולן במנורה',
            date=timezone.now() + timedelta(days=5),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=Decimal('5.00'),
            asking_price=Decimal('5.00'),
            status='sold',
            available_quantity=0,
            pdf_file=SimpleUploadedFile('ticket.pdf', PDF_BYTES, content_type='application/pdf'),
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='paid',
            total_amount=Decimal('5.00'),
            total_paid_by_buyer=Decimal('5.00'),
            quantity=1,
            event_name=self.event.name,
            ticket_ids=[self.ticket.pk],
        )

    def _assert_direct_pdf(self, res):
        self.assertEqual(res.status_code, 200, res.content[:300])
        content_type = res['Content-Type']
        self.assertTrue(
            content_type.startswith('application/pdf'),
            content_type,
        )
        self.assertIn('attachment', res['Content-Disposition'])
        self.assertIn(f'ticket_{self.ticket.pk}.pdf', res['Content-Disposition'])
        self.assertTrue(res.content.startswith(b'%PDF'), res.content[:40])
        lowered = res.content.lower()
        self.assertNotIn(b'browsable', lowered)
        self.assertNotIn(b'<html', lowered)
        self.assertNotIn(b'no ticket matches the given query', lowered)

    def test_email_signed_link_downloads_sold_ticket_from_browser(self):
        rows = _build_download_link_rows(self.order)
        self.assertEqual(len(rows), 1)
        _label, absolute_url = rows[0]
        path = urlparse(absolute_url).path
        query = urlparse(absolute_url).query
        res = self.client.get(
            f'{path}?{query}',
            HTTP_ACCEPT=BROWSER_ACCEPT,
        )
        self._assert_direct_pdf(res)

    def test_paid_out_ticket_still_downloads_with_signed_token(self):
        self.ticket.status = 'paid_out'
        self.ticket.save(update_fields=['status', 'updated_at'])
        token = build_ticket_download_token(self.ticket.pk, self.order.pk)
        res = self.client.get(
            f'/api/users/tickets/{self.ticket.pk}/download_pdf/',
            {'dl': token},
            HTTP_ACCEPT=BROWSER_ACCEPT,
        )
        self._assert_direct_pdf(res)

    def test_strict_html_accept_still_returns_pdf_not_406(self):
        token = build_ticket_download_token(self.ticket.pk, self.order.pk)
        res = self.client.get(
            f'/api/users/tickets/{self.ticket.pk}/download_pdf/',
            {'dl': token},
            HTTP_ACCEPT='text/html',
        )
        self.assertNotEqual(res.status_code, 406)
        self._assert_direct_pdf(res)

    def test_anonymous_without_token_is_plain_403_not_drf_html(self):
        res = self.client.get(
            f'/api/users/tickets/{self.ticket.pk}/download_pdf/',
            HTTP_ACCEPT=BROWSER_ACCEPT,
        )
        self.assertEqual(res.status_code, 403)
        self.assertTrue(res['Content-Type'].startswith('text/plain'))
        self.assertNotIn(b'<html', res.content.lower())
        self.assertNotIn(b'Browsable', res.content)

    def test_missing_ticket_is_plain_404_not_drf_html(self):
        token = build_ticket_download_token(999999, self.order.pk)
        res = self.client.get(
            '/api/users/tickets/999999/download_pdf/',
            {'dl': token},
            HTTP_ACCEPT=BROWSER_ACCEPT,
        )
        self.assertEqual(res.status_code, 404)
        self.assertTrue(res['Content-Type'].startswith('text/plain'))
        self.assertNotIn(b'<html', res.content.lower())
        self.assertNotIn(b'No Ticket matches the given query', res.content)
