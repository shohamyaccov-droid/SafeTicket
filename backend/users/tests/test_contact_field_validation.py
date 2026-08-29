from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket, User
from users.pricing import expected_buy_now_total


@override_settings(DEBUG=False, SECRET_KEY='contact-validation-secret')
class RegistrationContactValidationTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def _payload(self, **overrides):
        data = {
            'username': 'optional_names_buyer',
            'email': 'optional_names@example.test',
            'password': 'ValidPass123!',
            'password2': 'ValidPass123!',
            'phone_number': '0501234567',
        }
        data.update(overrides)
        return data

    def test_register_succeeds_without_first_or_last_name(self):
        res = self.api.post('/api/users/register/', self._payload(), format='json')
        self.assertEqual(res.status_code, 201, res.content)
        user = User.objects.get(email='optional_names@example.test')
        self.assertEqual(user.first_name, '')
        self.assertEqual(user.last_name, '')
        self.assertEqual(user.phone_number, '0501234567')

    def test_register_rejects_missing_phone(self):
        res = self.api.post(
            '/api/users/register/',
            self._payload(username='nophone', email='nophone@example.test', phone_number=''),
            format='json',
        )
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('phone_number', res.json())

    def test_register_rejects_omitted_phone(self):
        payload = self._payload(username='omitphone', email='omitphone@example.test')
        payload.pop('phone_number')
        res = self.api.post('/api/users/register/', payload, format='json')
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('phone_number', res.json())

    def test_register_rejects_blank_email(self):
        res = self.api.post(
            '/api/users/register/',
            self._payload(username='noemail', email=''),
            format='json',
        )
        self.assertEqual(res.status_code, 400, res.content)


@override_settings(DEBUG=False, SECRET_KEY='contact-validation-secret')
class ProfileContactValidationTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.user = User.objects.create_user(
            username='profile_contact',
            email='profile_contact@example.test',
            password='ValidPass123!',
            phone_number='0501112233',
        )
        self.api.force_authenticate(user=self.user)

    def test_profile_patch_allows_empty_names(self):
        res = self.api.patch(
            '/api/users/profile/',
            {'first_name': '', 'last_name': ''},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, '')
        self.assertEqual(self.user.last_name, '')

    def test_profile_patch_rejects_blank_phone(self):
        res = self.api.patch(
            '/api/users/profile/',
            {'phone_number': ''},
            format='json',
        )
        self.assertEqual(res.status_code, 400, res.data)
        self.assertEqual(res.data.get('code'), 'invalid_phone')


class GuestCheckoutContactValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        seller = User.objects.create_user(
            username='guest_val_seller',
            email='guest_val_seller@example.test',
            password='pass-12345',
            role='seller',
        )
        artist = Artist.objects.create(name='Guest Val Artist')
        self.event = Event.objects.create(
            name='Guest Val Event',
            artist=artist,
            date=timezone.now() + timedelta(days=30),
            venue='אצטדיון רמת גן',
            city='Ramat Gan',
            country='IL',
            category='sport',
        )
        self.asking_price = Decimal('100.00')
        self.ticket = Ticket.objects.create(
            seller=seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=self.asking_price,
            asking_price=self.asking_price,
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/test-guest-val.pdf',
        )

    def _guest_payload(self, **overrides):
        data = {
            'guest_email': 'guest_optional_name@example.test',
            'guest_phone': '0501234567',
            'ticket_id': self.ticket.id,
            'total_amount': str(expected_buy_now_total(self.asking_price, 1)),
            'quantity': 1,
            'event_name': self.event.name,
            'accepted_terms': True,
        }
        data.update(overrides)
        return data

    def test_guest_checkout_succeeds_without_names(self):
        res = self.client.post('/api/users/orders/guest/', self._guest_payload(), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        order = Order.objects.get(pk=res.data['id'])
        self.assertEqual(order.guest_email, 'guest_optional_name@example.test')
        self.assertEqual(order.guest_phone, '0501234567')
        self.assertFalse((order.guest_first_name or '').strip())
        self.assertFalse((order.guest_last_name or '').strip())

    def test_guest_checkout_rejects_missing_phone(self):
        res = self.client.post(
            '/api/users/orders/guest/',
            self._guest_payload(guest_phone=''),
            format='json',
        )
        self.assertEqual(res.status_code, 400, res.data)
        body = res.json() if hasattr(res, 'json') else res.data
        self.assertTrue('guest_phone' in body or 'phone' in str(body).lower())

    def test_guest_checkout_rejects_missing_email(self):
        res = self.client.post(
            '/api/users/orders/guest/',
            self._guest_payload(guest_email=''),
            format='json',
        )
        self.assertEqual(res.status_code, 400, res.data)
