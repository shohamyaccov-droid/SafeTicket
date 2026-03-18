"""
E2E QA: Advanced HttpOnly Cookie Authentication - Edge Cases
  - Test 1: Refresh flow (expired access, refresh gets new access cookie)
  - Test 2: Logout clears both cookies (max-age=0 or expires past)
  - Test 3: Tampered cookie returns 401

Run: python manage.py test test_e2e_httponly_advanced -v 2
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class E2EHttpOnlyAdvancedTest(TestCase):
    """Advanced E2E tests for HttpOnly cookie auth edge cases."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='advanced_cookie_user',
            email='advanced@test.com',
            password='SecurePass123!',
            role='buyer',
        )

    def test_1_refresh_flow(self):
        """
        Login to get cookies. Delete access_token only. Call token/refresh/.
        Assert 200 and NEW access_token cookie is set.
        """
        # Login
        r1 = self.client.post('/api/users/login/', {
            'username': 'advanced_cookie_user',
            'password': 'SecurePass123!',
        }, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertIn('refresh_token', self.client.cookies)

        # Remove access_token only (simulate expired access)
        if 'access_token' in self.client.cookies:
            del self.client.cookies['access_token']

        # Call refresh - only refresh_token cookie is sent
        r2 = self.client.post('/api/users/token/refresh/')
        self.assertEqual(r2.status_code, 200, r2.content.decode())

        # New access_token cookie must be set
        self.assertIn('access_token', r2.cookies, 'Refresh must set new access_token cookie')

        # Verify we can now hit profile
        r3 = self.client.get('/api/users/profile/')
        self.assertEqual(r3.status_code, 200, r3.content.decode())

    def test_2_complete_logout(self):
        """
        Login. Call logout. Assert Set-Cookie headers clear BOTH cookies.
        """
        # Login
        r1 = self.client.post('/api/users/login/', {
            'username': 'advanced_cookie_user',
            'password': 'SecurePass123!',
        }, format='json')
        self.assertEqual(r1.status_code, 200)

        # Logout
        r2 = self.client.post('/api/users/logout/')
        self.assertEqual(r2.status_code, 200)

        # Both cookies must be cleared (max-age=0 or expires in past)
        for name in ('access_token', 'refresh_token'):
            self.assertIn(name, r2.cookies, f'{name} must be in logout response')
            out = r2.cookies[name].output().lower()
            self.assertTrue(
                'max-age=0' in out or 'expires=' in out,
                f'{name} must be cleared (max-age=0 or expires). Got: {out}'
            )

        # Verify profile now returns 401
        r3 = self.client.get('/api/users/profile/')
        self.assertEqual(r3.status_code, 401, 'Profile must return 401 after logout')

    def test_3_tampered_cookie_returns_401(self):
        """
        Set garbage as access_token cookie. Hit /api/users/profile/.
        Assert 401 Unauthorized.
        """
        # Set fake/tampered cookie
        self.client.cookies['access_token'] = 'garbage.invalid.token'

        r = self.client.get('/api/users/profile/')
        self.assertEqual(r.status_code, 401, f'Expected 401 for tampered cookie, got {r.status_code}. Body: {r.content.decode()}')
