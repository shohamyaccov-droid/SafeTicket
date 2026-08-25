"""Artist slug generation + hub-page SEO payload tests."""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event
from users.seo import (
    build_artist_seo_payload,
    build_artist_slug_base,
    build_sitemap_xml,
    inject_seo_into_html,
)


@override_settings(
    FRONTEND_ORIGIN='https://tradetix.co.il',
    PUBLIC_SITE_ORIGIN='https://tradetix.co.il',
)
class ArtistSlugAndSeoTests(TestCase):
    def setUp(self):
        self.artist = Artist.objects.filter(name='אייל גולן').first()
        if not self.artist:
            self.artist = Artist.objects.create(name='אייל גולן')
        self.event = Event.objects.create(
            artist=self.artist,
            name='אייל גולן Live',
            date=timezone.now() + timedelta(days=30),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.client = APIClient()

    def test_hebrew_name_aliases_to_eyal_golan_slug(self):
        self.assertEqual(self.artist.slug, 'eyal-golan')
        self.assertEqual(build_artist_slug_base(self.artist), 'eyal-golan')

    def test_latin_name_also_aliases_to_eyal_golan(self):
        latin = Artist.objects.create(name='Eyal Golan')
        self.assertTrue(latin.slug.startswith('eyal-golan'))
        self.assertNotEqual(latin.slug, self.artist.slug)

    def test_retrieve_and_events_by_slug(self):
        res = self.client.get('/api/users/artists/eyal-golan/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['id'], self.artist.id)
        self.assertEqual(res.data['name'], 'אייל גולן')
        self.assertEqual(res.data['slug'], 'eyal-golan')
        self.assertTrue(res.data['seo_title'].startswith('כרטיסים לאייל גולן'))
        self.assertIn('לוח הופעות וכרטיסים יד שנייה', res.data['seo_title'])
        self.assertIn('TradeTix', res.data['seo_title'])
        self.assertIn('מחפשים כרטיסים לאייל גולן', res.data['seo_description'])
        self.assertTrue(res.data['canonical_url'].endswith('/artist/eyal-golan'))

        by_id = self.client.get(f'/api/users/artists/{self.artist.pk}/')
        self.assertEqual(by_id.status_code, 200, by_id.content)
        self.assertEqual(by_id.data['slug'], 'eyal-golan')

        events = self.client.get('/api/users/artists/eyal-golan/events/')
        self.assertEqual(events.status_code, 200, events.content)
        self.assertTrue(any(row['id'] == self.event.id for row in events.data))

    def test_seo_endpoint_and_html_injection(self):
        res = self.client.get('/api/users/artists/eyal-golan/seo/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertIn('כרטיסים לאייל גולן', res.data['seo_title'])
        self.assertEqual(res.data['json_ld']['@type'], 'MusicGroup')

        seo = build_artist_seo_payload(self.artist)
        html = inject_seo_into_html(
            '<html><head><title>Old</title>'
            '<meta name="description" content="x"></head>'
            '<body><div id="root"></div></body></html>',
            seo,
        )
        self.assertIn(seo['seo_title'], html)
        self.assertIn('כרטיסים לאייל גולן', html)
        self.assertIn('application/ld+json', html)
        self.assertIn('MusicGroup', html)
        self.assertIn('rel="canonical"', html)
        self.assertIn('/artist/eyal-golan', html)
        self.assertIn('יש לך כרטיס מיותר', html)

    def test_sitemap_includes_artist_route(self):
        xml = build_sitemap_xml()
        self.assertIn('https://tradetix.co.il/artist/eyal-golan', xml)
        self.assertIn(f'https://tradetix.co.il/event/{self.event.slug}', xml)
