from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from users.ga4_service import (
    Ga4AuthError,
    Ga4ConfigError,
    _page_kind,
    fetch_ga4_behavior_dashboard,
    fetch_ga4_last_7_days,
    normalize_ga4_property_id,
)

User = get_user_model()


class NormalizeGa4PropertyIdTests(SimpleTestCase):
    def test_accepts_digits_and_properties_prefix(self):
        self.assertEqual(normalize_ga4_property_id(' 512345678 '), '512345678')
        self.assertEqual(normalize_ga4_property_id('properties/512345678'), '512345678')

    def test_rejects_measurement_id_and_blank(self):
        with self.assertRaises(Ga4ConfigError):
            normalize_ga4_property_id('G-D0P22V9YLH')
        with self.assertRaises(Ga4ConfigError):
            normalize_ga4_property_id('')
        with self.assertRaises(Ga4ConfigError):
            normalize_ga4_property_id('abc')


class FetchGa4Last7DaysTests(SimpleTestCase):
    def test_maps_run_report_metrics(self):
        row = SimpleNamespace(
            metric_values=[
                SimpleNamespace(value='120'),
                SimpleNamespace(value='45'),
                SimpleNamespace(value='300'),
            ]
        )
        fake_response = SimpleNamespace(rows=[row])
        fake_client = MagicMock()
        fake_client.run_report.return_value = fake_response
        fake_creds = object()

        with (
            patch('users.ga4_service.get_adc_credentials', return_value=fake_creds),
            patch('users.ga4_service.BetaAnalyticsDataClient', return_value=fake_client) as client_cls,
        ):
            result = fetch_ga4_last_7_days(property_id='512345678')

        client_cls.assert_called_once_with(credentials=fake_creds)
        request = fake_client.run_report.call_args.args[0]
        self.assertEqual(request.property, 'properties/512345678')
        self.assertEqual(request.date_ranges[0].start_date, '7daysAgo')
        self.assertEqual(request.date_ranges[0].end_date, 'today')
        self.assertEqual([m.name for m in request.metrics], ['sessions', 'activeUsers', 'screenPageViews'])
        self.assertEqual(
            result,
            {
                'property_id': '512345678',
                'date_range': {'start_date': '7daysAgo', 'end_date': 'today'},
                'sessions': 120,
                'active_users': 45,
                'page_views': 300,
            },
        )

    def test_empty_rows_are_zeros(self):
        fake_client = MagicMock()
        fake_client.run_report.return_value = SimpleNamespace(rows=[])
        with (
            patch('users.ga4_service.get_adc_credentials', return_value=object()),
            patch('users.ga4_service.BetaAnalyticsDataClient', return_value=fake_client),
        ):
            result = fetch_ga4_last_7_days(property_id='1')
        self.assertEqual(result['sessions'], 0)
        self.assertEqual(result['active_users'], 0)
        self.assertEqual(result['page_views'], 0)

    def test_auth_error_when_adc_missing(self):
        with patch(
            'users.ga4_service.get_adc_credentials',
            side_effect=Ga4AuthError('No Application Default Credentials.'),
        ):
            with self.assertRaises(Ga4AuthError):
                fetch_ga4_last_7_days(property_id='1')


class FetchGa4OverviewCommandTests(SimpleTestCase):
    def test_command_prints_totals(self):
        payload = {
            'property_id': '512345678',
            'date_range': {'start_date': '7daysAgo', 'end_date': 'today'},
            'sessions': 10,
            'active_users': 4,
            'page_views': 22,
        }
        with patch('users.management.commands.fetch_ga4_overview.fetch_ga4_last_7_days', return_value=payload):
            call_command('fetch_ga4_overview', property_id='512345678')

    def test_command_surfaces_config_errors(self):
        with patch(
            'users.management.commands.fetch_ga4_overview.fetch_ga4_last_7_days',
            side_effect=Ga4ConfigError('GA4_PROPERTY_ID is not set.'),
        ):
            with self.assertRaises(CommandError):
                call_command('fetch_ga4_overview')


