"""
Permanent ticket status=taken (נתפס) must never be reservable or purchasable.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from users.models import Artist, Event, Ticket
from users.ticket_status import HE_TICKET_TAKEN, TICKET_STATUS_TAKEN
from users.views import TicketViewSet, create_order, guest_checkout


User = get_user_model()


class TakenTicketPurchaseBlockTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='taken_seller',
            email='taken_seller@example.com',
            password='pass',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='taken_buyer',
            email='taken_buyer@example.com',
            password='pass',
            role='buyer',
        )
        self.artist = Artist.objects.create(name='Taken Artist')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Taken Show',
            date=timezone.now() + timedelta(days=14),
            venue='Menora Mivtachim Arena',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file='tickets/pdfs/taken-test.pdf',
            status=TICKET_STATUS_TAKEN,
            verification_status='מאומת',
            available_quantity=1,
            custom_section_text='אזור בדיקה A',
            seat_row='1',
            listing_group_id='taken-group-1',
        )

    def test_reserve_rejected_for_taken_ticket(self):
        view = TicketViewSet.as_view({'post': 'reserve'})
        req = self.factory.post(f'/tickets/{self.ticket.id}/reserve/', {})
        force_authenticate(req, user=self.buyer)
        res = view(req, pk=self.ticket.id)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['error'], HE_TICKET_TAKEN)
        self.assertEqual(res.data['status'], TICKET_STATUS_TAKEN)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TICKET_STATUS_TAKEN)

    def test_create_order_rejected_for_taken_ticket(self):
        req = self.factory.post(
            '/orders/',
            {
                'ticket': self.ticket.id,
                'quantity': 1,
                'total_amount': '107.00',
                'accepted_terms': True,
            },
            format='json',
        )
        force_authenticate(req, user=self.buyer)
        res = create_order(req)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['error'], HE_TICKET_TAKEN)

    def test_guest_checkout_rejected_for_taken_ticket(self):
        req = self.factory.post(
            '/orders/guest/',
            {
                'ticket_id': self.ticket.id,
                'quantity': 1,
                'total_amount': '107.00',
                'guest_email': 'guest@example.com',
                'guest_phone': '0501234567',
                'guest_first_name': 'ישראל',
                'guest_last_name': 'ישראלי',
                'accepted_terms': True,
            },
            format='json',
        )
        res = guest_checkout(req)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['error'], HE_TICKET_TAKEN)

    def test_create_order_rejected_for_taken_listing_group(self):
        req = self.factory.post(
            '/orders/',
            {
                'ticket': self.ticket.id,
                'listing_group_id': 'taken-group-1',
                'quantity': 1,
                'total_amount': '107.00',
                'accepted_terms': True,
            },
            format='json',
        )
        force_authenticate(req, user=self.buyer)
        res = create_order(req)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['error'], HE_TICKET_TAKEN)

    def test_event_tickets_list_includes_taken_rows(self):
        res = self.client.get(f'/api/users/events/{self.event.pk}/tickets/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        rows = data if isinstance(data, list) else data.get('results', [])
        statuses = {row.get('status') for row in rows}
        self.assertIn(TICKET_STATUS_TAKEN, statuses)
        taken_row = next(r for r in rows if r.get('status') == TICKET_STATUS_TAKEN)
        self.assertEqual(taken_row['id'], self.ticket.id)
        self.assertTrue(taken_row.get('is_taken'))

    def test_event_tickets_list_includes_sold_rows_as_taken(self):
        sold = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            pdf_file='tickets/pdfs/sold-test.pdf',
            status='sold',
            verification_status='מאומת',
            available_quantity=0,
            custom_section_text='אזור נמכר',
            seat_row='2',
            listing_group_id='sold-group-1',
        )
        res = self.client.get(f'/api/users/events/{self.event.pk}/tickets/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        rows = data if isinstance(data, list) else data.get('results', [])
        sold_row = next(r for r in rows if r.get('id') == sold.id)
        self.assertEqual(sold_row['status'], 'sold')
        self.assertTrue(sold_row.get('is_taken'))
