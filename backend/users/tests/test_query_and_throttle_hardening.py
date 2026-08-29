"""
N+1 catalog query budgets + public/SMS throttle (anti-scrape / anti-bot).

Run: python manage.py test users.tests.test_query_and_throttle_hardening -v 2
"""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from users.models import Artist, Event, Ticket, User
from users.querysets import (
    EVENT_CATALOG_SELECT_RELATED,
    TICKET_CATALOG_SELECT_RELATED,
    annotate_active_tickets_total,
    event_venue_sections_prefetch,
)
from users.serializers import EventListSerializer, TicketListSerializer


def _rest_framework_with_rates(**rates):
    rf = deepcopy(settings.REST_FRAMEWORK)
    merged = dict(rf.get('DEFAULT_THROTTLE_RATES') or {})
    merged.update(rates)
    rf['DEFAULT_THROTTLE_RATES'] = merged
    return rf


class _CatalogFixtures(APITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.api = APIClient()
        self.now = timezone.now()
        self.seller = User.objects.create_user(
            username='n1_seller',
            email='n1-seller@example.test',
            password='pass-12345',
            role='seller',
        )

    def _seed_events(self, n, *, prefix):
        events = []
        for i in range(n):
            artist = Artist.objects.create(name=f'{prefix} Artist {i}')
            event = Event.objects.create(
                name=f'{prefix} Show {i}',
                artist=artist,
                date=self.now + timedelta(days=7 + i),
                venue='היכל מנורה מבטחים',
                city='Tel Aviv',
                country='IL',
                category='concert',
                status='פעיל',
            )
            Ticket.objects.create(
                seller=self.seller,
                event=event,
                event_name=event.name,
                event_date=event.date,
                venue=event.venue,
                original_price=Decimal('100.00'),
                asking_price=Decimal('100.00'),
                available_quantity=2,
                status='active',
                verification_status='מאומת',
                pdf_file=f'tickets/pdfs/{prefix}-{i}.pdf',
            )
            events.append(event)
        return events


class EventTicketUserQueryOptimizationTests(_CatalogFixtures):
    def test_event_list_serializer_eliminates_n_plus_one(self):
        events = self._seed_events(10, prefix='SerEv')
        ids = [e.pk for e in events]

        with CaptureQueriesContext(connection) as naive:
            naive_rows = list(Event.objects.filter(pk__in=ids))
            EventListSerializer(naive_rows, many=True).data

        with CaptureQueriesContext(connection) as optimized:
            opt_rows = list(
                annotate_active_tickets_total(
                    Event.objects.filter(pk__in=ids)
                    .select_related(*EVENT_CATALOG_SELECT_RELATED)
                    .prefetch_related(event_venue_sections_prefetch())
                )
            )
            EventListSerializer(opt_rows, many=True).data

        self.assertGreater(
            len(naive),
            len(optimized),
            f'expected prefetch/annotate to cut queries ({len(naive)} vs {len(optimized)})',
        )
        # Naive path is ~1 fetch + per-event artist/venue/ticket aggregates.
        self.assertGreaterEqual(len(naive), 10)
        self.assertLessEqual(len(optimized), 4)
        self._event_serializer_naive = len(naive)
        self._event_serializer_opt = len(optimized)

    def test_ticket_list_serializer_eliminates_n_plus_one(self):
        events = self._seed_events(10, prefix='SerTk')
        ids = [e.pk for e in events]

        with CaptureQueriesContext(connection) as naive:
            naive_rows = list(Ticket.objects.filter(event_id__in=ids))
            TicketListSerializer(naive_rows, many=True).data

        with CaptureQueriesContext(connection) as optimized:
            opt_rows = list(
                Ticket.objects.filter(event_id__in=ids).select_related(*TICKET_CATALOG_SELECT_RELATED)
            )
            TicketListSerializer(opt_rows, many=True).data

        self.assertGreater(len(naive), len(optimized))
        self.assertGreaterEqual(len(naive), 10)
        self.assertLessEqual(len(optimized), 3)

    def test_event_list_assert_num_queries_stable_and_flat_as_n_grows(self):
        self._seed_events(4, prefix='EvA')
        self.api.get('/api/users/events/')
        with CaptureQueriesContext(connection) as small:
            res_small = self.api.get('/api/users/events/')
        self.assertEqual(res_small.status_code, 200, res_small.content)
        small_n = len(small)

        with self.assertNumQueries(small_n):
            res_repeat = self.api.get('/api/users/events/')
        self.assertEqual(res_repeat.status_code, 200)

        self._seed_events(12, prefix='EvB')
        self.api.get('/api/users/events/')
        with CaptureQueriesContext(connection) as large:
            res_large = self.api.get('/api/users/events/')
        self.assertEqual(res_large.status_code, 200, res_large.content)
        large_n = len(large)

        with self.assertNumQueries(large_n):
            self.api.get('/api/users/events/')

        self.assertLessEqual(
            large_n,
            small_n + 2,
            f'event list queries grew with catalog size ({small_n} -> {large_n})',
        )
        self.assertLessEqual(large_n, 18)

    def test_ticket_list_assert_num_queries_stable_and_flat_as_n_grows(self):
        self._seed_events(4, prefix='TkA')
        self.api.get('/api/users/tickets/')
        with CaptureQueriesContext(connection) as small:
            res_small = self.api.get('/api/users/tickets/')
        self.assertEqual(res_small.status_code, 200, res_small.content)
        small_n = len(small)

        with self.assertNumQueries(small_n):
            self.api.get('/api/users/tickets/')

        self._seed_events(10, prefix='TkB')
        self.api.get('/api/users/tickets/')
        with CaptureQueriesContext(connection) as large:
            res_large = self.api.get('/api/users/tickets/')
        self.assertEqual(res_large.status_code, 200, res_large.content)
        large_n = len(large)

        with self.assertNumQueries(large_n):
            self.api.get('/api/users/tickets/')

        self.assertLessEqual(
            large_n,
            small_n + 2,
            f'ticket list queries grew with catalog size ({small_n} -> {large_n})',
        )
        self.assertLessEqual(large_n, 20)

    def test_event_tickets_assert_num_queries_stable_as_listings_grow(self):
        event = self._seed_events(1, prefix='EvTk')[0]
        for i in range(5):
            Ticket.objects.create(
                seller=self.seller,
                event=event,
                event_name=event.name,
                event_date=event.date,
                venue=event.venue,
                original_price=Decimal('80.00'),
                asking_price=Decimal('80.00'),
                available_quantity=1,
                status='active',
                verification_status='מאומת',
                pdf_file=f'tickets/pdfs/evtk-extra-{i}.pdf',
            )
        url = f'/api/users/events/{event.pk}/tickets/'
        self.api.get(url)
        with CaptureQueriesContext(connection) as small:
            res = self.api.get(url)
        self.assertEqual(res.status_code, 200, res.content)
        small_n = len(small)

        with self.assertNumQueries(small_n):
            self.api.get(url)

        for i in range(8):
            Ticket.objects.create(
                seller=self.seller,
                event=event,
                event_name=event.name,
                event_date=event.date,
                venue=event.venue,
                original_price=Decimal('90.00'),
                asking_price=Decimal('90.00'),
                available_quantity=1,
                status='active',
                verification_status='מאומת',
                pdf_file=f'tickets/pdfs/evtk-more-{i}.pdf',
            )
        self.api.get(url)
        with CaptureQueriesContext(connection) as large:
            res = self.api.get(url)
        self.assertEqual(res.status_code, 200, res.content)
        large_n = len(large)

        with self.assertNumQueries(large_n):
            self.api.get(url)

        self.assertLessEqual(
            large_n,
            small_n + 2,
            f'event tickets queries grew with listing count ({small_n} -> {large_n})',
        )
        self.assertLessEqual(large_n, 22)

    def test_dashboard_listings_assert_num_queries_flat_as_n_grows(self):
        self.api.force_authenticate(self.seller)
        self._seed_events(4, prefix='DashA')
        self.api.get('/api/users/dashboard/')
        with CaptureQueriesContext(connection) as small:
            res = self.api.get('/api/users/dashboard/')
        self.assertEqual(res.status_code, 200, res.content)
        small_n = len(small)

        with self.assertNumQueries(small_n):
            self.api.get('/api/users/dashboard/')

        self._seed_events(8, prefix='DashB')
        self.api.get('/api/users/dashboard/')
        with CaptureQueriesContext(connection) as large:
            res = self.api.get('/api/users/dashboard/')
        self.assertEqual(res.status_code, 200, res.content)
        large_n = len(large)

        with self.assertNumQueries(large_n):
            self.api.get('/api/users/dashboard/')

        self.assertLessEqual(
            large_n,
            small_n + 2,
            f'dashboard queries grew with listing count ({small_n} -> {large_n})',
        )


class PublicCatalogAndSmsThrottleTests(_CatalogFixtures):
    def _burst(self, n, factory):
        statuses = []
        for i in range(n):
            statuses.append(factory(i).status_code)
        return statuses

    @override_settings(REST_FRAMEWORK=_rest_framework_with_rates(public_catalog='8/minute'))
    def test_bot_burst_on_event_list_is_throttled(self):
        cache.clear()
        self._seed_events(1, prefix='ThrEv')
        statuses = self._burst(100, lambda _i: self.api.get('/api/users/events/'))
        allowed = statuses.count(200)
        blocked = statuses.count(429)
        self.assertEqual(allowed, 8, statuses[:20])
        self.assertEqual(blocked, 92)
        self.assertTrue(all(s in (200, 429) for s in statuses))

    @override_settings(REST_FRAMEWORK=_rest_framework_with_rates(public_catalog='8/minute'))
    def test_bot_burst_on_ticket_list_is_throttled(self):
        cache.clear()
        self._seed_events(1, prefix='ThrTk')
        statuses = self._burst(100, lambda _i: self.api.get('/api/users/tickets/'))
        self.assertEqual(statuses.count(200), 8, statuses[:20])
        self.assertEqual(statuses.count(429), 92)

    @override_settings(REST_FRAMEWORK=_rest_framework_with_rates(sms_verification='5/minute'))
    def test_bot_burst_on_sms_verification_is_throttled(self):
        cache.clear()
        statuses = self._burst(
            100,
            lambda i: self.api.post(
                '/api/users/sms/request/',
                {'phone': f'0501234{i:03d}'},
                format='json',
            ),
        )
        self.assertEqual(statuses.count(200), 5, statuses[:20])
        self.assertEqual(statuses.count(429), 95)
        self.assertTrue(all(s in (200, 429) for s in statuses))

    def test_sms_request_rejects_invalid_phone_without_sending(self):
        cache.clear()
        res = self.api.post('/api/users/sms/request/', {'phone': '12'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.data.get('sent'))
