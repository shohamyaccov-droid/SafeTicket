"""
Zero information leakage — production (DEBUG=False) API surface.

Guarantees:
- 4xx/5xx responses never include stack traces, SQL, filesystem paths, or PSP payloads.
- Full detail stays in server logs (verified via assertLogs where practical).

Run: python manage.py test users.tests.test_api_error_leakage -v 2
"""
from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from safeticket.exception_handler import sanitize_error_payload
from safeticket.middleware import GlobalExceptionJSONMiddleware
from services.payme_service import PayMeError
from users.models import Artist, Event, Order, Ticket

User = get_user_model()

_LEAK_MARKERS = (
    'traceback',
    'Traceback',
    'File "',
    "File '",
    'site-packages',
    'sqlite3',
    'OperationalError',
    'IntegrityError',
    'django.db',
    'psycopg',
    'SECRET',
    'payme_response',
    'payme_raw',
    'Cloudinary',
    'full traceback',
)


def _assert_no_leak(testcase: TestCase, payload) -> None:
    raw = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    lower = raw.lower()
    for marker in _LEAK_MARKERS:
        testcase.assertNotIn(marker.lower(), lower, msg=f'Leak marker {marker!r} found in: {raw[:800]}')
    testcase.assertNotRegex(raw, r'[A-Za-z]:\\\\Users\\\\', msg=f'Windows path leak: {raw[:400]}')
    testcase.assertNotRegex(raw, r'/home/[^"\s]+/', msg=f'Unix path leak: {raw[:400]}')


def _minimal_pdf_bytes() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


@override_settings(DEBUG=False, SECRET_KEY='leak-test-secret-key-not-for-prod')
class SanitizePayloadUnitTests(TestCase):
    def test_strips_traceback_and_payme_keys(self):
        dirty = {
            'error': 'Failed',
            'traceback': 'Traceback (most recent call last):\n  File "/app/x.py"',
            'payme_response': {'secret': 'abc', 'status_code': 500},
            'payme_raw': {'foo': 1},
            'detail': 'sqlite3.OperationalError: no such table',
            'fields': {'listing_price': ['Must be positive.']},
        }
        clean = sanitize_error_payload(dirty)
        self.assertNotIn('traceback', clean)
        self.assertNotIn('payme_response', clean)
        self.assertNotIn('payme_raw', clean)
        self.assertEqual(clean['fields']['listing_price'], ['Must be positive.'])
        self.assertEqual(clean['detail'], 'Something went wrong. Please try again later.')
        _assert_no_leak(self, clean)


@override_settings(DEBUG=False, SECRET_KEY='leak-test-secret-key-not-for-prod')
class MiddlewareLeakageTests(TestCase):
    def test_process_exception_hides_details_when_debug_false(self):
        factory = RequestFactory()
        request = factory.get('/api/users/events/')
        mw = GlobalExceptionJSONMiddleware(lambda r: None)

        with self.assertLogs('safeticket.middleware', level='ERROR') as logs:
            response = mw.process_exception(
                request,
                RuntimeError('SECRET_DB_DSN=postgres://admin:hunter2@db/prod'),
            )

        self.assertEqual(response.status_code, 500)
        body = json.loads(response.content.decode('utf-8'))
        self.assertEqual(body.get('error'), 'Internal server error')
        self.assertNotIn('hunter2', response.content.decode('utf-8'))
        self.assertNotIn('traceback', body)
        _assert_no_leak(self, body)
        # Full detail must reach the logger
        joined = '\n'.join(logs.output)
        self.assertIn('hunter2', joined)


