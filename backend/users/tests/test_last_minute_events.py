"""Homepage last-minute (דקה 90) event list: next 14 days, chronological."""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from users.models import Artist, Event, Ticket, User


class LastMinuteEventsApiTests(APITestCase):
    def setUp(self):
        self.api = APIClient()
        self.now = timezone.now()
        self.seller = User.objects.create_user(
            username='lm_seller',
            email='lm_seller@example.test',
            password='pass-12345',
            role='seller',
        )
        self.artist = Artist.objects.create(name='Last Minute Artist')

    def _event(self, *, name, when, with_ticket=True):
        event = Event.objects.create(
            name=name,
            artist=self.artist,
            date=when,
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        if with_ticket:
            Ticket.objects.create(
                seller=self.seller,
                event=event,
                event_name=event.name,
                event_date=event.date,
                venue=event.venue,
                original_price=Decimal('100.00'),
                asking_price=Decimal('100.00'),
                available_quantity=1,
                status='active',
                verification_status='מאומת',
                pdf_file='tickets/pdfs/last-minute.pdf',
            )
        return event

    def test_last_minute_excludes_past_and_beyond_14_days_and_sorts_soonest_first(self):
        past = self._event(name='Past Show', when=self.now - timedelta(days=1))
        soon = self._event(name='Soonest Show', when=self.now + timedelta(days=2))
        later = self._event(name='Later Show', when=self.now + timedelta(days=10))
        too_far = self._event(name='Far Show', when=self.now + timedelta(days=15))
        empty = self._event(
            name='Soon No Tickets',
            when=self.now + timedelta(days=3),
            with_ticket=False,
        )

        res = self.api.get('/api/users/events/', {'last_minute': '1'})
        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names = [item['name'] for item in payload]

        self.assertIn(soon.name, names)
        self.assertIn(later.name, names)
        self.assertNotIn(past.name, names)
        self.assertNotIn(too_far.name, names)
        self.assertNotIn(empty.name, names)
        self.assertLess(names.index(soon.name), names.index(later.name))
        self.assertIn('waitlist_count', payload[0])
        self.assertEqual(payload[0]['waitlist_count'], 0)

    def test_default_event_list_still_includes_events_beyond_14_days(self):
        far = self._event(name='Far Marketplace Show', when=self.now + timedelta(days=20))
        res = self.api.get('/api/users/events/')
        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names = [item['name'] for item in payload]
        self.assertIn(far.name, names)
