"""
E2E QA: HttpOnly Cookie Authentication
  - Test 1: Login returns Set-Cookie with HttpOnly flag
  - Test 2: Authenticated request via cookie succeeds (profile)

Run: python manage.py test test_e2e_httponly_cookies -v 2
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class E2EHttpOnlyCookiesTest(TestCase):
    """E2E tests for HttpOnly cookie-based JWT auth."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cookie_test_user',
            email='cookie@test.com',
            password='SecurePass123!',
            role='buyer',
        )

    def test_1_login_sets_httponly_cookies(self):
        """
        Call login. Assert Set-Cookie headers exist, contain tokens, include HttpOnly.
        """
        r = self.client.post('/api/users/login/', {
            'username': 'cookie_test_user',
            'password': 'SecurePass123!',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content.decode())

        # Django stores cookies in response.cookies (SimpleCookie)
        self.assertIn('access_token', r.cookies, 'access_token cookie must be set')
        self.assertIn('refresh_token', r.cookies, 'refresh_token cookie must be set')
        # Check HttpOnly flag - SimpleCookie outputs it in the header string
        for name in ('access_token', 'refresh_token'):
            cookie_output = r.cookies[name].output()
            self.assertIn('HttpOnly', cookie_output, f'{name} cookie must have HttpOnly flag. Got: {cookie_output}')

        # Tokens must NOT be in response body
        data = r.json()
        self.assertNotIn('access', data, 'Access token must NOT be in response body')
        self.assertNotIn('refresh', data, 'Refresh token must NOT be in response body')
        self.assertIn('user', data, 'User data must be in response')

    def test_2_authenticated_request_via_cookie(self):
        """
        Login, then fetch profile. Cookies are sent automatically.
        Assert profile returns 200 with user data.
        """
        # Login (client stores cookies automatically)
        r1 = self.client.post('/api/users/login/', {
            'username': 'cookie_test_user',
            'password': 'SecurePass123!',
        }, format='json')
        self.assertEqual(r1.status_code, 200)

        # Profile request - no Authorization header; cookies are sent by test client
        r2 = self.client.get('/api/users/profile/')
        self.assertEqual(r2.status_code, 200, r2.content.decode())
        data = r2.json()
        self.assertIn('user', data)
        self.assertEqual(data['user']['username'], 'cookie_test_user')
