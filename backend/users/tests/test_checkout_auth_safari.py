"""Checkout auth for cookie-less clients (iOS Safari ITP) vs cookie clients (desktop)."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import Artist, Event, Order, Ticket
from users.pricing import expected_buy_now_total

User = get_user_model()


@override_settings(
    PAYME_SELLER_ID='seller-id-test',
    PAYME_API_URL='https://testpay.payme.io/api',
    JWT_RESPONSE_BODY_TOKENS=True,
)
class CheckoutAuthSafariDesktopScenariosTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='auth_seller',
            email='auth_seller@test.com',
            password='Pass12345!',
            role='seller',
        )
        self.buyer = User.objects.create_user(
            username='auth_buyer',
            email='auth_buyer@test.com',
            password='Pass12345!',
            role='buyer',
            first_name='Buyer',
            last_name='Mobile',
            phone_number='0501234567',
        )
        artist = Artist.objects.create(name='Auth Artist')
        self.event = Event.objects.create(
            artist=artist,
            name='Auth Event',
            date=timezone.now() + timedelta(days=10),
            venue='Hall',
            city='Tel Aviv',
            country='IL',
        )
        self.asking = Decimal('100.00')
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            original_price=self.asking,
            asking_price=self.asking,
            pdf_file='tickets/pdfs/auth.pdf',
            status='active',
            verification_status='מאומת',
            available_quantity=1,
        )

    def _login_body_tokens(self):
        """Simulate mobile login: tokens in JSON body (cookies may be ignored by Safari)."""
        res = self.client.post(
            '/api/users/login/',
            {'username': 'auth_buyer', 'password': 'Pass12345!'},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)
        return res.data['access'], res.data['refresh']

    def _pending_order(self):
        total = expected_buy_now_total(self.asking, 1)
        return Order.objects.create(
            user=self.buyer,
            ticket=self.ticket,
            event_name=self.event.name,
            quantity=1,
            total_amount=total,
            status='pending_payment',
        )

    def test_login_returns_body_tokens_for_safari_bearer_storage(self):
        access, refresh = self._login_body_tokens()
        self.assertTrue(len(access) > 20)
        self.assertTrue(len(refresh) > 20)

    def test_payme_init_with_bearer_only_no_cookies_succeeds(self):
        """iOS Safari: cookies blocked; Authorization Bearer must authorize PayMe init."""
        access, _refresh = self._login_body_tokens()
        self.client.cookies.clear()
        order = self._pending_order()

        with patch('users.payme_views.generate_payme_sale_for_order') as mock_sale:
            mock_sale.return_value = {
                'payme_sale_url': 'https://testpay.payme.io/hosted/safari',
                'transaction_id': 'txn_safari_1',
                'raw': {},
            }
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
            res = self.client.post(
                '/api/users/payments/payme/init/',
                {
                    'order_id': order.id,
                    'success_url': 'https://example.test/ok',
                    'failure_url': 'https://example.test/fail',
                },
                format='json',
            )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn('redirect_url', res.data)

    def test_payme_init_without_bearer_or_cookies_forbidden_not_logout_signal(self):
        """Anonymous PayMe init on owned order → 403 Forbidden (SPA must NOT treat as session expiry)."""
        order = self._pending_order()
        self.client.credentials()
        self.client.cookies.clear()
        res = self.client.post(
            '/api/users/payments/payme/init/',
            {
                'order_id': order.id,
                'success_url': 'https://example.test/ok',
                'failure_url': 'https://example.test/fail',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 403, res.data)
        self.assertIn('Forbidden', str(res.data.get('error', '')))

    def test_desktop_style_cookie_auth_payme_init_succeeds(self):
        """Desktop: JWT cookies attached (SameSite=None capable browsers)."""
        refresh = RefreshToken.for_user(self.buyer)
        access = str(refresh.access_token)
        order = self._pending_order()
        self.client.credentials()
        self.client.cookies['access_token'] = access
        self.client.cookies['refresh_token'] = str(refresh)

        with patch('users.payme_views.generate_payme_sale_for_order') as mock_sale:
            mock_sale.return_value = {
                'payme_sale_url': 'https://testpay.payme.io/hosted/desktop',
                'transaction_id': 'txn_desk_1',
                'raw': {},
            }
            res = self.client.post(
                '/api/users/payments/payme/init/',
                {
                    'order_id': order.id,
                    'success_url': 'https://example.test/ok',
                    'failure_url': 'https://example.test/fail',
                },
                format='json',
            )
        self.assertEqual(res.status_code, 200, res.data)

    def test_refresh_body_token_without_cookies_issues_new_access(self):
        """Safari refresh path: body refresh token, no cookie jar."""
        _access, refresh = self._login_body_tokens()
        self.client.cookies.clear()
        self.client.credentials()
        res = self.client.post(
            '/api/users/token/refresh/',
            {'refresh': refresh},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn('access', res.data)

    def test_logged_in_create_order_then_payme_bearer_chain(self):
        """Logged-in-before-checkout happy path (mobile Bearer)."""
        access, _ = self._login_body_tokens()
        self.client.cookies.clear()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.client.post(f'/api/users/tickets/{self.ticket.id}/reserve/', {'quantity': 1}, format='json')
        total = expected_buy_now_total(self.asking, 1)
        create = self.client.post(
            '/api/users/orders/',
            {
                'ticket': self.ticket.id,
                'total_amount': str(total),
                'quantity': 1,
                'event_name': self.event.name,
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertEqual(create.status_code, 201, create.data)
        with patch('users.payme_views.generate_payme_sale_for_order') as mock_sale:
            mock_sale.return_value = {
                'payme_sale_url': 'https://testpay.payme.io/hosted/chain',
                'transaction_id': 'txn_chain',
                'raw': {},
            }
            init = self.client.post(
                '/api/users/payments/payme/init/',
                {
                    'order_id': create.data['id'],
                    'success_url': 'https://example.test/ok',
                    'failure_url': 'https://example.test/fail',
                },
                format='json',
            )
        self.assertEqual(init.status_code, 200, init.data)

    def test_guest_checkout_payme_with_email_skip_auth(self):
        """Guest checkout: no login; guest_email authorizes PayMe init."""
        self.client.credentials()
        self.client.cookies.clear()
        guest_email = 'guest_safari@test.com'
        total = expected_buy_now_total(self.asking, 1)
        self.client.post(
            f'/api/users/tickets/{self.ticket.id}/reserve/',
            {'email': guest_email, 'quantity': 1},
            format='json',
        )
        create = self.client.post(
            '/api/users/orders/guest/',
            {
                'guest_first_name': 'Guest',
                'guest_last_name': 'Buyer',
                'guest_email': guest_email,
                'guest_phone': '0509988776',
                'ticket_id': self.ticket.id,
                'total_amount': str(total),
                'quantity': 1,
                'event_name': self.event.name,
                'accepted_terms': True,
            },
            format='json',
        )
        self.assertEqual(create.status_code, 201, create.data)
        with patch('users.payme_views.generate_payme_sale_for_order') as mock_sale:
            mock_sale.return_value = {
                'payme_sale_url': 'https://testpay.payme.io/hosted/guest',
                'transaction_id': 'txn_guest',
                'raw': {},
            }
            init = self.client.post(
                '/api/users/payments/payme/init/',
                {
                    'order_id': create.data['id'],
                    'guest_email': guest_email,
                    'success_url': 'https://example.test/ok',
                    'failure_url': 'https://example.test/fail',
                },
                format='json',
            )
        self.assertEqual(init.status_code, 200, init.data)
