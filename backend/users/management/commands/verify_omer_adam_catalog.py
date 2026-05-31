"""
Self-verification for Omer Adam / Ramat Gan catalog and Sell-page API contract.

Usage:
  cd backend
  python manage.py verify_omer_adam_catalog
  python manage.py verify_omer_adam_catalog --api-base https://safeticket-api.onrender.com/api
"""

from __future__ import annotations

import sys
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.utils import timezone

from users.models import Artist, Event
from users.views import ArtistViewSet, EventViewSet

ARTIST_NAME = 'עומר אדם'
VENUE_SUBSTR = 'רמת גן'
RAMAT_GAN_TITLE_SUBSTR = 'אצטדיון רמת גן'


class Command(BaseCommand):
    help = 'Verify Omer Adam artist/events in DB and for_sell API responses (Sell dropdown contract).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-base',
            type=str,
            default='',
            help='Optional remote API base (e.g. https://safeticket-api.onrender.com/api) for HTTP checks.',
        )

    def handle(self, *args, **options):
        ok = True
        now = timezone.now()

        self.stdout.write(self.style.HTTP_INFO('=== 1) DATABASE: Artist ==='))
        artists = list(Artist.objects.filter(name=ARTIST_NAME).order_by('id'))
        if not artists:
            ok = False
            self.stdout.write(self.style.ERROR(f'FAIL: No Artist named {ARTIST_NAME!r}'))
        else:
            for a in artists:
                self.stdout.write(f'  OK artist id={a.pk} name={a.name!r}')

        self.stdout.write(self.style.HTTP_INFO('=== 2) DATABASE: Events (Ramat Gan + all Omer concerts) ==='))
        omer_events = list(
            Event.objects.filter(artist__name=ARTIST_NAME, date__gte=now)
            .select_related('artist', 'venue_place')
            .order_by('date')
        )
        ramat_gan = [
            e
            for e in omer_events
            if RAMAT_GAN_TITLE_SUBSTR in (e.name or '')
            or (e.venue_place and VENUE_SUBSTR in (e.venue_place.name or ''))
        ]
        self.stdout.write(f'  Upcoming Omer events: {len(omer_events)}')
        for e in omer_events:
            vp = e.venue_place.name if e.venue_place else '(no venue_place)'
            self.stdout.write(
                f'    id={e.pk} date={e.date.isoformat()} category={e.category!r} '
                f'status={e.status!r} high_demand={e.high_demand} venue_place={vp!r} name={e.name!r}'
            )
        if len(ramat_gan) < 4:
            ok = False
            self.stdout.write(
                self.style.ERROR(
                    f'FAIL: Expected >=4 upcoming Ramat Gan shows, found {len(ramat_gan)}. '
                    f'Run: python manage.py seed_omer_adam'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f'  OK Ramat Gan shows: {len(ramat_gan)}'))

        for e in omer_events:
            if not e.artist_id:
                ok = False
                self.stdout.write(self.style.ERROR(f'FAIL: Event id={e.pk} has no artist_id'))

        self.stdout.write(self.style.HTTP_INFO('=== 3) LOCAL API: ArtistViewSet list ==='))
        rf = RequestFactory()

        def _artist_names(for_sell: bool) -> list[str]:
            params = {'for_sell': '1'} if for_sell else {}
            req = rf.get('/api/users/artists/', params)
            view = ArtistViewSet.as_view({'get': 'list'})
            resp = view(req)
            return [row['name'] for row in resp.data]

        default_names = _artist_names(False)
        sell_names = _artist_names(True)
        self.stdout.write(f'  GET /artists/ (inventory only): {default_names!r}')
        self.stdout.write(f'  GET /artists/?for_sell=1: {sell_names!r}')
        if ARTIST_NAME not in sell_names:
            ok = False
            self.stdout.write(self.style.ERROR(f'FAIL: {ARTIST_NAME!r} missing from for_sell artist list'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  OK {ARTIST_NAME!r} in for_sell artist list'))

        self.stdout.write(self.style.HTTP_INFO('=== 4) LOCAL API: EventViewSet for_sell per artist ==='))
        if artists:
            aid = artists[0].pk
            req = rf.get(f'/api/users/events/?for_sell=1&artist={aid}')
            view = EventViewSet.as_view({'get': 'list'})
            resp = view(req)
            names = [row.get('name') for row in resp.data]
            self.stdout.write(f'  GET /events/?for_sell=1&artist={aid}: {len(names)} row(s)')
            for n in names:
                self.stdout.write(f'    - {n}')
            if not names:
                ok = False
                self.stdout.write(self.style.ERROR('FAIL: No events for Omer with for_sell=1'))

        api_base = (options.get('api_base') or '').strip().rstrip('/')
        if api_base:
            self.stdout.write(self.style.HTTP_INFO(f'=== 5) REMOTE HTTP: {api_base} ==='))
            ok = self._check_remote(api_base, ok)

        if ok:
            self.stdout.write(self.style.SUCCESS('VERIFY: ALL CHECKS PASSED'))
        else:
            self.stdout.write(self.style.ERROR('VERIFY: ONE OR MORE CHECKS FAILED'))
            sys.exit(1)

    def _check_remote(self, api_base: str, ok: bool) -> bool:
        artists_url = urljoin(api_base + '/', 'users/artists/')
        try:
            inv = requests.get(artists_url, timeout=30)
            sell = requests.get(artists_url, params={'for_sell': '1'}, timeout=30)
            inv.raise_for_status()
            sell.raise_for_status()
        except requests.RequestException as exc:
            self.stdout.write(self.style.ERROR(f'FAIL remote HTTP: {exc}'))
            return False

        inv_names = [a.get('name') for a in inv.json()]
        sell_names = [a.get('name') for a in sell.json()]
        self.stdout.write(f'  remote GET /artists/: {inv_names!r}')
        self.stdout.write(f'  remote GET /artists/?for_sell=1: {sell_names!r}')
        if ARTIST_NAME not in sell_names:
            ok = False
            self.stdout.write(self.style.ERROR(f'FAIL remote: {ARTIST_NAME!r} not in for_sell list'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  OK remote for_sell includes {ARTIST_NAME!r}'))

        omer_id = next((a['id'] for a in sell.json() if a.get('name') == ARTIST_NAME), None)
        if omer_id:
            ev_url = urljoin(api_base + '/', 'users/events/')
            ev_res = requests.get(ev_url, params={'for_sell': '1', 'artist': omer_id}, timeout=30)
            ev_res.raise_for_status()
            ev_rows = ev_res.json()
            self.stdout.write(f'  remote events for artist {omer_id}: {len(ev_rows)}')
            for row in ev_rows:
                self.stdout.write(f'    - {row.get("name")} @ {row.get("date")}')
            rg = [r for r in ev_rows if RAMAT_GAN_TITLE_SUBSTR in (r.get('name') or '')]
            if len(rg) < 4:
                ok = False
                self.stdout.write(
                    self.style.ERROR(
                        f'FAIL remote: only {len(rg)} Ramat Gan show(s); deploy seed_omer_adam on production'
                    )
                )
        return ok
