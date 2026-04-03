"""
Hybrid seating (Venue / VenueSection) + ticket listing; email must not 500 listing creation.

Run:
  cd backend && python manage.py test users.tests.test_hybrid_seating_listing_email_resilience -v 2
"""
from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket, Venue, VenueSection

User = get_user_model()


def _pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


class HybridSeatingListingEmailResilienceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        future = timezone.now() + timedelta(days=60)
        self.artist = Artist.objects.create(name='Seating QA Artist')
        self.venue = Venue.objects.create(name='QA Arena', city='Tel Aviv')
        self.sec_a = VenueSection.objects.create(venue=self.venue, name='Gate A')
        VenueSection.objects.create(venue=self.venue, name='Gate B')
        self.event_structured = Event.objects.create(
            name='Structured Venue Event',
            artist=self.artist,
            date=future,
            venue='אחר',
            venue_place=self.venue,
            city='Tel Aviv',
            country='US',
        )
        self.event_plain = Event.objects.create(
            name='Plain Text Venue Event',
            artist=self.artist,
            date=future,
            venue='אחר',
            city='New York',
            country='US',
        )
        self.seller = User.objects.create_user(
            username='qa_seating_seller',
            password='pass',
            email='seller@seating.test',
            role='seller',
        )

    def test_event_detail_includes_venue_detail_and_sections(self):
        r = self.client.get(f'/api/users/events/{self.event_structured.id}/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r.content))
        self.assertIn('venue_detail', r.data)
        self.assertEqual(r.data['venue_detail']['id'], self.venue.id)
        self.assertEqual(r.data['venue_detail']['name'], self.venue.name)
        names = {s['name'] for s in r.data['venue_detail']['sections']}
        self.assertEqual(names, {'Gate A', 'Gate B'})

    def test_plain_event_has_null_venue_detail(self):
        r = self.client.get(f'/api/users/events/{self.event_plain.id}/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data.get('venue_detail'))

    def test_list_ticket_structured_section_persists_fk(self):
        b = _pdf_bytes()
        pdf = SimpleUploadedFile('t.pdf', b, content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event_structured.id,
                'original_price': '80',
                'listing_price': '100',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'venue_section': str(self.sec_a.id),
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', r.content))
        t = Ticket.objects.get(pk=r.data['id'])
        self.assertEqual(t.venue_section_id, self.sec_a.id)
        self.assertFalse((t.custom_section_text or '').strip())
        self.assertEqual(t.get_section_display(), 'Gate A')

    def test_list_ticket_free_text_section(self):
        b = _pdf_bytes()
        pdf = SimpleUploadedFile('t.pdf', b, content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event_plain.id,
                'original_price': '80',
                'listing_price': '100',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'custom_section_text': 'Terrace 9',
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', r.content))
        t = Ticket.objects.get(pk=r.data['id'])
        self.assertEqual(t.custom_section_text, 'Terrace 9')
        self.assertIsNone(t.venue_section_id)
        self.assertEqual(t.get_section_display(), 'Terrace 9')

    @mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=OSError('SMTP failure'))
    def test_ticket_creation_succeeds_when_mailer_raises(self, _mock_send):
        b = _pdf_bytes()
        pdf = SimpleUploadedFile('t.pdf', b, content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event_plain.id,
                'original_price': '50',
                'listing_price': '50',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
                'section': 'Legacy multipart section field',
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 201, getattr(r, 'data', r.content))
        self.assertTrue(Ticket.objects.filter(pk=r.data['id']).exists())
        t = Ticket.objects.get(pk=r.data['id'])
        self.assertIn('Legacy', t.get_section_display())

    def test_send_notification_does_not_propagate_smtp_errors(self):
        from users.notifications import _send_notification

        with mock.patch(
            'django.core.mail.EmailMultiAlternatives.send',
            side_effect=OSError('SMTP failure'),
        ):
            _send_notification(
                'TradeTix test',
                'offer_new',
                'buyer@example.com',
                {
                    'event_name': 'X',
                    'amount_display': '$1',
                    'currency_code': 'USD',
                    'counterparty_name': 'a',
                    'offer_id': 1,
                },
            )