@override_settings(DEBUG=False, SECRET_KEY='leak-test-secret-key-not-for-prod')
class DrfExceptionHandlerLeakageTests(TestCase):
    def test_unhandled_exception_returns_generic_500(self):
        class BoomView(APIView):
            authentication_classes = []
            permission_classes = []

            def get(self, request):
                raise RuntimeError('SELECT * FROM users_user WHERE password=...')

        factory = APIRequestFactory()
        request = factory.get('/api/boom/')
        view = BoomView.as_view()

        with self.assertLogs('safeticket.exception_handler', level='ERROR'):
            response = view(request)

        self.assertEqual(response.status_code, 500)
        _assert_no_leak(self, response.data)
        self.assertEqual(response.data.get('error'), 'Internal server error')

    def test_validation_error_still_returns_field_messages(self):
        class BadView(APIView):
            authentication_classes = []
            permission_classes = []

            def post(self, request):
                raise ValidationError({'listing_price': ['Must be a positive number.']})

        factory = APIRequestFactory()
        request = factory.post('/api/bad/', {}, format='json')
        response = BadView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['listing_price'], ['Must be a positive number.'])


@override_settings(
    DEBUG=False,
    SECRET_KEY='leak-test-secret-key-not-for-prod',
    PAYME_SELLER_ID='seller_test',
    PAYME_API_URL='https://testpay.payme.io/api',
)
class PaymeInitLeakageTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.buyer = User.objects.create_user(
            username='leak_buyer',
            email='leak_buyer@test.invalid',
            password='x',
            role='buyer',
            first_name='Buyer',
            phone_number='0500000000',
        )
        future = timezone.now() + timedelta(days=30)
        artist = Artist.objects.create(name='Leak Artist')
        self.event = Event.objects.create(
            name='Leak Event',
            artist=artist,
            date=future,
            venue='מקום',
            city='Tel Aviv',
            country='IL',
            category='concert',
        )
        seller = User.objects.create_user(
            username='leak_seller',
            email='leak_seller@test.invalid',
            password='x',
            role='seller',
        )
        self.ticket = Ticket.objects.create(
            seller=seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='available',
            available_quantity=1,
        )
        self.order = Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            status='pending_payment',
            total_amount=Decimal('115.00'),
            total_paid_by_buyer=Decimal('115.00'),
            quantity=1,
            event_name=self.event.name,
            currency='ILS',
        )

    def test_payme_error_does_not_leak_upstream_payload(self):
        self.api.force_authenticate(self.buyer)
        boom = PayMeError(
            'PayMe rejected: invalid seller_payme_id xyz',
            http_status=502,
            payload={'status_error_code': 99, 'status_error_details': 'internal map dump', 'api_key': 'SECRET'},
        )
        with patch('users.payme_views.generate_payme_sale_for_order', side_effect=boom):
            res = self.api.post(
                '/api/users/payments/payme/init/',
                {
                    'order_id': self.order.id,
                    'success_url': 'https://tradetix.co.il/ok',
                    'failure_url': 'https://tradetix.co.il/fail',
                },
                format='json',
            )
        self.assertEqual(res.status_code, 502)
        body = res.json()
        self.assertNotIn('payme_response', body)
        self.assertNotIn('payme_http_status', body)
        self.assertNotIn('SECRET', json.dumps(body))
        self.assertNotIn('seller_payme_id', json.dumps(body))
        self.assertIn('error', body)
        _assert_no_leak(self, body)

    def test_missing_transaction_id_does_not_include_raw(self):
        self.api.force_authenticate(self.buyer)
        with patch(
            'users.payme_views.generate_payme_sale_for_order',
            return_value={'transaction_id': None, 'payme_sale_url': 'https://x', 'raw': {'secret': 'SECRET'}},
        ):
            res = self.api.post(
                '/api/users/payments/payme/init/',
                {
                    'order_id': self.order.id,
                    'success_url': 'https://tradetix.co.il/ok',
                    'failure_url': 'https://tradetix.co.il/fail',
                },
                format='json',
            )
        self.assertEqual(res.status_code, 502)
        body = res.json()
        self.assertNotIn('payme_response', body)
        self.assertNotIn('SECRET', json.dumps(body))
        _assert_no_leak(self, body)


