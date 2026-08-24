"""Listing must work without bank details; payouts stay a later profile step."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket

User = get_user_model()
UPLOAD_URL = '/api/users/tickets/'


def _pdf_file():
    return SimpleUploadedFile(
        'listing-ticket.pdf',
        b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n',
        content_type='application/pdf',
    )


@override_settings(DEBUG=True, SECRET_KEY='listing-without-bank-secret')
class ListingWithoutBankDetailsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(
            username='guest-lister',
            email='guest-lister@example.test',
            password='test-pass-123',
            role='buyer',
            is_email_verified=True,
        )
        self.artist = Artist.objects.create(name='Listing Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Listing Event',
            date=timezone.now() + timedelta(days=21),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
        )

    def test_buyer_can_create_listing_without_bank_and_becomes_seller(self):
        self.client.force_authenticate(self.buyer)
        payload = {
            'event_id': str(self.event.id),
            'original_price': '90.00',
            'listing_price': '90',
            'available_quantity': '1',
            'pdf_files_count': '1',
            'il_legal_declaration': 'true',
            'pdf_file_0': _pdf_file(),
        }
        res = self.client.post(UPLOAD_URL, payload, format='multipart')
        self.assertEqual(res.status_code, 201, res.content)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.role, 'seller')
        self.assertFalse(self.buyer.has_payout_details)
        ticket = Ticket.objects.latest('id')
        self.assertEqual(ticket.seller_id, self.buyer.id)
        wallet = self.client.get('/api/users/me/wallet/')
        self.assertEqual(wallet.status_code, 200)
        self.assertTrue(wallet.data['needs_payout_details'])
