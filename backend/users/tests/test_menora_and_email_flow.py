from decimal import Decimal
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket, Venue


User = get_user_model()


class MenoraAndEmailFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='menora-email-admin',
            email='admin@tradetix.test',
            password='pass',
            is_staff=True,
        )
        self.seller = User.objects.create_user(
            username='menora-email-seller',
            email='seller@tradetix.test',
            password='pass',
            role='seller',
        )
        self.artist = Artist.objects.create(name='Menora QA Artist')
        self.menora = Venue.objects.get(name='היכל מנורה מבטחים', city='תל אביב')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Menora QA Show',
            date=timezone.now() + timedelta(days=30),
            venue='היכל מנורה מבטחים',
            venue_place=self.menora,
            city='תל אביב',
            country='IL',
        )

    def test_menora_event_sections_use_real_lower_upper_blocks(self):
        response = self.client.get(f'/api/users/events/{self.event.id}/')

        self.assertEqual(response.status_code, 200, getattr(response, 'data', response.content))
        sections = response.data['venue_detail']['sections']
        names = {section['name'] for section in sections}

        self.assertIn('1 תחתון', names)
        self.assertIn('1 עליון', names)
        self.assertNotIn('101', names)

    @mock.patch.dict('os.environ', {'RESEND_API_KEY': 're_test_key'})
    @mock.patch('users.utils.emails._post_resend_http', return_value={'id': 'email_test'})
    def test_ticket_approval_sends_one_resend_email(self, mock_resend_send):
        ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('100'),
            asking_price=Decimal('100'),
            pdf_file='tickets/pdfs/menora-email.pdf',
            receipt_file='tickets/receipts/menora-email-receipt.pdf',
            status='pending_approval',
            verification_status='ממתין לאישור',
            row='7',
            seat_numbers='22',
            available_quantity=1,
        )
        self.client.force_authenticate(self.admin)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/users/admin/tickets/{ticket.id}/approve/', {}, format='json')

        self.assertEqual(response.status_code, 200, getattr(response, 'data', response.content))
        mock_resend_send.assert_called_once()
        payload = mock_resend_send.call_args.args[1]
        self.assertEqual(payload['from'], 'TradeTix <onboarding@resend.dev>')
        self.assertEqual(payload['to'], [self.seller.email])
        self.assertIn('הכרטיס שלך אושר', payload['subject'])
        self.assertIn('html', payload)
        self.assertIn('הכרטיס שלכם אושר', payload['html'])
        self.assertNotIn('לוגו TradeTix יופיע כאן', payload['html'])
        self.assertIn('tab=sales', payload['html'])
