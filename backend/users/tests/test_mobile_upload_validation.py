"""
Mobile ticket upload validation QA.

Exercises the same multipart endpoint the mobile/web UI uses and verifies that
bad files receive explicit error messages instead of silent failures.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket

User = get_user_model()
UPLOAD_URL = '/api/users/tickets/'


def _pdf_file(name='mobile-ticket.pdf', content_type='application/pdf', content=None):
    return SimpleUploadedFile(
        name,
        content or b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
        content_type=content_type,
    )


def _jpg_file(name='mobile-ticket.jpg'):
    return SimpleUploadedFile(
        name,
        b'\xff\xd8\xff\xe0' + b'JFIF\x00' + b'\x00' * 64 + b'\xff\xd9',
        content_type='image/jpeg',
    )


def _png_file(name='mobile-ticket.png'):
    return SimpleUploadedFile(
        name,
        b'\x89PNG\r\n\x1a\n' + b'\x00' * 64,
        content_type='image/png',
    )


@override_settings(DEBUG=True, SECRET_KEY='upload-validation-secret')
class MobileTicketUploadValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='mobile_upload_seller',
            email='mobile_upload_seller@example.test',
            password='test-pass-123',
            role='seller',
            is_email_verified=True,
        )
        self.artist = Artist.objects.create(name='Mobile Upload Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Mobile Upload Event',
            date=timezone.now() + timedelta(days=21),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
        )
        self.client.force_authenticate(self.seller)

    def _upload_payload(self, upload):
        return {
            'event_id': str(self.event.id),
            'original_price': '120.00',
            'available_quantity': '1',
            'pdf_files_count': '1',
            'il_legal_declaration': 'true',
            'pdf_file_0': upload,
        }

    def _assert_upload_success(self, upload, expected_suffix):
        before = Ticket.objects.count()
        res = self.client.post(UPLOAD_URL, self._upload_payload(upload), format='multipart')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(Ticket.objects.count(), before + 1)
        ticket = Ticket.objects.latest('id')
        self.assertEqual(ticket.seller_id, self.seller.id)
        self.assertTrue(ticket.pdf_file.name.lower().endswith(expected_suffix))
        self.assertEqual(ticket.available_quantity, 1)

    def test_mobile_upload_accepts_pdf_jpg_and_png_ticket_files(self):
        self._assert_upload_success(_pdf_file(), '.pdf')
        self._assert_upload_success(_jpg_file(), '.jpg')
        self._assert_upload_success(_png_file(), '.png')

    def test_mobile_upload_rejects_invalid_file_type_with_clear_message(self):
        res = self.client.post(
            UPLOAD_URL,
            self._upload_payload(
                SimpleUploadedFile('ticket.txt', b'not a ticket file', content_type='text/plain')
            ),
            format='multipart',
        )
        self.assertEqual(res.status_code, 400, res.content)
        message = str(res.data.get('error', ''))
        self.assertIn('סוג קובץ לא חוקי', message)
        self.assertIn('PDF, JPG או PNG', message)

    def test_mobile_upload_rejects_oversized_file_with_clear_message(self):
        oversized = _pdf_file(
            name='huge-ticket.pdf',
            content=b'%PDF-1.4\n' + (b'0' * ((5 * 1024 * 1024) + 1)),
        )
        res = self.client.post(UPLOAD_URL, self._upload_payload(oversized), format='multipart')
        self.assertEqual(res.status_code, 400, res.content)
        message = str(res.data.get('error', ''))
        self.assertIn('קובץ גדול מדי', message)
        self.assertIn('5MB', message)
