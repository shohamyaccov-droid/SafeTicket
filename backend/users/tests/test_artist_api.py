from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket, User


class ArtistListApiTests(TestCase):
    def test_artist_list_includes_zero_inventory_artists(self):
        Artist.objects.create(name='Zero Inventory Artist')

        res = APIClient().get('/api/users/artists/')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        row = next((item for item in payload if item['name'] == 'Zero Inventory Artist'), None)
        self.assertIsNotNone(row)
        self.assertEqual(row['total_tickets_count'], 0)

    def test_artist_list_orders_active_inventory_before_empty_artists(self):
        seller = User.objects.create_user(
            username='artist_sort_seller',
            email='artist-sort-seller@example.test',
            password='pass-12345',
            role='seller',
        )
        empty_artist = Artist.objects.create(name='AAA Empty Artist')
        active_artist = Artist.objects.create(name='ZZZ Active Artist')
        event = Event.objects.create(
            name='Active Artist Show',
            artist=active_artist,
            date=timezone.now() + timezone.timedelta(days=14),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        Ticket.objects.create(
            seller=seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price='100.00',
            asking_price='100.00',
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/artist-sort.pdf',
        )

        res = APIClient().get('/api/users/artists/')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names = [item['name'] for item in payload]
        self.assertLess(names.index(active_artist.name), names.index(empty_artist.name))


class EventListApiTests(TestCase):
    def test_event_list_orders_active_inventory_before_empty_events(self):
        seller = User.objects.create_user(
            username='event_sort_seller',
            email='event-sort-seller@example.test',
            password='pass-12345',
            role='seller',
        )
        artist = Artist.objects.create(name='Event Sort Artist')
        empty_event = Event.objects.create(
            name='AAA Empty Event',
            artist=artist,
            date=timezone.now() + timezone.timedelta(days=7),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        active_event = Event.objects.create(
            name='ZZZ Active Event',
            artist=artist,
            date=timezone.now() + timezone.timedelta(days=30),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        Ticket.objects.create(
            seller=seller,
            event=active_event,
            event_name=active_event.name,
            event_date=active_event.date,
            venue=active_event.venue,
            original_price='100.00',
            asking_price='100.00',
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/event-sort.pdf',
        )

        res = APIClient().get('/api/users/events/')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names = [item['name'] for item in payload]
        self.assertLess(names.index(active_event.name), names.index(empty_event.name))
