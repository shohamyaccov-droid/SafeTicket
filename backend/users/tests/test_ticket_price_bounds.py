"""Reject non-positive listing / face prices on ticket create."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event

User = get_user_model()


class TicketPriceBoundsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='price_seller',
            email='price_seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        self.client.force_authenticate(user=self.seller)
        artist = Artist.objects.create(name='Price Bound Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Price Bound Show',
            date=timezone.now() + timedelta(days=40),
            venue='היכל מנורה מבטחים',
            city='תל אביב',
            country='IL',
            category='concert',
            status='פעיל',
        )

    def _pdf(self, name='t.pdf'):
        return SimpleUploadedFile(name, b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n', content_type='application/pdf')

    def test_negative_listing_price_rejected(self):
        res = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '-10',
                'listing_price': '-10',
                'available_quantity': 1,
                'pdf_files_count': 1,
                'pdf_file_0': self._pdf(),
                'il_legal_declaration': 'true',
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 400)

    def test_zero_listing_price_rejected(self):
        res = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '0',
                'listing_price': '0',
                'available_quantity': 1,
                'pdf_files_count': 1,
                'pdf_file_0': self._pdf('z.pdf'),
                'il_legal_declaration': 'true',
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 400)
