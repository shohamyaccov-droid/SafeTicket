"""Event slug generation + Schema.org JSON-LD SEO payload tests."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket
from users.seo import (
    build_event_json_ld,
    build_event_seo_payload,
    build_event_slug_base,
    build_seo_title,
    build_sitemap_xml,
    get_static_page_seo,
    inject_seo_into_html,
)

User = get_user_model()


@override_settings(
    FRONTEND_ORIGIN='https://tradetix.co.il',
    PUBLIC_SITE_ORIGIN='https://tradetix.co.il',
)
class EventSlugAndSeoTests(TestCase):
    def setUp(self):
        # Launch seed already creates אייל גולן / איתי לוי; reuse them so
        # ASCII slugs stay eyal-golan / itay-levi instead of -6 / -7 suffixes.
        self.artist = Artist.objects.filter(name='אייל גולן').first()
        if not self.artist:
            self.artist = Artist.objects.create(name='אייל גולן')
        self.event = Event.objects.create(
            artist=self.artist,
            name='Eyal Golan Live',
            date=timezone.now() + timedelta(days=30),
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.seller = User.objects.create_user(
            username='seo_seller',
            email='seo_seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('200'),
            asking_price=Decimal('250'),
            available_quantity=2,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/seo.pdf',
        )
        Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=Decimal('300'),
            asking_price=Decimal('400'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/seo2.pdf',
        )

        Ticket.objects.filter(event=self.event).update(
            asking_price=Decimal('250.00')
        )
        Ticket.objects.filter(event=self.event, original_price=Decimal('300')).update(
            asking_price=Decimal('400.00')
        )
        # Re-fetch for SEO helpers
        self.event.refresh_from_db()

    def test_slug_auto_generated_unique(self):
        self.assertTrue(self.event.slug)
        self.assertTrue(all(ord(c) < 128 for c in self.event.slug), self.event.slug)
        self.assertIn('eyal-golan', self.event.slug.lower())
        self.assertNotIn('tel-aviv', self.event.slug.lower())
        date_part = timezone.localtime(self.event.date).strftime('%Y-%m-%d')
        self.assertEqual(self.artist.slug, 'eyal-golan')
        self.assertEqual(self.event.slug, f'eyal-golan-{date_part}')
        twin = Event.objects.create(
            artist=self.artist,
            name='Eyal Golan Live 2',
            date=self.event.date,
            venue='היכל מנורה מבטחים',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.assertTrue(twin.slug)
        self.assertTrue(all(ord(c) < 128 for c in twin.slug), twin.slug)
        self.assertNotEqual(twin.slug, self.event.slug)
        self.assertTrue(twin.slug.startswith(f'eyal-golan-{date_part}'))

    def test_hebrew_artist_slug_is_english_artist_and_date(self):
        from datetime import datetime

        artist = Artist.objects.filter(name='איתי לוי').first()
        if not artist:
            artist = Artist.objects.create(name='איתי לוי')
        self.assertEqual(artist.slug, 'itay-levi')
        show_at = timezone.make_aware(datetime(2026, 8, 29, 20, 0, 0))
        event = Event.objects.create(
            artist=artist,
            name='איתי לוי בהופעה',
            date=show_at,
            venue='אמפי MAX',
            city='ראשון לציון',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.assertEqual(event.slug, 'itay-levi-2026-08-29')
        self.assertTrue(all(ord(c) < 128 for c in event.slug))

    def test_legacy_hebrew_slug_still_resolves(self):
        from users.seo import event_legacy_redirect_path, resolve_event_by_identifier

        hebrew = 'אייל-גולן-תל-אביב-2099-01-01'
        Event.objects.filter(pk=self.event.pk).update(legacy_slug=hebrew)
        self.event.refresh_from_db()

        found = resolve_event_by_identifier(hebrew)
        self.assertEqual(found.pk, self.event.pk)

        client = APIClient()
        res = client.get(f'/api/users/events/{hebrew}/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['id'], self.event.pk)
        self.assertEqual(res.data['slug'], self.event.slug)
        self.assertTrue(res.data['canonical_url'].endswith(f'/event/{self.event.slug}'))

        tickets = client.get(f'/api/users/events/{hebrew}/tickets/')
        self.assertEqual(tickets.status_code, 200)

        self.assertEqual(event_legacy_redirect_path(hebrew, self.event), f'/event/{self.event.slug}')
        self.assertIsNone(event_legacy_redirect_path(self.event.slug, self.event))

    def test_slug_base_from_artist_and_date(self):
        base = build_event_slug_base(self.event)
        self.assertIn('eyal-golan', base.lower())
        self.assertNotIn('tel-aviv', base.lower())
        self.assertRegex(base, r'^eyal-golan-\d{4}-\d{2}-\d{2}$')

    def test_json_ld_event_and_aggregate_offer(self):
        data = build_event_json_ld(self.event)
        self.assertEqual(data['@context'], 'https://schema.org')
        self.assertEqual(data['@type'], 'Event')
        self.assertEqual(data['name'], 'Eyal Golan Live')
        self.assertTrue(data['startDate'])
        self.assertEqual(data['location']['@type'], 'Place')
        offers = data['offers']
        self.assertEqual(offers['@type'], 'AggregateOffer')
        self.assertEqual(offers['priceCurrency'], 'ILS')
        self.assertEqual(Decimal(offers['lowPrice']), Decimal('250.00'))
        self.assertEqual(Decimal(offers['highPrice']), Decimal('400.00'))
        self.assertEqual(offers['offerCount'], '3')
        self.assertIn('InStock', offers['availability'])
        self.assertTrue(data['url'].endswith(f'/event/{self.event.slug}'))
        nested = offers.get('offers') or []
        self.assertGreaterEqual(len(nested), 1)
        self.assertEqual(nested[0]['@type'], 'Offer')
        self.assertIn('price', nested[0])

    def test_seo_title_uses_artist_and_venue(self):
        title = build_seo_title(self.event)
        self.assertTrue(title.startswith('כרטיסים ל'))
        self.assertIn(self.artist.name, title)
        self.assertIn('TradeTix', title)

    def test_sitemap_includes_static_pages_and_active_events(self):
        import xml.etree.ElementTree as ET

        xml = build_sitemap_xml()
        self.assertIn('<?xml version="1.0"', xml)
        self.assertIn('urlset', xml)
        self.assertIn('https://tradetix.co.il/how-it-works', xml)
        self.assertIn('https://tradetix.co.il/faq', xml)
        self.assertIn(f'https://tradetix.co.il/event/{self.event.slug}', xml)
        self.assertIn('https://tradetix.co.il/artist/eyal-golan', xml)
        ET.fromstring(xml)
        cancelled = Event.objects.create(
            artist=self.artist,
            name='Cancelled Show',
            date=timezone.now() + timedelta(days=10),
            venue='Hall',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='בוטל',
        )
        xml2 = build_sitemap_xml()
        self.assertNotIn(f'/event/{cancelled.slug}', xml2)

    def test_robots_allows_crawlers_and_points_to_sitemap(self):
        res = self.client.get('/robots.txt')
        self.assertEqual(res.status_code, 200)
        body = res.content.decode('utf-8')
        self.assertIn('User-agent: *', body)
        self.assertIn('Allow: /', body)
        self.assertIn('Sitemap: https://tradetix.co.il/sitemap.xml', body)

    def test_sitemap_endpoint_returns_xml(self):
        res = self.client.get('/sitemap.xml')
        self.assertEqual(res.status_code, 200)
        self.assertIn('xml', res['Content-Type'])
        self.assertIn('<urlset', res.content.decode('utf-8'))
        self.assertIn('public, max-age=300', res['Cache-Control'])

    def test_inject_html_includes_json_ld_script(self):
        seo = build_event_seo_payload(self.event)
        html = inject_seo_into_html(
            '<html><head><title>Old</title>'
            '<meta name="robots" content="noindex, nofollow">'
            '<meta name="description" content="x"></head>'
            '<body><div id="root"></div></body></html>',
            seo,
        )
        self.assertIn(seo['seo_title'], html)
        self.assertIn('application/ld+json', html)
        self.assertIn('"@type": "Event"', html)
        self.assertIn('AggregateOffer', html)
        self.assertIn('rel="canonical"', html)
        self.assertIn('https://tradetix.co.il/event/', seo['canonical_url'])
        self.assertIn('name="robots" content="index, follow"', html)
        self.assertNotIn('noindex', html)

    def test_how_it_works_crawler_html_has_headings_and_steps(self):
        seo = get_static_page_seo('/how-it-works')
        self.assertIsNotNone(seo)
        self.assertIn('איך למכור כרטיס', seo['crawler_html'])
        self.assertIn('<ol>', seo['crawler_html'])
        html = inject_seo_into_html(
            '<html><head><title>Old</title><meta name="description" content="x"></head>'
            '<body><div id="root"></div></body></html>',
            seo,
        )
        self.assertIn(seo['seo_title'], html)
        self.assertIn('איך למכור כרטיס להופעה', html)
        self.assertIn('כרטיסים יד שניה', html)
        self.assertIn('תשלום מאובטח', html)
        self.assertIn('<div id="root"><article class="seo-crawler-snapshot">', html)
        self.assertIn('HowTo', html)

    def test_faq_crawler_html_lists_questions(self):
        seo = get_static_page_seo('/faq')
        html = inject_seo_into_html(
            '<html><head><title>Old</title></head><body><div id="root"></div></body></html>',
            seo,
        )
        self.assertIn('שאלות ותשובות', html)
        self.assertIn('FAQPage', html)
        self.assertIn('הגנת הקונה', html)

    def test_home_static_seo_uses_default_title(self):
        seo = get_static_page_seo('/')
        self.assertTrue(seo['seo_title'].startswith('TradeTix'))
        html = inject_seo_into_html(
            '<html><head><title>Old</title></head><body><div id="root"></div></body></html>',
            seo,
        )
        self.assertIn('WebSite', html)

    def test_staging_frontend_origin_never_used_for_canonical(self):
        from users.seo import event_canonical_url, frontend_origin

        with self.settings(
            FRONTEND_ORIGIN='https://safeticket-web.onrender.com',
            PUBLIC_SITE_ORIGIN='',
        ):
            self.assertEqual(frontend_origin(), 'https://tradetix.co.il')
            self.assertTrue(
                event_canonical_url(self.event).startswith('https://tradetix.co.il/event/')
            )

    def test_api_retrieve_by_slug_and_seo_action(self):
        client = APIClient()
        by_id = client.get(f'/api/users/events/{self.event.pk}/')
        self.assertEqual(by_id.status_code, 200)
        self.assertEqual(by_id.data['slug'], self.event.slug)
        self.assertTrue(all(ord(c) < 128 for c in by_id.data['slug']))
        self.assertTrue(by_id.data['canonical_url'].endswith(f'/event/{self.event.slug}'))
        self.assertIn('seo_title', by_id.data)
        self.assertEqual(by_id.data['json_ld']['@type'], 'Event')

        by_slug = client.get(f'/api/users/events/{self.event.slug}/')
        self.assertEqual(by_slug.status_code, 200)
        self.assertEqual(by_slug.data['id'], self.event.pk)

        seo = client.get(f'/api/users/events/{self.event.slug}/seo/')
        self.assertEqual(seo.status_code, 200)
        self.assertEqual(seo.data['json_ld']['offers']['@type'], 'AggregateOffer')

        tickets = client.get(f'/api/users/events/{self.event.slug}/tickets/')
        self.assertEqual(tickets.status_code, 200)
        self.assertGreaterEqual(len(tickets.data), 2)
