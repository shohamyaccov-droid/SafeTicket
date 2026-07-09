from django.test import TestCase
from django.utils import timezone

from users.models import Event
from users.serializers import EventListSerializer, EventSerializer


class EventVenueApiNormalizationTests(TestCase):
    def setUp(self):
        self.event = Event.objects.create(
            name='Test Show',
            date=timezone.now(),
            venue='אחר',
            city='תל אביב',
            country='IL',
        )

    def test_event_serializer_maps_other_to_israel(self):
        data = EventSerializer(self.event).data
        self.assertEqual(data['venue'], 'ישראל')

    def test_event_list_serializer_maps_other_to_israel(self):
        data = EventListSerializer(self.event).data
        self.assertEqual(data['venue'], 'ישראל')

    def test_named_venue_unchanged(self):
        self.event.venue = 'היכל מנורה מבטחים'
        self.event.save(update_fields=['venue'])
        data = EventSerializer(self.event).data
        self.assertEqual(data['venue'], 'היכל מנורה מבטחים')
