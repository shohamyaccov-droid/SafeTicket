"""
E2E Browser Simulation: Strictly simulates a real browser's CORS preflight and requests.
  - Preflight: OPTIONS with Origin + Access-Control-Request-Method
  - Login: POST with Origin, assert 200 and HttpOnly cookies
  - Protected fetch: GET /profile/ with cookies, assert 200

Run: python manage.py test test_e2e_browser_simulation -v 2
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()

ORIGIN = 'http://localhost:3000'


class E2EBrowserSimulationTest(TestCase):
    """Simulates real browser CORS negotiation and login flow."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='browser_user',
            email='browser@test.com',
            password='SecurePass123!',
            role='buyer',
        )

    def test_1_preflight_returns_cors_headers(self):
        """
        OPTIONS /api/users/login/ with Origin and Access-Control-Request-Method.
        Assert 200, Access-Control-Allow-Origin, Access-Control-Allow-Credentials.
        """
        r = self.client.options(
            '/api/users/login/',
            HTTP_ORIGIN=ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='Content-Type',
        )
        self.assertEqual(r.status_code, 200, f'Preflight must return 200. Got: {r.status_code}')
        headers_lower = {k.lower(): v for k, v in r.items()}
        self.assertIn(
            'access-control-allow-origin',
            headers_lower,
            f'Response must include Access-Control-Allow-Origin. Headers: {list(headers_lower.keys())}',
        )
        allow_origin = headers_lower.get('access-control-allow-origin')
        self.assertEqual(
            allow_origin, ORIGIN,
            f'Access-Control-Allow-Origin must match origin. Got: {allow_origin}',
        )
        allow_creds = headers_lower.get('access-control-allow-credentials')
        self.assertEqual(
            allow_creds, 'true',
            f'Access-Control-Allow-Credentials must be true. Got: {allow_creds}',
        )

    def test_2_login_with_origin_sets_cookies(self):
        """
        POST /api/users/login/ with HTTP_ORIGIN and valid credentials.
        Assert 200 OK and HttpOnly cookies (access_token, refresh_token).
        """
        r = self.client.post(
            '/api/users/login/',
            {'username': 'browser_user', 'password': 'SecurePass123!'},
            format='json',
            HTTP_ORIGIN=ORIGIN,
        )
        self.assertEqual(r.status_code, 200, f'Login must return 200. Got: {r.status_code}. Body: {r.content.decode()}')
        self.assertIn('access_token', r.cookies, 'Login must set access_token cookie')
        self.assertIn('refresh_token', r.cookies, 'Login must set refresh_token cookie')
        for name in ('access_token', 'refresh_token'):
            out = r.cookies[name].output().lower()
            self.assertIn('httponly', out, f'{name} cookie must have HttpOnly. Got: {out}')

    def test_3_protected_fetch_with_cookies_succeeds(self):
        """
        Login, then GET /api/users/profile/ with cookies.
        Assert 200 OK.
        """
        # Login first
        r1 = self.client.post(
            '/api/users/login/',
            {'username': 'browser_user', 'password': 'SecurePass123!'},
            format='json',
            HTTP_ORIGIN=ORIGIN,
        )
        self.assertEqual(r1.status_code, 200)

        # Protected fetch - test client automatically sends cookies
        r2 = self.client.get('/api/users/profile/')
        self.assertEqual(
            r2.status_code, 200,
            f'Profile must return 200 when authenticated. Got: {r2.status_code}. Body: {r2.content.decode()}',
        )
        data = r2.json()
        self.assertIn('user', data)
        self.assertEqual(data['user']['username'], 'browser_user')
