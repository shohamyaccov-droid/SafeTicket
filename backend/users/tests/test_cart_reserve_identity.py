"""Cart reserve must bind to buyer identity so mobile can reclaim/release locks."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket
from users.cart_identity import (
    anonymous_reservation_matches,
    cart_token_email,
    stored_anonymous_reservation_email,
)

User = get_user_model()


class CartIdentityHelperTests(TestCase):
    def test_prefers_real_email_over_cart_token(self):
        token = 'd' * 32
        self.assertEqual(
            stored_anonymous_reservation_email(guest_email='buyer@example.com', cart_token=token),
            'buyer@example.com',
        )
        self.assertTrue(
            anonymous_reservation_matches(
                cart_token_email(token),
                guest_email='buyer@example.com',
                cart_token=token,
            )
        )


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

    def test_anonymous_reserve_with_cart_token_locks_without_email(self):
        ticket = self._ticket()
        token = 'a' * 32
        res = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'cart_token': token, 'quantity': 1},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertTrue((ticket.reservation_email or '').endswith('@cart.tradetix.invalid'))

    def test_anonymous_release_with_cart_token_unlocks_immediately(self):
        ticket = self._ticket()
        token = 'b' * 32
        lock = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'cart_token': token, 'quantity': 1},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        release = self.client.post(
            f'/api/users/tickets/{ticket.id}/release_reservation/',
            {'cart_token': token},
            format='json',
        )
        self.assertEqual(release.status_code, 200, release.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_at)
        self.assertIsNone(ticket.reservation_email)

    def test_cart_token_hold_can_be_claimed_with_real_email(self):
        ticket = self._ticket()
        token = 'c' * 32
        lock = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'cart_token': token, 'quantity': 1},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        claim = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'cart_token': token, 'email': 'buyer@example.com', 'quantity': 1},
            format='json',
        )
        self.assertEqual(claim.status_code, 200, claim.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertEqual(ticket.reservation_email, 'buyer@example.com')

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

    def test_event_tickets_include_reserved_lock_fields(self):
        ticket = self._ticket()
        token = 'e' * 32
        lock = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'cart_token': token, 'quantity': 1},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        listing = self.client.get(f'/api/users/events/{self.event.pk}/tickets/')
        self.assertEqual(listing.status_code, 200, listing.data)
        rows = listing.data if isinstance(listing.data, list) else listing.data.get('results') or listing.data
        row = next((t for t in rows if t['id'] == ticket.id), None)
        self.assertIsNotNone(row)
        self.assertTrue(row.get('is_locked'))
        self.assertTrue(row.get('locked_until'))
        self.assertEqual(row.get('status'), 'reserved')

    def test_unlock_alias_releases_hold(self):
        ticket = self._ticket()
        token = 'f' * 32
        lock = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'cart_token': token, 'quantity': 1},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        unlock = self.client.post(
            f'/api/users/tickets/{ticket.id}/unlock/',
            {'cart_token': token},
            format='json',
        )
        self.assertEqual(unlock.status_code, 200, unlock.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_at)
        self.assertIsNone(ticket.reservation_email)

    def test_authenticated_reserve_can_unlock_anonymously_with_cart_token(self):
        """Tab-close sendBeacon has no Bearer — cart_token must still release the hold."""
        ticket = self._ticket()
        token = 'aa' * 16
        self.client.force_authenticate(self.buyer)
        lock = self.client.post(
            f'/api/users/tickets/{ticket.id}/reserve/',
            {'quantity': 1, 'cart_token': token},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')
        self.assertTrue((ticket.reservation_email or '').endswith('@cart.tradetix.invalid'))

        self.client.force_authenticate(None)
        unlock = self.client.post(
            f'/api/users/tickets/{ticket.id}/unlock/',
            {'cart_token': token},
            format='json',
        )
        self.assertEqual(unlock.status_code, 200, unlock.data)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'active')
        self.assertIsNone(ticket.reserved_by_id)
        self.assertIsNone(ticket.reservation_email)

    def test_partially_sold_listing_group_can_reserve_remaining_seats(self):
        group_id = str(uuid4())
        sold_a = self._ticket(listing_group_id=group_id, status='sold', available_quantity=0)
        sold_b = self._ticket(listing_group_id=group_id, status='sold', available_quantity=0)
        live_a = self._ticket(listing_group_id=group_id)
        live_b = self._ticket(listing_group_id=group_id)
        self.client.force_authenticate(self.buyer)
        lock = self.client.post(
            f'/api/users/tickets/{sold_a.id}/reserve/',
            {'listing_group_id': group_id, 'quantity': 2},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        self.assertEqual(lock.data.get('quantity'), 2)
        live_a.refresh_from_db()
        live_b.refresh_from_db()
        sold_a.refresh_from_db()
        sold_b.refresh_from_db()
        self.assertEqual(live_a.status, 'reserved')
        self.assertEqual(live_b.status, 'reserved')
        self.assertEqual(sold_a.status, 'sold')
        self.assertEqual(sold_b.status, 'sold')
        self.assertFalse(sold_a.reserved_by_id)

        listing = self.client.get(f'/api/users/events/{self.event.pk}/tickets/')
        rows = listing.data if isinstance(listing.data, list) else listing.data
        sold_row = next(t for t in rows if t['id'] == sold_a.id)
        live_row = next(t for t in rows if t['id'] == live_a.id)
        self.assertFalse(sold_row.get('is_locked'))
        self.assertTrue(live_row.get('is_locked'))

    def test_partially_sold_group_reserve_without_listing_group_id_uses_siblings(self):
        group_id = str(uuid4())
        sold = self._ticket(listing_group_id=group_id, status='sold', available_quantity=0)
        live = self._ticket(listing_group_id=group_id)
        self.client.force_authenticate(self.buyer)
        lock = self.client.post(
            f'/api/users/tickets/{sold.id}/reserve/',
            {'quantity': 1},
            format='json',
        )
        self.assertEqual(lock.status_code, 200, lock.data)
        live.refresh_from_db()
        sold.refresh_from_db()
        self.assertEqual(live.status, 'reserved')
        self.assertEqual(sold.status, 'sold')

    def test_cannot_reserve_more_than_remaining_after_partial_sale(self):
        group_id = str(uuid4())
        self._ticket(listing_group_id=group_id, status='sold', available_quantity=0)
        self._ticket(listing_group_id=group_id, status='sold', available_quantity=0)
        live = self._ticket(listing_group_id=group_id)
        self._ticket(listing_group_id=group_id)
        self.client.force_authenticate(self.buyer)
        blocked = self.client.post(
            f'/api/users/tickets/{live.id}/reserve/',
            {'listing_group_id': group_id, 'quantity': 3},
            format='json',
        )
        self.assertEqual(blocked.status_code, 400, blocked.data)
        self.assertEqual(blocked.data.get('code'), 'insufficient_inventory')
        live.refresh_from_db()
        self.assertEqual(live.status, 'active')
