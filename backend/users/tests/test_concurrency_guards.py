from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from users.models import Artist, Event, Offer, Ticket
from users.views import HE_OFFER_NOT_PENDING, HE_RESERVATION_RELEASE_FORBIDDEN, HE_TICKET_HELD_BY_OTHER
from users.views import OfferViewSet, TicketViewSet


User = get_user_model()


def _user(username, role='buyer'):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='pass',
        role=role,
    )


class MarketplaceConcurrencyGuardTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.seller = _user('seller', role='seller')
        self.buyer1 = _user('buyer1')
        self.buyer2 = _user('buyer2')
        self.artist = Artist.objects.create(name='Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Launch Show',
            date=timezone.now() + timedelta(days=30),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
        )

    def _ticket(self):
        return Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            pdf_file='tickets/pdfs/test.pdf',
            status='active',
            verification_status='מאומת',
            available_quantity=1,
        )

    def test_reserve_second_buyer_gets_hebrew_conflict(self):
        ticket = self._ticket()
        reserve_view = TicketViewSet.as_view({'post': 'reserve'})

        req1 = self.factory.post(f'/tickets/{ticket.id}/reserve/', {})
        force_authenticate(req1, user=self.buyer1)
        res1 = reserve_view(req1, pk=ticket.id)
        self.assertEqual(res1.status_code, 200)

        req2 = self.factory.post(f'/tickets/{ticket.id}/reserve/', {})
        force_authenticate(req2, user=self.buyer2)
        res2 = reserve_view(req2, pk=ticket.id)

        self.assertEqual(res2.status_code, 400)
        self.assertEqual(res2.data['error'], HE_TICKET_HELD_BY_OTHER)

    def test_wrong_user_cannot_release_reserved_ticket(self):
        ticket = self._ticket()
        ticket.status = 'reserved'
        ticket.reserved_by = self.buyer1
        ticket.reserved_at = timezone.now()
        ticket.save(update_fields=['status', 'reserved_by', 'reserved_at'])
        release_view = TicketViewSet.as_view({'post': 'release_reservation'})

        req = self.factory.post(f'/tickets/{ticket.id}/release_reservation/', {})
        force_authenticate(req, user=self.buyer2)
        res = release_view(req, pk=ticket.id)

        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data['error'], HE_RESERVATION_RELEASE_FORBIDDEN)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'reserved')

    def test_accept_rejects_competing_offer_after_first_accept(self):
        ticket = self._ticket()
        offer1 = Offer.objects.create(
            buyer=self.buyer1,
            ticket=ticket,
            amount=Decimal('90'),
            quantity=1,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1),
        )
        offer2 = Offer.objects.create(
            buyer=self.buyer2,
            ticket=ticket,
            amount=Decimal('95'),
            quantity=1,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1),
        )
        accept_view = OfferViewSet.as_view({'post': 'accept'})

        req1 = self.factory.post(f'/offers/{offer1.id}/accept/', {})
        force_authenticate(req1, user=self.seller)
        res1 = accept_view(req1, pk=offer1.id)
        self.assertEqual(res1.status_code, 200)

        offer2.refresh_from_db()
        self.assertEqual(offer2.status, 'rejected')
        req2 = self.factory.post(f'/offers/{offer2.id}/accept/', {})
        force_authenticate(req2, user=self.seller)
        res2 = accept_view(req2, pk=offer2.id)

        self.assertEqual(res2.status_code, 400)
        self.assertEqual(res2.data['error'], HE_OFFER_NOT_PENDING)

    def test_counter_double_submit_second_attempt_gets_clean_error(self):
        ticket = self._ticket()
        offer = Offer.objects.create(
            buyer=self.buyer1,
            ticket=ticket,
            amount=Decimal('90'),
            quantity=1,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1),
        )
        counter_view = OfferViewSet.as_view({'post': 'counter'})

        req1 = self.factory.post(f'/offers/{offer.id}/counter/', {'amount': '95'}, format='json')
        force_authenticate(req1, user=self.seller)
        res1 = counter_view(req1, pk=offer.id)
        self.assertEqual(res1.status_code, 201)

        req2 = self.factory.post(f'/offers/{offer.id}/counter/', {'amount': '96'}, format='json')
        force_authenticate(req2, user=self.seller)
        res2 = counter_view(req2, pk=offer.id)

        self.assertEqual(res2.status_code, 400)
        self.assertEqual(res2.data['error'], HE_OFFER_NOT_PENDING)
        self.assertEqual(Offer.objects.filter(parent_offer=offer).count(), 1)
