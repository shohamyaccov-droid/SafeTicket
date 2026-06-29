from django.test import TestCase
from rest_framework.test import APIClient

from users.models import Artist


class ArtistListApiTests(TestCase):
    def test_artist_list_includes_zero_inventory_artists(self):
        Artist.objects.create(name='Zero Inventory Artist')

        res = APIClient().get('/api/users/artists/')

        self.assertEqual(res.status_code, 200, res.content)
        payload = res.data if isinstance(res.data, list) else res.data.get('results', [])
        row = next((item for item in payload if item['name'] == 'Zero Inventory Artist'), None)
        self.assertIsNotNone(row)
        self.assertEqual(row['total_tickets_count'], 0)
