"""Tests for allow_negotiation and max-2 offer limit."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Offer, Ticket

User = get_user_model()


class NegotiationControlTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='neg_seller',
            email='neg_seller@test.com',
            password='Pass12345!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='neg_buyer',
            email='neg_buyer@test.com',
            password='Pass12345!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Neg Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Neg Event',
            date=timezone.now() + timedelta(days=30),
            venue='Test Venue',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            seat_row='A',
            original_price=Decimal('100.00'),
            asking_price=Decimal('120.00'),
            available_quantity=2,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/neg-test.pdf',
            allow_negotiation=True,
            listing_group_id='neg-group-1',
        )

    def _offer(self, amount='90.00'):
        self.client.force_authenticate(self.buyer)
        return self.client.post(
            '/api/users/offers/',
            {'ticket': self.ticket.pk, 'amount': amount, 'quantity': 1},
            format='json',
        )

    def test_offer_rejected_when_negotiation_disabled(self):
        self.ticket.allow_negotiation = False
        self.ticket.save(update_fields=['allow_negotiation'])
        res = self._offer()
        self.assertEqual(res.status_code, 400, res.content)

    def test_max_two_pending_or_rejected_offers(self):
        r1 = self._offer('90.00')
        self.assertEqual(r1.status_code, 201, r1.content)
        Offer.objects.filter(buyer=self.buyer, ticket=self.ticket).update(
            status='rejected',
            created_at=timezone.now() - timedelta(minutes=1),
        )
        r2 = self._offer('85.00')
        self.assertEqual(r2.status_code, 201, r2.content)
        Offer.objects.filter(buyer=self.buyer, ticket=self.ticket, status='pending').update(
            status='rejected',
            created_at=timezone.now() - timedelta(minutes=1),
        )
        r3 = self._offer('80.00')
        self.assertEqual(r3.status_code, 400, r3.content)
        self.assertEqual(
            Offer.objects.filter(
                buyer=self.buyer,
                ticket__listing_group_id='neg-group-1',
                offer_round_count=0,
                status__in=['pending', 'rejected'],
            ).count(),
            2,
        )

    def test_list_serializer_exposes_allow_negotiation(self):
        self.client.force_authenticate(None)
        res = self.client.get(f'/api/users/events/{self.event.pk}/tickets/')
        self.assertEqual(res.status_code, 200, res.content)
        rows = res.data if isinstance(res.data, list) else res.data.get('results') or []
        mine = next((t for t in rows if t.get('id') == self.ticket.pk), None)
        self.assertIsNotNone(mine)
        self.assertTrue(mine.get('allow_negotiation'))
