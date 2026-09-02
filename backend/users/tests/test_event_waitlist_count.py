"""Public waitlist_count on event list/detail APIs."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from users.models import Artist, Event, TicketAlert
from users.serializers import EventListSerializer, EventSerializer


class EventWaitlistCountApiTests(APITestCase):
    def setUp(self):
        self.api = APIClient()
        self.artist = Artist.objects.create(name='Waitlist Artist')
        self.event = Event.objects.create(
            name='Waitlist Show',
            artist=self.artist,
            date=timezone.now() + timedelta(days=5),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.other = Event.objects.create(
            name='Quiet Show',
            artist=self.artist,
            date=timezone.now() + timedelta(days=6),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        TicketAlert.objects.create(event=self.event, email='one@example.test', notified=False)
        TicketAlert.objects.create(event=self.event, email='two@example.test', notified=False)
        TicketAlert.objects.create(event=self.event, email='done@example.test', notified=True)
        TicketAlert.objects.create(
            artist=self.artist,
            event=None,
            email='artist@example.test',
            notified=False,
        )

    def test_list_exposes_waiting_event_alerts_only(self):
        res = self.api.get('/api/users/events/')
        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        by_id = {item['id']: item for item in payload}
        self.assertEqual(by_id[self.event.id]['waitlist_count'], 2)
        self.assertEqual(by_id[self.other.id]['waitlist_count'], 0)

    def test_detail_exposes_waitlist_count(self):
        res = self.api.get(f'/api/users/events/{self.event.id}/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['waitlist_count'], 2)

    def test_serializers_return_integer_zero_without_alerts(self):
        self.assertEqual(EventSerializer(self.other).data['waitlist_count'], 0)
        self.assertEqual(EventListSerializer(self.other).data['waitlist_count'], 0)
