"""Israeli spam-law opt-in: agreed_to_marketing defaults False and is never implied."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.consent import is_explicit_marketing_opt_in
from users.models import Artist, Event, Order, Ticket, User
from users.pricing import expected_buy_now_total


class MarketingConsentHelperTests(TestCase):
    def test_only_explicit_true_counts(self):
        self.assertTrue(is_explicit_marketing_opt_in(True))
        self.assertTrue(is_explicit_marketing_opt_in('true'))
        self.assertTrue(is_explicit_marketing_opt_in('1'))
        self.assertFalse(is_explicit_marketing_opt_in(False))
        self.assertFalse(is_explicit_marketing_opt_in(None))
        self.assertFalse(is_explicit_marketing_opt_in(''))
        self.assertFalse(is_explicit_marketing_opt_in('false'))


@override_settings(DEBUG=False, SECRET_KEY='marketing-opt-in-secret')
class RegistrationMarketingOptInTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def _payload(self, **overrides):
        data = {
            'username': 'mkt_buyer',
            'email': 'mkt_buyer@example.test',
            'password': 'ValidPass123!',
            'password2': 'ValidPass123!',
            'phone_number': '0501234567',
        }
        data.update(overrides)
        return data

    def test_register_defaults_marketing_false_when_omitted(self):
        res = self.api.post('/api/users/register/', self._payload(), format='json')
        self.assertEqual(res.status_code, 201, res.content)
        user = User.objects.get(email='mkt_buyer@example.test')
        self.assertFalse(user.agreed_to_marketing)
        self.assertFalse(res.json()['user']['agreed_to_marketing'])

    def test_register_saves_unchecked_false(self):
        res = self.api.post(
            '/api/users/register/',
            self._payload(username='mkt_no', email='mkt_no@example.test', agreed_to_marketing=False),
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.content)
        user = User.objects.get(email='mkt_no@example.test')
        self.assertFalse(user.agreed_to_marketing)

    def test_register_saves_checked_true(self):
        res = self.api.post(
            '/api/users/register/',
            self._payload(username='mkt_yes', email='mkt_yes@example.test', agreed_to_marketing=True),
            format='json',
            HTTP_X_FORWARDED_FOR='203.0.113.40',
        )
        self.assertEqual(res.status_code, 201, res.content)
        user = User.objects.get(email='mkt_yes@example.test')
        self.assertTrue(user.agreed_to_marketing)
        self.assertTrue(res.json()['user']['agreed_to_marketing'])
        self.assertIsNotNone(user.marketing_opt_in_at)
        self.assertEqual(user.marketing_opt_in_ip, '203.0.113.40')

    def test_register_unchecked_leaves_audit_blank(self):
        res = self.api.post(
            '/api/users/register/',
            self._payload(username='mkt_blank', email='mkt_blank@example.test', agreed_to_marketing=False),
            format='json',
            HTTP_X_FORWARDED_FOR='203.0.113.41',
        )
        self.assertEqual(res.status_code, 201, res.content)
        user = User.objects.get(email='mkt_blank@example.test')
        self.assertFalse(user.agreed_to_marketing)
        self.assertIsNone(user.marketing_opt_in_at)
        self.assertIsNone(user.marketing_opt_in_ip)


@override_settings(DEBUG=False, SECRET_KEY='marketing-opt-in-secret')
class CheckoutMarketingOptInTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        seller = User.objects.create_user(
            username='mkt_seller', email='mkt_seller@test.invalid', password='x', role='seller'
        )
        self.buyer = User.objects.create_user(
            username='mkt_checkout_buyer',
            email='mkt_checkout_buyer@test.invalid',
            password='x',
            role='buyer',
            phone_number='0501111111',
        )
        event = Event.objects.create(
            name='Mkt Event',
            artist=Artist.objects.create(name='Mkt Artist'),
            date=timezone.now() + timedelta(days=12),
            venue='מקום',
            city='Tel Aviv',
            country='US',
            category='concert',
        )
        self.ticket = Ticket.objects.create(
            seller=seller,
            event=event,
            event_name=event.name,
            event_date=event.date,
            venue=event.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='active',
            available_quantity=1,
        )
        self.total = expected_buy_now_total(self.ticket.asking_price, 1)

    def test_authenticated_checkout_opt_in_updates_user_and_order(self):
        self.api.force_authenticate(self.buyer)
        self.api.post(f'/api/users/tickets/{self.ticket.pk}/reserve/', {}, format='json')
        res = self.api.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.pk,
                'quantity': 1,
                'total_amount': str(self.total),
                'accepted_terms': True,
                'agreed_to_marketing': True,
            },
            format='json',
            HTTP_X_FORWARDED_FOR='198.51.100.20',
        )
        self.assertEqual(res.status_code, 201, res.content)
        order = Order.objects.get(pk=res.json()['id'])
        self.assertTrue(order.agreed_to_marketing)
        self.buyer.refresh_from_db()
        self.assertTrue(self.buyer.agreed_to_marketing)
        self.assertIsNotNone(self.buyer.marketing_opt_in_at)
        self.assertEqual(self.buyer.marketing_opt_in_ip, '198.51.100.20')

    def test_guest_checkout_opt_in_saved_on_order_not_implied(self):
        res_off = self.api.post(
            '/api/users/orders/guest/',
            {
                'guest_first_name': 'Guest',
                'guest_last_name': 'Off',
                'guest_email': 'guest_mkt_off@test.invalid',
                'guest_phone': '0501234567',
                'ticket_id': self.ticket.pk,
                'quantity': 1,
                'total_amount': str(self.total),
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertEqual(res_off.status_code, 201, res_off.content)
        order_off = Order.objects.get(pk=res_off.json()['id'])
        self.assertFalse(order_off.agreed_to_marketing)

        ticket2 = Ticket.objects.create(
            seller=self.ticket.seller,
            event=self.ticket.event,
            event_name=self.ticket.event_name,
            event_date=self.ticket.event_date,
            venue=self.ticket.venue,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            status='active',
            available_quantity=1,
        )
        res_on = self.api.post(
            '/api/users/orders/guest/',
            {
                'guest_first_name': 'Guest',
                'guest_last_name': 'On',
                'guest_email': 'guest_mkt_on@test.invalid',
                'guest_phone': '0501234568',
                'ticket_id': ticket2.pk,
                'quantity': 1,
                'total_amount': str(self.total),
                'accepted_terms': True,
                'agreed_to_marketing': True,
            },
            format='json',
        )
        self.assertEqual(res_on.status_code, 201, res_on.content)
        order_on = Order.objects.get(pk=res_on.json()['id'])
        self.assertTrue(order_on.agreed_to_marketing)
