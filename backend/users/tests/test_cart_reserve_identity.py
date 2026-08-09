"""Cart reserve must bind to buyer identity so mobile can reclaim/release locks."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket

User = get_user_model()


class CartReserveIdentityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='cart_seller',
            email='cart_seller@test.com',
            password='Pass12345!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='cart_buyer',
            email='cart_buyer@test.com',
            password='Pass12345!',
            role='buyer',
        )
        artist = Artist.objects.create(name='Cart Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Cart Event',
            date=timezone.now() + timedelta(days=14),
            venue='Hall',
            city='Tel Aviv',
            country='IL',
        )

    def _ticket(self, **kwargs):
        defaults = dict(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('120.00'),
            asking_price=Decimal('120.00'),
            pdf_file='tickets/pdfs/cart.pdf',
            status='active',
            verification_status='מאומת',
            available_quantity=1,
        )
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def test_anonymous_reserve_requires_email(self):
        ticket = self._ticket()
        res = self.client.post(f'/api/users/tickets/{ticket.id}/reserve/', {}, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertEqual(res.data.get('code'), 'guest_email_required')
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')

    def test_same_buyer_can_rereserve_after_orphan_style_second_call(self):
        """Simulate desktop→mobile: second reserve by same auth must succeed."""
        ticket = self._ticket()
        self.client.force_authenticate(self.buyer)
        first = self.client.post(f'/api/users/tickets/{ticket.id}/reserve/', {'quantity': 1}, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        second = self.client.post(f'/api/users/tickets/{ticket.id}/reserve/', {'quantity': 1}, format='json')
        self.assertEqual(second.status_code, 200, second.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertEqual(ticket.reserved_by_id, self.buyer.id)

    def test_listing_group_foreign_hold_returns_held_by_other(self):
        group_id = str(uuid4())
        a = self._ticket(listing_group_id=group_id)
        self._ticket(listing_group_id=group_id)
        other = User.objects.create_user(
            username='cart_other',
            email='cart_other@test.com',
            password='Pass12345!',
            role='buyer',
        )
        self.client.force_authenticate(other)
        lock = self.client.post(
            f'/api/users/tickets/{a.id}/reserve/',
            {'listing_group_id': group_id, 'quantity': 2},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)

        self.client.force_authenticate(self.buyer)
        blocked = self.client.post(
            f'/api/users/tickets/{a.id}/reserve/',
            {'listing_group_id': group_id, 'quantity': 1},
            format='json',
        )
        self.assertEqual(blocked.status_code, 400, blocked.data)
        self.assertEqual(blocked.data.get('code'), 'held_by_other')

    def test_release_clears_all_listing_group_seats_for_buyer(self):
        group_id = str(uuid4())
        a = self._ticket(listing_group_id=group_id)
        b = self._ticket(listing_group_id=group_id)
        self.client.force_authenticate(self.buyer)
        lock = self.client.post(
            f'/api/users/tickets/{a.id}/reserve/',
            {'listing_group_id': group_id, 'quantity': 2},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        release = self.client.post(f'/api/users/tickets/{a.id}/release_reservation/', {}, format='json')
        self.assertEqual(release.status_code, 200, release.data)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.status, 'active')
        self.assertEqual(b.status, 'active')
        self.assertIsNone(a.reserved_by_id)
        self.assertIsNone(b.reserved_by_id)

    def test_release_is_idempotent_when_already_active(self):
        ticket = self._ticket()
        self.client.force_authenticate(self.buyer)
        release = self.client.post(
            f'/api/users/tickets/{ticket.id}/release_reservation/',
            {},
            format='json',
        )
        self.assertEqual(release.status_code, 200, release.data)
        self.assertTrue(release.data.get('success'))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')

    def test_release_after_reserve_unlocks_immediately(self):
        ticket = self._ticket()
        self.client.force_authenticate(self.buyer)
        lock = self.client.post(f'/api/users/tickets/{ticket.id}/reserve/', {'quantity': 1}, format='json')
        self.assertEqual(lock.status_code, 200, lock.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        release = self.client.post(
            f'/api/users/tickets/{ticket.id}/release_reservation/',
            {},
            format='json',
        )
        self.assertEqual(release.status_code, 200, release.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_at)
        self.assertIsNone(ticket.reserved_by_id)
