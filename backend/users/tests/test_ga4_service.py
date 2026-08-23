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
