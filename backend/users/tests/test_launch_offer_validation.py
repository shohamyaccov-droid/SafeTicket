"""Launch readiness: offer amount validation (no zero / negative)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket

User = get_user_model()


class OfferAmountValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        self.seller = User.objects.create_user(
            username='ofseller',
            email='ofs@test.com',
            password='x',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='ofbuyer',
            email='ofb@test.com',
            password='x',
            role='buyer',
        )
        artist = Artist.objects.create(name='OA')
        ev = Event.objects.create(
            artist=artist,
            name='OA Event',
            date=timezone.now() + timedelta(days=20),
            venue='אחר',
            city='London',
            country='GB',
        )
        pdf = SimpleUploadedFile(
            't.pdf',
            b'%PDF-1.4\n1 0 obj<<>>endobj trailer<<>>\n%%EOF',
            content_type='application/pdf',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=ev,
            original_price=Decimal('50.00'),
            asking_price=Decimal('50.00'),
            pdf_file=pdf,
            status='active',
            available_quantity=1,
            verification_status='מאומת',
        )

    def test_negative_offer_rejected(self):
        self.client.force_authenticate(self.buyer)
        r = self.client.post(
            '/api/users/offers/',
            {'ticket': self.ticket.id, 'amount': '-10.00', 'quantity': 1},
            format='json',
        )
        self.assertEqual(r.status_code, 400, r.data)

    def test_zero_offer_rejected(self):
        self.client.force_authenticate(self.buyer)
        r = self.client.post(
            '/api/users/offers/',
            {'ticket': self.ticket.id, 'amount': '0', 'quantity': 1},
            format='json',
        )
        self.assertEqual(r.status_code, 400, r.data)
