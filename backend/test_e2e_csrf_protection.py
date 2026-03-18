"""
E2E CSRF Protection: Double-Submit Cookie pattern validation.
  - Test 1: POST without X-CSRFToken (attack blocked) -> 403
  - Test 2: POST with X-CSRFToken (legitimate) -> 200

Run: python manage.py test test_e2e_csrf_protection -v 2
"""
from django.test import TestCase
from django.test.client import ClientHandler
from django.contrib.auth import get_user_model

User = get_user_model()


class E2ECSRFProtectionTest(TestCase):
    """Verify CSRF blocks unauthorized requests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='csrf_user',
            email='csrf@test.com',
            password='SecurePass123!',
            role='buyer',
        )
        self.client.enforce_csrf_checks = True
        self.client.handler = ClientHandler(enforce_csrf_checks=True)

    def test_1_attack_blocked_post_without_csrf_header_returns_403(self):
        """
        Login to get JWT cookies. POST to logout WITHOUT X-CSRFToken.
        Simulates attacker with stolen cookies but no CSRF token.
        """
        # Get CSRF cookie first (required for login POST)
        r0 = self.client.get('/api/users/csrf/')
        self.assertEqual(r0.status_code, 200)
        csrf_token = r0.cookies.get('csrftoken')
        self.assertIsNotNone(csrf_token, 'CSRF cookie must be set')

        # Login with X-CSRFToken (legitimate flow)
        r1 = self.client.post(
            '/api/users/login/',
            {'username': 'csrf_user', 'password': 'SecurePass123!'},
            format='json',
            HTTP_X_CSRFTOKEN=r0.cookies['csrftoken'].value,
        )
        self.assertEqual(r1.status_code, 200)

        # Attack: POST logout WITHOUT X-CSRFToken (attacker has JWT cookies but no token)
        r2 = self.client.post('/api/users/logout/')
        self.assertEqual(
            r2.status_code, 403,
            f'CSRF attack must be blocked with 403. Got: {r2.status_code}. Body: {r2.content.decode()}',
        )

    def test_2_legitimate_request_with_csrf_header_succeeds(self):
        """
        Fetch CSRF token. Login. POST logout WITH X-CSRFToken.
        Assert 200 OK.
        """
        # Get CSRF cookie
        r0 = self.client.get('/api/users/csrf/')
        self.assertEqual(r0.status_code, 200)
        csrf_value = r0.cookies['csrftoken'].value

        # Login
        r1 = self.client.post(
            '/api/users/login/',
            {'username': 'csrf_user', 'password': 'SecurePass123!'},
            format='json',
            HTTP_X_CSRFTOKEN=csrf_value,
        )
        self.assertEqual(r1.status_code, 200)

        # Legitimate: POST logout WITH X-CSRFToken
        r2 = self.client.post('/api/users/logout/', HTTP_X_CSRFTOKEN=csrf_value)
        self.assertEqual(
            r2.status_code, 200,
            f'Legitimate request must succeed. Got: {r2.status_code}. Body: {r2.content.decode()}',
        )
