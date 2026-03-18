"""
E2E User Journey: Simulates the React UI's API flow
  1. Click Login: POST /api/users/login/ -> 200 OK, cookies set
  2. Page Load (Dashboard): GET /api/users/profile/ (with cookies) -> 200 OK
  3. Click Logout: POST /api/users/logout/ -> 200 OK, cookies cleared
  4. Page Load (Logged Out): GET /api/users/profile/ -> 401 Unauthorized

Run: python manage.py test test_e2e_user_journey_ui -v 2
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class E2EUserJourneyUITest(TestCase):
    """Simulates the complete user journey as the React UI would call the API."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='journey_user',
            email='journey@test.com',
            password='SecurePass123!',
            role='buyer',
        )

    def test_full_user_journey_login_dashboard_logout(self):
        """
        Simulate: Login -> Dashboard load -> Logout -> Logged-out page load.
        """
        # Step 1: Click Login - POST /api/users/login/
        r1 = self.client.post('/api/users/login/', {
            'username': 'journey_user',
            'password': 'SecurePass123!',
        }, format='json')
        self.assertEqual(r1.status_code, 200, f'Login must return 200. Got: {r1.content.decode()}')
        self.assertIn('access_token', r1.cookies, 'Login must set access_token cookie')
        self.assertIn('refresh_token', r1.cookies, 'Login must set refresh_token cookie')

        # Step 2: Page Load (Dashboard) - GET /api/users/profile/ with cookies
        r2 = self.client.get('/api/users/profile/')
        self.assertEqual(r2.status_code, 200, f'Profile must return 200 when logged in. Got: {r2.content.decode()}')
        data = r2.json()
        self.assertIn('user', data)
        self.assertEqual(data['user']['username'], 'journey_user')

        # Step 3: Click Logout - POST /api/users/logout/
        r3 = self.client.post('/api/users/logout/')
        self.assertEqual(r3.status_code, 200, f'Logout must return 200. Got: {r3.content.decode()}')
        # Cookies must be cleared
        for name in ('access_token', 'refresh_token'):
            self.assertIn(name, r3.cookies, f'{name} must be in logout response')
            out = r3.cookies[name].output().lower()
            self.assertTrue(
                'max-age=0' in out or 'expires=' in out,
                f'{name} must be cleared. Got: {out}'
            )

        # Step 4: Page Load (Logged Out) - GET /api/users/profile/ -> 401
        r4 = self.client.get('/api/users/profile/')
        self.assertEqual(
            r4.status_code, 401,
            f'Profile must return 401 after logout. Got: {r4.status_code}. Body: {r4.content.decode()}'
        )
