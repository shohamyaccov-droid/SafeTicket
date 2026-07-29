from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

User = get_user_model()


@override_settings(DEBUG=False, SECRET_KEY='auth-happy-secret')
class AuthHappyPathTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def test_register_returns_user_and_jwt_tokens(self):
        payload = {
            'username': 'happy_buyer',
            'email': 'happy_buyer@example.test',
            'password': 'ValidPass123!',
            'password2': 'ValidPass123!',
            'first_name': 'Happy',
            'last_name': 'Buyer',
            'phone_number': '0501234567',
        }

        res = self.api.post('/api/users/register/', payload, format='json')

        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertIn('user', body)
        self.assertIn('access', body)
        self.assertIn('refresh', body)
        self.assertEqual(body['user']['email'], payload['email'])
        self.assertTrue(User.objects.filter(email=payload['email']).exists())

    def test_login_returns_user_and_jwt_tokens(self):
        user = User.objects.create_user(
            username='login_buyer',
            email='login_buyer@example.test',
            password='ValidPass123!',
            first_name='Login',
            last_name='Buyer',
        )

        res = self.api.post(
            '/api/users/login/',
            {'username': user.username, 'password': 'ValidPass123!'},
            format='json',
        )

        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        self.assertIn('user', body)
        self.assertIn('access', body)
        self.assertIn('refresh', body)
        self.assertEqual(body['user']['username'], user.username)
