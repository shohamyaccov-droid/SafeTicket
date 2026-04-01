"""
E2E QA: Sell catalog (for_sell + artist) + US ticket active without receipt.

Simulates CEO flow: list events for sale, scope by artist, create US listing with open pricing.

Run:
  cd backend
  python manage.py test test_sell_us_e2e_flow -v 2
"""
from __future__ import annotations

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from pypdf import PdfWriter
from rest_framework.test import APIClient

from users.models import Artist, Event, Ticket

User = get_user_model()


def _pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


class SellUsE2EFlowTest(TestCase):
    """Console-friendly E2E: API catalog + multipart ticket create (US = active)."""

    def setUp(self):
        self.client = APIClient()
        self.client.enforce_csrf_checks = False
        future = timezone.now() + timedelta(days=180)
        self.artist = Artist.objects.create(name='Taylor Swift E2E')
        self.event_us = Event.objects.create(
            name='Taylor Swift — USA Stadium (E2E)',
            artist=self.artist,
            date=future,
            venue='אחר',
            city='Nashville',
            country='US',
            category='concert',
        )
        self.seller = User.objects.create_user(
            username='sell_e2e_seller',
            password='testpass123',
            email='sell_e2e@test.com',
            role='seller',
        )

    def test_sell_dropdown_catalog_and_us_ticket_goes_live(self):
        # --- 1) Global for_sell list includes zero-inventory event ---
        r_all = self.client.get('/api/users/events/', {'for_sell': '1'})
        self.assertEqual(r_all.status_code, 200)
        data_all = r_all.json()
        rows_all = data_all if isinstance(data_all, list) else data_all.get('results', [])
        ids_all = [e['id'] for e in rows_all]
        self.assertIn(
            self.event_us.id,
            ids_all,
            'for_sell=1 must include upcoming events with no tickets (Sell catalog)',
        )

        # --- 2) Artist-scoped list (same query Sell.jsx uses after selecting artist) ---
        r_art = self.client.get(
            '/api/users/events/',
            {'for_sell': '1', 'artist': str(self.artist.id)},
        )
        self.assertEqual(r_art.status_code, 200)
        data_art = r_art.json()
        rows = data_art if isinstance(data_art, list) else data_art.get('results', [])
        self.assertTrue(any(e['id'] == self.event_us.id for e in rows), 'Artist filter must return the US event')
        row = next(e for e in rows if e['id'] == self.event_us.id)
        self.assertEqual(row.get('country'), 'US')
        self.assertEqual(row.get('tickets_count'), 0)  # no inventory yet
        artist_key = row.get('artist')
        self.assertTrue(
            artist_key == self.artist.id or (row.get('artist_detail') or {}).get('id') == self.artist.id,
            'Response must expose artist id for dropdown matching',
        )

        print('\n=== Sell US E2E — API catalog OK ===')
        print(f"  for_sell global contains event #{self.event_us.id}: {self.event_us.id in ids_all}")
        print(f"  for_sell+artist contains event: {any(e['id'] == self.event_us.id for e in rows)}")
        print(f"  tickets_count: {row.get('tickets_count')}")

        # --- 3) Seller creates ticket: open pricing, no receipt (US) → active ---
        b = _pdf_bytes()
        pdf = SimpleUploadedFile('ticket.pdf', b, content_type='application/pdf')
        self.client.force_authenticate(self.seller)
        r_ticket = self.client.post(
            '/api/users/tickets/',
            {
                'event_id': self.event_us.id,
                'original_price': '100',
                'listing_price': '5000',
                'available_quantity': '1',
                'pdf_files_count': '1',
                'pdf_file_0': pdf,
            },
            format='multipart',
        )
        self.assertEqual(r_ticket.status_code, 201, getattr(r_ticket, 'data', r_ticket.content))
        tid = r_ticket.data['id']
        ticket = Ticket.objects.get(pk=tid)
        self.assertEqual(ticket.status, 'active')
        self.assertEqual(str(ticket.event_id), str(self.event_us.id))

        pub = self.client.get(f'/api/users/events/{self.event_us.id}/tickets/')
        self.assertEqual(pub.status_code, 200)
        pub_ids = [x['id'] for x in pub.data] if isinstance(pub.data, list) else []
        self.assertIn(tid, pub_ids, 'US listing must appear on public event tickets immediately')

        print('=== Sell US E2E — ticket created ===')
        print(f"  ticket id={tid} status={ticket.status}")
        print(f"  listed on event page: {tid in pub_ids}")
        print('=== Sell US E2E — PASS ===\n')