@override_settings(GA4_PROPERTY_ID='512345678')
class AdminGa4OverviewViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username='ga4-admin',
            email='ga4-admin@example.test',
            password='pass-12345',
            is_staff=True,
        )
        self.buyer = User.objects.create_user(
            username='ga4-buyer',
            email='ga4-buyer@example.test',
            password='pass-12345',
            role='buyer',
        )

    def test_staff_gets_overview(self):
        payload = {
            'property_id': '512345678',
            'date_range': {'start_date': '7daysAgo', 'end_date': 'today'},
            'sessions': 8,
            'active_users': 3,
            'page_views': 19,
        }
        self.client.force_authenticate(user=self.staff)
        with patch('users.ga4_views.fetch_ga4_last_7_days', return_value=payload):
            res = self.client.get('/api/users/admin/ga4-overview/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['sessions'], 8)
        self.assertEqual(res.data['active_users'], 3)
        self.assertEqual(res.data['page_views'], 19)

    def test_non_staff_is_forbidden(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.get('/api/users/admin/ga4-overview/')
        self.assertEqual(res.status_code, 403)


def _metric_row(*values, dimensions=None):
    return SimpleNamespace(
        metric_values=[SimpleNamespace(value=str(v)) for v in values],
        dimension_values=[SimpleNamespace(value=str(d)) for d in (dimensions or [])],
    )


def _report(*rows):
    return SimpleNamespace(rows=list(rows))


def _string_filter_values(expr):
    values = []
    if expr is None:
        return values
    filt = getattr(expr, 'filter', None)
    if filt is not None and getattr(filt, 'string_filter', None) and filt.string_filter.value:
        values.append(filt.string_filter.value)
    or_group = getattr(expr, 'or_group', None)
    if or_group is not None:
        for child in or_group.expressions:
            values.extend(_string_filter_values(child))
    and_group = getattr(expr, 'and_group', None)
    if and_group is not None:
        for child in and_group.expressions:
            values.extend(_string_filter_values(child))
    return values


class PageKindTests(SimpleTestCase):
    def test_distinguishes_event_from_event_group_and_ticket(self):
        self.assertEqual(_page_kind('/event/coldplay'), 'event')
        self.assertEqual(_page_kind('/event-group/Coldplay'), 'event_group')
        self.assertEqual(_page_kind('/artist/12'), 'artist')
        self.assertEqual(_page_kind('/ticket/99?seat=1'), 'ticket')
        self.assertEqual(_page_kind('/sell/new'), 'sell')
        self.assertEqual(_page_kind('/'), 'home')


class FetchGa4BehaviorDashboardTests(SimpleTestCase):
    def test_maps_multiple_reports_and_funnel_filters(self):
        totals = _report(_metric_row(100, 40, 250, 55, 0.42, 95.5, 0.55))
        marketplace = _report(
            _metric_row(80, 50, 0.3, 120, dimensions=['/event/coldplay', 'Coldplay']),
            _metric_row(20, 15, 0.5, 40, dimensions=['/artist/12', 'Artist 12']),
            _metric_row(10, 8, 0.2, 60, dimensions=['/ticket/9', 'Ticket 9']),
        )
        home = _report(_metric_row(80))
        ticket_details = _report(_metric_row(60))
        begin_checkout = _report(_metric_row(20))
        purchase = _report(_metric_row(8))
        sell_new = _report(_metric_row(30))
        generate_lead = _report(_metric_row(6))

        fake_client = MagicMock()
        fake_client.run_report.side_effect = [
            totals,
            marketplace,
            home,
            ticket_details,
            begin_checkout,
            purchase,
            sell_new,
            generate_lead,
        ]
        fake_creds = object()

        with (
            patch('users.ga4_service.get_adc_credentials', return_value=fake_creds),
            patch('users.ga4_service.BetaAnalyticsDataClient', return_value=fake_client) as client_cls,
        ):
            result = fetch_ga4_behavior_dashboard(property_id='512345678')

        client_cls.assert_called_once_with(credentials=fake_creds)
        self.assertEqual(fake_client.run_report.call_count, 8)

        requests = [call.args[0] for call in fake_client.run_report.call_args_list]
        self.assertEqual(
            [m.name for m in requests[0].metrics],
            [
                'sessions',
                'activeUsers',
                'screenPageViews',
                'engagedSessions',
                'bounceRate',
                'averageSessionDuration',
                'engagementRate',
            ],
        )
        marketplace_paths = _string_filter_values(requests[1].dimension_filter)
        self.assertIn('/event', marketplace_paths)
        self.assertIn('/artist', marketplace_paths)
        self.assertIn('/ticket', marketplace_paths)
        self.assertEqual(_string_filter_values(requests[2].dimension_filter), ['/'])
        ticket_detail_paths = _string_filter_values(requests[3].dimension_filter)
        self.assertIn('/event', ticket_detail_paths)
        self.assertIn('/ticket', ticket_detail_paths)
        self.assertNotIn('/artist', ticket_detail_paths)
        self.assertEqual(_string_filter_values(requests[4].dimension_filter), ['begin_checkout'])
        self.assertEqual(_string_filter_values(requests[5].dimension_filter), ['purchase'])
        sell_paths = _string_filter_values(requests[6].dimension_filter)
        self.assertTrue(any(v == '/sell/new' or v.startswith('/sell/new/') for v in sell_paths))
        self.assertNotIn('/sell', sell_paths)
        self.assertEqual(_string_filter_values(requests[7].dimension_filter), ['generate_lead'])

        self.assertEqual(result['sessions'], 100)
        self.assertEqual(result['active_users'], 40)
        self.assertEqual(result['page_views'], 250)
        self.assertEqual(result['engagement']['engaged_sessions'], 55)
        self.assertEqual(result['engagement']['bounce_rate_percent'], 42.0)
        self.assertEqual(result['engagement']['avg_session_duration_seconds'], 95.5)
        self.assertEqual(result['engagement']['engagement_rate_percent'], 55.0)

        kinds = {row['kind'] for row in result['marketplace_pages']}
        self.assertEqual(kinds, {'event', 'artist', 'ticket'})
        self.assertEqual(result['top_pages'], result['marketplace_pages'])

        buyer = result['buyer_funnel']
        self.assertEqual([s['key'] for s in buyer['steps']], ['home', 'ticket_details', 'checkout', 'purchase'])
        self.assertEqual([s['sessions'] for s in buyer['steps']], [80, 60, 20, 8])
        self.assertEqual(buyer['dropoffs'][0]['dropoff_percent'], 25.0)
        self.assertEqual(buyer['dropoffs'][1]['dropoff_percent'], 66.7)
        self.assertEqual(buyer['dropoffs'][2]['dropoff_percent'], 60.0)

        seller = result['seller_funnel']
        self.assertEqual([s['key'] for s in seller['steps']], ['sell_new', 'listing_created'])
        self.assertEqual([s['sessions'] for s in seller['steps']], [30, 6])
        self.assertEqual(seller['dropoffs'][0]['dropoff_percent'], 80.0)
        self.assertEqual(seller['steps'][0]['path'], '/sell/new')
        self.assertEqual(result['limitations']['funnel_type'], 'independent_counts')

    def test_empty_reports_are_zeros_and_null_dropoffs(self):
        empty = _report()
        fake_client = MagicMock()
        fake_client.run_report.side_effect = [empty] * 8
        with (
            patch('users.ga4_service.get_adc_credentials', return_value=object()),
            patch('users.ga4_service.BetaAnalyticsDataClient', return_value=fake_client),
        ):
            result = fetch_ga4_behavior_dashboard(property_id='1')
        self.assertEqual(result['sessions'], 0)
        self.assertEqual(result['marketplace_pages'], [])
        self.assertIsNone(result['buyer_funnel']['dropoffs'][0]['dropoff_percent'])
        self.assertIsNone(result['seller_funnel']['dropoffs'][0]['conversion_percent'])


@override_settings(GA4_PROPERTY_ID='512345678')
class AdminGa4BehaviorViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username='ga4-behavior-admin',
            email='ga4-behavior-admin@example.test',
            password='pass-12345',
            is_staff=True,
        )
        self.buyer = User.objects.create_user(
            username='ga4-behavior-buyer',
            email='ga4-behavior-buyer@example.test',
            password='pass-12345',
            role='buyer',
        )

    def test_staff_gets_behavior_dashboard(self):
        payload = {
            'property_id': '512345678',
            'sessions': 9,
            'buyer_funnel': {'steps': [], 'dropoffs': []},
            'seller_funnel': {'steps': [], 'dropoffs': []},
        }
        self.client.force_authenticate(user=self.staff)
        with patch('users.ga4_views.fetch_ga4_behavior_dashboard', return_value=payload):
            res = self.client.get('/api/users/admin/ga4-behavior/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['sessions'], 9)

    def test_non_staff_is_forbidden(self):
        self.client.force_authenticate(user=self.buyer)
        res = self.client.get('/api/users/admin/ga4-behavior/')
        self.assertEqual(res.status_code, 403)
