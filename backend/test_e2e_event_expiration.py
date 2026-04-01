"""
E2E QA: Event Expiration (Auto-hiding past events, blocking late purchases)
  - Test 1: GET /api/users/events/ returns ONLY future events
  - Test 2: simulate_payment on past-event ticket fails with 400

Run: python manage.py test test_e2e_event_expiration -v 2
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from users.models import Event, Artist, Ticket

User = get_user_model()


class E2EEventExpirationTest(TestCase):
    """E2E tests for event expiration logic."""

    def setUp(self):
        artist = Artist.objects.create(name='Expiration Test Artist')
        self.past_event = Event.objects.create(
            artist=artist,
            name='Past Event (Yesterday)',
            date=timezone.now() - timedelta(days=1),
            venue='מנורה מבטחים',
            city='Tel Aviv',
        )
        self.future_event = Event.objects.create(
            artist=artist,
            name='Future Event (Tomorrow)',
            date=timezone.now() + timedelta(days=1),
            venue='מנורה מבטחים',
            city='Tel Aviv',
        )
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF'
        pdf_file = SimpleUploadedFile('ticket.pdf', pdf_content, content_type='application/pdf')
        seller = User.objects.create_user(
            username='expiration_seller',
            email='exp@test.com',
            password='testpass123',
            role='seller',
        )
        self.past_ticket = Ticket.objects.create(
            seller=seller,
            event=self.past_event,
            event_name=self.past_event.name,
            original_price=100.00,
            asking_price=100.00,
            pdf_file=pdf_file,
            status='active',
            available_quantity=1,
            verification_status='מאומת',
        )
        pdf_file2 = SimpleUploadedFile('ticket2.pdf', pdf_content, content_type='application/pdf')
        self.future_ticket = Ticket.objects.create(
            seller=seller,
            event=self.future_event,
            event_name=self.future_event.name,
            original_price=100.00,
            asking_price=100.00,
            pdf_file=pdf_file2,
            status='active',
            available_quantity=1,
            verification_status='מאומת',
        )

    def test_1_feed_only_future_events(self):
        """
        GET /api/users/events/ returns ONLY the future event.
        Past event must not appear.
        """
        r = self.client.get('/api/users/events/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        if not isinstance(results, list):
            results = [data]
        ids = [e['id'] for e in results]
        self.assertIn(self.future_event.id, ids, 'Future event must be in feed')
        self.assertNotIn(self.past_event.id, ids, 'Past event must NOT be in feed')

    def test_1b_for_sell_lists_events_without_inventory(self):
        """
        Default GET hides events with no active listings; Sell flow uses for_sell=1.
        """
        artist = Artist.objects.create(name='Catalog Only Artist')
        no_ticket_event = Event.objects.create(
            artist=artist,
            name='Future Show — No Listings Yet',
            date=timezone.now() + timedelta(days=14),
            venue='מנורה מבטחים',
            city='Nashville',
        )
        r_default = self.client.get('/api/users/events/')
        self.assertEqual(r_default.status_code, 200)
        data = r_default.json()
        results = data.get('results', data) if isinstance(data, dict) else data
        ids = [e['id'] for e in results]
        self.assertNotIn(
            no_ticket_event.id,
            ids,
            'Marketplace feed must not surface zero-inventory events',
        )

        r_sell = self.client.get('/api/users/events/', {'for_sell': '1'})
        self.assertEqual(r_sell.status_code, 200)
        data2 = r_sell.json()
        results_sell = data2.get('results', data2) if isinstance(data2, dict) else data2
        ids_sell = [e['id'] for e in results_sell]
        self.assertIn(
            no_ticket_event.id,
            ids_sell,
            'Sell catalog must include upcoming events with no tickets yet',
        )

    def test_2_purchase_block_past_event(self):
        """
        simulate_payment on ticket for past event fails with 400.
        """
        r = self.client.post(
            '/api/users/payments/simulate/',
            {'ticket_id': self.past_ticket.id, 'amount': 110, 'quantity': 1},
            format='json',
        )
        self.assertEqual(r.status_code, 400, f'Expected 400, got {r.status_code}. Body: {r.content.decode()}')
        data = r.json()
        self.assertIn('error', data)
        self.assertIn('passed', str(data.get('error', '')).lower())
