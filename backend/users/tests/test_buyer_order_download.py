"""Buyer dashboard purchase timeline and ticket download payload."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Event, Order, Ticket

User = get_user_model()


@override_settings(DEBUG=True, SECRET_KEY='test-secret-key-for-local')
class BuyerOrderDownloadTimelineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(
            username='buyer_dl',
            email='buyer_dl@test.com',
            password='test-pass-123',
        )
        self.seller = User.objects.create_user(
            username='seller_dl',
            email='seller_dl@test.com',
            password='test-pass-123',
            role='seller',
        )
        self.event = Event.objects.create(
            name='Download Event',
            date=timezone.now() + timedelta(days=10),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='sold',
            available_quantity=0,
            pdf_file=SimpleUploadedFile('ticket.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='paid',
            total_amount=Decimal('115.00'),
            total_paid_by_buyer=Decimal('115.00'),
            final_negotiated_price=Decimal('100.00'),
            buyer_service_fee=Decimal('15.00'),
            seller_service_fee=Decimal('0.00'),
            net_seller_revenue=Decimal('100.00'),
            quantity=1,
            event_name=self.event.name,
            ticket_ids=[self.ticket.pk],
        )

    def test_paid_order_timeline_is_ready_for_download_not_processing(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.get('/api/users/dashboard/')
        self.assertEqual(res.status_code, 200)
        purchase = next(p for p in res.data['purchases'] if p['id'] == self.order.pk)
        timeline = purchase['status_timeline']
        self.assertEqual(timeline['current_label'], 'מוכן להורדה')
        labels = [s['label'] for s in timeline['steps']]
        self.assertEqual(labels[1], 'תשלום אושר')
        self.assertEqual(labels[2], 'מוכן להורדה')
        self.assertEqual(labels.count('מוכן להורדה'), 1)
        self.assertNotIn('מעבד', labels)
        self.assertTrue(purchase['tickets'][0]['has_pdf_file'])
        self.assertTrue(purchase['tickets'][0]['pdf_file_url'])
        self.assertEqual(purchase['tickets'][0]['id'], self.ticket.pk)
        self.assertIn('ticket_ids', purchase)
        self.assertEqual(purchase['ticket_ids'], [self.ticket.pk])
        self.assertEqual(purchase['ticket_details']['id'], self.ticket.pk)

    def test_buyer_can_download_paid_ticket_file(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.get(f'/api/users/tickets/{self.ticket.pk}/download_pdf/')
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.content), 0)
        self.assertTrue(res['Content-Type'].startswith('application/pdf'))
        self.assertIn('attachment', res['Content-Disposition'])

    def test_ticket_details_include_section_row_seat_when_fk_null(self):
        self.ticket.custom_section_text = 'שער 7'
        self.ticket.row = '12'
        self.ticket.seat_numbers = '3-4'
        self.ticket.save(update_fields=['custom_section_text', 'row', 'seat_numbers', 'section_legacy'])
        self.order.ticket = None
        self.order.ticket_ids = [self.ticket.pk]
        self.order.save(update_fields=['ticket', 'ticket_ids'])

        self.client.force_authenticate(user=self.buyer)
        res = self.client.get('/api/users/dashboard/')
        self.assertEqual(res.status_code, 200)
        purchase = next(p for p in res.data['purchases'] if p['id'] == self.order.pk)
        details = purchase['ticket_details']
        self.assertEqual(details['id'], self.ticket.pk)
        self.assertEqual(details['section'], 'שער 7')
        self.assertEqual(details['row'], '12')
        self.assertEqual(details['seat_numbers'], '3-4')
        self.assertTrue(purchase['pdf_download_url'])
        self.assertIn(str(self.ticket.pk), purchase['pdf_download_url'])
        self.assertEqual(purchase['tickets'][0]['id'], self.ticket.pk)
