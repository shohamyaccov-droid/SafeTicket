from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket, User


class ArtistListApiTests(TestCase):
    def test_artist_list_includes_zero_inventory_artists(self):
        Artist.objects.create(name='Zero Inventory Artist', category='standup')

        res = APIClient().get('/api/users/artists/')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        row = next((item for item in payload if item['name'] == 'Zero Inventory Artist'), None)
        self.assertIsNotNone(row)
        self.assertEqual(row['total_tickets_count'], 0)
        self.assertEqual(row['category'], 'standup')

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

    def test_artist_list_does_not_count_past_event_inventory_as_active(self):
        seller = User.objects.create_user(
            username='past_artist_seller',
            email='past-artist-seller@example.test',
            password='pass-12345',
            role='seller',
        )
        artist = Artist.objects.create(name='Past Inventory Artist')
        past_event = Event.objects.create(
            name='Past Artist Show',
            artist=artist,
            date=timezone.now() - timezone.timedelta(days=3),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        Ticket.objects.create(
            seller=seller,
            event=past_event,
            event_name=past_event.name,
            event_date=past_event.date,
            venue=past_event.venue,
            original_price='100.00',
            asking_price='100.00',
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/past-artist.pdf',
        )

        res = APIClient().get('/api/users/artists/')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        row = next((item for item in payload if item['name'] == artist.name), None)
        self.assertIsNotNone(row)
        self.assertEqual(row['total_tickets_count'], 0)

    def test_artist_list_excludes_international_artists(self):
        Artist.objects.create(name='Local Artist')
        Artist.objects.create(name='Taylor Swift', is_international=True)

        res = APIClient().get('/api/users/artists/')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names = [item['name'] for item in payload]
        self.assertIn('Local Artist', names)
        self.assertNotIn('Taylor Swift', names)

    def test_recommended_artist_list_excludes_empty_and_past_only_artists(self):
        seller = User.objects.create_user(
            username='recommended_seller',
            email='recommended-seller@example.test',
            password='pass-12345',
            role='seller',
        )
        empty_artist = Artist.objects.create(name='Empty Recommended Artist')
        past_artist = Artist.objects.create(name='Past Recommended Artist')
        future_artist = Artist.objects.create(name='Future Recommended Artist')
        ticket_artist = Artist.objects.create(name='Ticket Recommended Artist')
        past_event = Event.objects.create(
            name='Past Recommended Show',
            artist=past_artist,
            date=timezone.now() - timezone.timedelta(days=3),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        future_event = Event.objects.create(
            name='Future Recommended Show',
            artist=future_artist,
            date=timezone.now() + timezone.timedelta(days=12),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        ticket_event = Event.objects.create(
            name='Ticket Recommended Show',
            artist=ticket_artist,
            date=timezone.now() + timezone.timedelta(days=20),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        for event, pdf_name in (
            (past_event, 'past-recommended.pdf'),
            (ticket_event, 'ticket-recommended.pdf'),
        ):
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
                pdf_file=f'tickets/{pdf_name}',
            )

        res = APIClient().get('/api/users/artists/?recommended=1')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names = [item['name'] for item in payload]
        self.assertNotIn(empty_artist.name, names)
        self.assertNotIn(past_artist.name, names)
        self.assertIn(future_artist.name, names)
        self.assertIn(ticket_artist.name, names)


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

    def test_event_list_excludes_international_artists(self):
        local_artist = Artist.objects.create(name='Local Event Artist')
        international_artist = Artist.objects.create(name='Bruno Mars', is_international=True)
        local_event = Event.objects.create(
            name='Local Event',
            artist=local_artist,
            date=timezone.now() + timezone.timedelta(days=7),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        Event.objects.create(
            name='International Event',
            artist=international_artist,
            date=timezone.now() + timezone.timedelta(days=7),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )

        res = APIClient().get('/api/users/events/')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        names = [item['name'] for item in payload]
        self.assertIn(local_event.name, names)
        self.assertNotIn('International Event', names)
