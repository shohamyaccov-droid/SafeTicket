"""
E2E QA: Seamless Registration & Login (No OTP Friction)
Verifies the frictionless flow after OTP rollback:
  - Test 1: Register returns 201 with access + refresh tokens instantly
  - Test 2: Login with same credentials returns 200 with valid tokens, no 401/email_not_verified

Run: python manage.py test test_e2e_registration_seamless -v 2
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class E2ERegistrationSeamlessTest(TestCase):
    """E2E tests for frictionless registration and login."""

    def test_1_instant_tokens_on_registration(self):
        """
        Register a brand new user via /api/users/register/.
        Assert 201, user in body, and JWT tokens set as HttpOnly cookies (instant login).
        """
        r = self.client.post('/api/users/register/', {
            'username': 'seamless_user',
            'email': 'seamless@test.com',
            'password': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'role': 'buyer',
        }, format='json')

        self.assertEqual(r.status_code, 201, f'Expected 201, got {r.status_code}. Body: {r.content.decode()}')
        data = r.json()
        self.assertIn('user', data, 'Response must contain user object')
        self.assertIn('access_token', r.cookies, 'Access token must be set as HttpOnly cookie')
        self.assertIn('refresh_token', r.cookies, 'Refresh token must be set as HttpOnly cookie')

    def test_2_direct_login_after_registration(self):
        """
        Register a user, then login with same credentials.
        Assert 200 with user data and cookies, NO 401 or email_not_verified errors.
        """
        # Register
        r1 = self.client.post('/api/users/register/', {
            'username': 'login_test_user',
            'email': 'login_test@test.com',
            'password': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'role': 'buyer',
        }, format='json')
        self.assertEqual(r1.status_code, 201, r1.content.decode())
        self.assertIn('access_token', r1.cookies, 'Registration must set access cookie')

        # Login with same credentials
        r2 = self.client.post('/api/users/login/', {
            'username': 'login_test_user',
            'password': 'SecurePass123!',
        }, format='json')

        self.assertEqual(r2.status_code, 200, f'Expected 200, got {r2.status_code}. Body: {r2.content.decode()}')
        data = r2.json()
        self.assertIn('user', data, 'Login must return user data')
        self.assertIn('access_token', r2.cookies, 'Login must set access cookie')
        self.assertNotEqual(r2.status_code, 401, 'Must NOT return 401')
        self.assertNotIn('email_not_verified', str(data).lower(), 'Must NOT block on email verification')
