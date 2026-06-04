import json
import logging
from unittest.mock import patch

from django.test import TestCase, override_settings


WEBHOOK_URL = '/api/payments/webhook/'
LOGGER_NAME = 'users.grow_views'


class GrowPaymentWebhookTest(TestCase):
    """Rigorous edge-case coverage — endpoint must never return HTTP 500."""

    def _post_raw(self, body=b'', content_type='application/json', **extra):
        return self.client.post(WEBHOOK_URL, data=body, content_type=content_type, **extra)

    def _assert_acknowledged(self, response):
        self.assertNotEqual(
            response.status_code,
            500,
            msg=f'unexpected server error: {getattr(response, "content", b"")!r}',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'received'})

    def test_post_returns_200_without_auth(self):
        response = self.client.post(
            WEBHOOK_URL,
            {'event': 'payment.updated', 'transaction_id': 'txn_123'},
            content_type='application/json',
        )
        self._assert_acknowledged(response)

    def test_empty_json_body_logs_empty_and_returns_200(self):
        with self.assertLogs(LOGGER_NAME, level='INFO') as logs:
            response = self._post_raw(b'', content_type='application/json')
        self._assert_acknowledged(response)
        combined = '\n'.join(logs.output)
        self.assertIn('(empty)', combined)

    def test_empty_object_json(self):
        with self.assertLogs(LOGGER_NAME, level='INFO') as logs:
            response = self._post_raw(b'{}', content_type='application/json')
        self._assert_acknowledged(response)
        self.assertIn('(empty)', '\n'.join(logs.output))

    def test_malformed_json_returns_200_not_500(self):
        with self.assertLogs(LOGGER_NAME, level='WARNING') as logs:
            response = self._post_raw(b'{"broken":', content_type='application/json')
        self._assert_acknowledged(response)
        self.assertTrue(any('invalid JSON' in line for line in logs.output))

    def test_json_null_root(self):
        with self.assertLogs(LOGGER_NAME, level='INFO'):
            response = self._post_raw(b'null', content_type='application/json')
        self._assert_acknowledged(response)

    def test_json_array_root(self):
        response = self._post_raw(
            json.dumps([1, 'x', {'nested': True}]).encode(),
            content_type='application/json',
        )
        self._assert_acknowledged(response)

    def test_json_string_root(self):
        response = self._post_raw(b'"payment-complete"', content_type='application/json')
        self._assert_acknowledged(response)

    def test_json_number_root(self):
        response = self._post_raw(b'42', content_type='application/json')
        self._assert_acknowledged(response)

    def test_json_boolean_root(self):
        response = self._post_raw(b'true', content_type='application/json')
        self._assert_acknowledged(response)

    def test_missing_standard_fields_still_200(self):
        response = self._post_raw(b'{"foo": "bar"}', content_type='application/json')
        self._assert_acknowledged(response)

    def test_unexpected_nested_and_mixed_types(self):
        payload = {
            'status': 123,
            'flags': [True, None, 0],
            'meta': {'retry': 'yes', 'amount': '12.50'},
            'weird': {'a': {'b': {'c': [1, 2, 3]}}},
        }
        response = self.client.post(
            WEBHOOK_URL,
            payload,
            content_type='application/json',
        )
        self._assert_acknowledged(response)

    def test_unicode_and_special_characters(self):
        response = self._post_raw(
            json.dumps({'event': 'תשלום', 'note': '€ — ✓'}).encode('utf-8'),
            content_type='application/json; charset=utf-8',
        )
        self._assert_acknowledged(response)

    def test_invalid_utf8_body(self):
        with self.assertLogs(LOGGER_NAME, level='WARNING') as logs:
            response = self._post_raw(b'\xff\xfe{"a":1}', content_type='application/json')
        self._assert_acknowledged(response)
        self.assertTrue(
            any('UTF-8' in line or 'invalid' in line.lower() for line in logs.output)
        )

    def test_plain_text_body_without_json_content_type(self):
        response = self._post_raw(b'not-json-at-all', content_type='text/plain')
        self._assert_acknowledged(response)

    def test_form_urlencoded_empty(self):
        response = self._post_raw(b'', content_type='application/x-www-form-urlencoded')
        self._assert_acknowledged(response)

    def test_large_json_payload(self):
        big = {'items': [{'id': i, 'ok': True} for i in range(500)]}
        response = self.client.post(WEBHOOK_URL, big, content_type='application/json')
        self._assert_acknowledged(response)

    def test_get_method_not_allowed_not_500(self):
        response = self.client.get(WEBHOOK_URL)
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(response.status_code, 405)

    @override_settings(DEBUG=True)
    def test_internal_exception_still_returns_200(self):
        with patch(
            'users.grow_views._safe_parse_grow_body',
            side_effect=RuntimeError('simulated failure'),
        ):
            with self.assertLogs(LOGGER_NAME, level='ERROR') as logs:
                response = self._post_raw(b'{"ok": true}', content_type='application/json')
        self._assert_acknowledged(response)
        self.assertTrue(any('unexpected error' in line for line in logs.output))

    def test_payload_for_log_helper_empty_cases(self):
        from users.grow_views import _payload_for_log

        self.assertEqual(_payload_for_log(None), '(empty)')
        self.assertEqual(_payload_for_log({}), '(empty)')
        self.assertEqual(_payload_for_log([]), '(empty)')

    def test_stress_mixed_edge_cases_sequence(self):
        """Burst of odd payloads — none may produce 500."""
        cases = [
            (b'', 'application/json'),
            (b'   ', 'application/json'),
            (b'[]', 'application/json'),
            (b'{"a":1,}', 'application/json'),
            (json.dumps({'nested': {'x': [None, False, 0]}}).encode(), 'application/json'),
        ]
        for body, ctype in cases:
            with self.subTest(body=body[:40], ctype=ctype):
                response = self._post_raw(body, content_type=ctype)
                self._assert_acknowledged(response)
