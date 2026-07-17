"""Unit tests for Shomer Shabbat payment gating."""
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from users.shabbat import (
    HAVDALAH_BUFFER,
    SHABBAT_RESTRICTION_CODE,
    ShabbatWindow,
    _extract_window_from_hebcal_payload,
    clear_shabbat_cache,
    get_shabbat_status,
    shabbat_forbidden_response,
    shabbat_status_view,
)

TZ_IL = ZoneInfo('Asia/Jerusalem')


def _sample_hebcal_payload(candles: datetime, havdalah: datetime) -> dict:
    return {
        'items': [
            {
                'title': 'Candle lighting',
                'date': candles.isoformat(),
                'category': 'candles',
            },
            {
                'title': 'Havdalah',
                'date': havdalah.isoformat(),
                'category': 'havdalah',
            },
        ]
    }


class ShabbatWindowTests(SimpleTestCase):
    def setUp(self):
        clear_shabbat_cache()
        cache.clear()

    def tearDown(self):
        clear_shabbat_cache()
        cache.clear()

    def test_extract_applies_five_minute_havdalah_buffer(self):
        candles = datetime(2026, 7, 17, 19, 10, tzinfo=TZ_IL)
        havdalah = datetime(2026, 7, 18, 20, 20, tzinfo=TZ_IL)
        window = _extract_window_from_hebcal_payload(_sample_hebcal_payload(candles, havdalah))
        self.assertEqual(window.havdalah, havdalah)
        self.assertEqual(window.havdalah_buffered, havdalah + HAVDALAH_BUFFER)
        self.assertEqual(HAVDALAH_BUFFER, timedelta(minutes=5))

    def test_contains_true_during_shabbat_and_buffer(self):
        candles = datetime(2026, 7, 17, 19, 10, tzinfo=TZ_IL)
        havdalah = datetime(2026, 7, 18, 20, 20, tzinfo=TZ_IL)
        window = ShabbatWindow(
            candle_lighting=candles,
            havdalah=havdalah,
            havdalah_buffered=havdalah + HAVDALAH_BUFFER,
        )
        self.assertTrue(window.contains(candles))
        self.assertTrue(window.contains(havdalah + timedelta(minutes=2)))
        self.assertFalse(window.contains(havdalah + timedelta(minutes=5)))
        self.assertFalse(window.contains(candles - timedelta(minutes=1)))

    @patch('users.shabbat._fetch_hebcal_window')
    def test_status_and_forbidden_response_during_shabbat(self, mock_fetch):
        candles = datetime(2026, 7, 17, 19, 10, tzinfo=TZ_IL)
        havdalah = datetime(2026, 7, 18, 20, 20, tzinfo=TZ_IL)
        mock_fetch.return_value = ShabbatWindow(
            candle_lighting=candles,
            havdalah=havdalah,
            havdalah_buffered=havdalah + HAVDALAH_BUFFER,
        )
        mid = candles + timedelta(hours=2)
        info = get_shabbat_status(now=mid)
        self.assertTrue(info['is_shabbat'])
        self.assertEqual(info['havdalah_time'], (havdalah + HAVDALAH_BUFFER).isoformat())
        self.assertEqual(info['havdalah_buffer_minutes'], 5)

        resp = shabbat_forbidden_response(now=mid)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['code'], SHABBAT_RESTRICTION_CODE)
        self.assertEqual(resp.data['havdalah_time'], (havdalah + HAVDALAH_BUFFER).isoformat())

    @patch('users.shabbat._fetch_hebcal_window')
    def test_not_blocked_after_buffered_havdalah(self, mock_fetch):
        candles = datetime(2026, 7, 17, 19, 10, tzinfo=TZ_IL)
        havdalah = datetime(2026, 7, 18, 20, 20, tzinfo=TZ_IL)
        mock_fetch.return_value = ShabbatWindow(
            candle_lighting=candles,
            havdalah=havdalah,
            havdalah_buffered=havdalah + HAVDALAH_BUFFER,
        )
        after = havdalah + timedelta(minutes=5, seconds=1)
        self.assertFalse(get_shabbat_status(now=after)['is_shabbat'])
        self.assertIsNone(shabbat_forbidden_response(now=after))

    @patch('users.shabbat.requests.get')
    def test_hebcal_failure_uses_cache_when_available(self, mock_get):
        candles = datetime(2026, 7, 17, 19, 10, tzinfo=TZ_IL)
        havdalah = datetime(2026, 7, 18, 20, 20, tzinfo=TZ_IL)
        # Prime cache via successful extract path
        from users.shabbat import CACHE_KEY_TIMES, _window_to_cache_dict

        window = ShabbatWindow(
            candle_lighting=candles,
            havdalah=havdalah,
            havdalah_buffered=havdalah + HAVDALAH_BUFFER,
        )
        cache.set(CACHE_KEY_TIMES, _window_to_cache_dict(window), 3600)
        mock_get.side_effect = RuntimeError('network down')

        # force_refresh=False should hit cache without calling network
        from users.shabbat import get_shabbat_window

        got = get_shabbat_window(force_refresh=False)
        self.assertEqual(got.havdalah_buffered, window.havdalah_buffered)
        mock_get.assert_not_called()

    def test_status_endpoint_returns_json(self):
        factory = APIRequestFactory()
        candles = datetime(2026, 7, 17, 19, 10, tzinfo=TZ_IL)
        havdalah = datetime(2026, 7, 18, 20, 20, tzinfo=TZ_IL)
        with patch(
            'users.shabbat.get_shabbat_window',
            return_value=ShabbatWindow(
                candle_lighting=candles,
                havdalah=havdalah,
                havdalah_buffered=havdalah + HAVDALAH_BUFFER,
            ),
        ):
            request = factory.get('/users/shabbat/status/')
            response = shabbat_status_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('is_shabbat', response.data)
        self.assertIn('havdalah_time', response.data)