@override_settings(DEBUG=False, SECRET_KEY='leak-test-secret-key-not-for-prod')
class AuthAndValidationLeakageTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def test_login_bad_credentials_no_leak(self):
        res = self.api.post(
            '/api/users/login/',
            {'username': 'nobody@test.invalid', 'password': 'wrong'},
            format='json',
        )
        self.assertIn(res.status_code, (400, 401))
        _assert_no_leak(self, res.json() if res.content else {})

    def test_not_found_ticket_no_leak(self):
        res = self.api.get('/api/users/tickets/99999999/')
        self.assertIn(res.status_code, (404, 403, 401))
        if res.content:
            _assert_no_leak(self, res.json())

    def test_malformed_json_body_no_leak(self):
        res = self.api.post(
            '/api/users/login/',
            data='{"username": ',
            content_type='application/json',
        )
        self.assertIn(res.status_code, (400, 401, 415))
        if res.content:
            try:
                body = res.json()
            except Exception:
                body = {'raw': res.content.decode('utf-8', errors='replace')[:500]}
            _assert_no_leak(self, body)

    def test_huge_payload_rejected_safely(self):
        huge = 'x' * (2 * 1024 * 1024)
        res = self.api.post(
            '/api/users/login/',
            {'username': huge, 'password': 'x'},
            format='json',
        )
        self.assertIn(res.status_code, (400, 401, 413, 500))
        if res.content:
            try:
                body = res.json()
            except Exception:
                body = {'raw': res.content.decode('utf-8', errors='replace')[:500]}
            _assert_no_leak(self, body)


@override_settings(DEBUG=False, SECRET_KEY='leak-test-secret-key-not-for-prod')
class TicketUploadPdfLeakageTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.seller = User.objects.create_user(
            username='pdf_leak_seller',
            email='pdf_leak@test.invalid',
            password='x',
            role='seller',
        )
        future = timezone.now() + timedelta(days=40)
        artist = Artist.objects.create(name='PDF Leak Artist')
        self.event = Event.objects.create(
            name='PDF Leak Event',
            artist=artist,
            date=future,
            venue='מקום',
            city='Tel Aviv',
            country='US',
            category='concert',
        )
        self.api.force_authenticate(self.seller)

    def test_corrupt_pdf_error_omits_exception_text(self):
        bad = SimpleUploadedFile('bad.pdf', b'%PDF-1.4 not-a-real-pdf', content_type='application/pdf')
        res = self.api.post(
            '/api/users/tickets/',
            {
                'event_id': self.event.id,
                'original_price': '100.00',
                'listing_price': '100.00',
                'available_quantity': '2',
                'pdf_files_count': '1',
                'pdf_file_0': bad,
                'delivery_method': 'instant',
            },
            format='multipart',
        )
        # May be 400 (cannot read) — must not embed exception internals
        self.assertIn(res.status_code, (400, 500))
        body = res.json()
        err = str(body.get('error') or body.get('detail') or body)
        self.assertNotIn('(', err)  # we used to append (str(e))
        _assert_no_leak(self, body)


@override_settings(DEBUG=False, SECRET_KEY='leak-test-secret-key-not-for-prod')
class PricingAndCouponEdgeLeakageTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def test_validate_coupon_negative_and_wrong_types(self):
        for payload in (
            {'code': '', 'base_amount': -1},
            {'code': ['array'], 'base_amount': 'nope'},
            {'code': None},
            {'code': 'A' * 5000, 'base_amount': 10**18},
        ):
            res = self.api.post('/api/users/coupons/validate/', payload, format='json')
            self.assertIn(res.status_code, (400, 404, 429), msg=payload)
            if res.content:
                _assert_no_leak(self, res.json())

    def test_pricing_settings_public_and_safe(self):
        res = self.api.get('/api/users/pricing/settings/')
        self.assertEqual(res.status_code, 200)
        body = res.json()
        _assert_no_leak(self, body)
        self.assertTrue(
            any(k in body for k in ('service_fee_percentage', 'base_buyer_fee_percent')),
            msg=f'Unexpected pricing payload keys: {list(body.keys())}',
        )
