from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import Artist, Event, Order, Ticket, User
from users.pricing import expected_buy_now_total


class GuestCheckoutFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username='guest_flow_seller',
            email='seller@example.test',
            password='pass-12345',
            role='seller',
        )
        self.artist = Artist.objects.create(name='Guest Flow Artist')
        self.event = Event.objects.create(
            name='Guest Flow Event',
            artist=self.artist,
            date=timezone.now() + timezone.timedelta(days=30),
            venue='אצטדיון רמת גן',
            city='Ramat Gan',
            country='IL',
            category='sport',
        )
        self.asking_price = Decimal('100.00')
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=self.event,
            event_name=self.event.name,
            event_date=self.event.date,
            venue=self.event.venue,
            original_price=self.asking_price,
            asking_price=self.asking_price,
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/test-guest-flow.pdf',
        )

    @override_settings(PAYME_SELLER_ID='seller-id-test', PAYME_API_URL='https://testpay.payme.io/api')
    @patch('users.payme_views.generate_payme_sale_for_order')
    def test_guest_checkout_can_create_order_and_init_payme_without_authentication(self, mock_generate_sale):
        guest_email = 'guest@example.test'
        checkout_total = expected_buy_now_total(self.asking_price, 1)
        mock_generate_sale.return_value = {
            'payme_sale_url': 'https://testpay.payme.io/hosted/guest-checkout',
            'transaction_id': 'payme_guest_txn_001',
            'raw': {},
        }

        create_res = self.client.post(
            '/api/users/orders/guest/',
            {
                'guest_email': guest_email,
                'guest_phone': '0501234567',
                'ticket_id': self.ticket.id,
                'total_amount': str(checkout_total),
                'quantity': 1,
                'event_name': self.event.name,
            },
            format='json',
        )

        self.assertEqual(create_res.status_code, 201, create_res.data)
        order = Order.objects.get(pk=create_res.data['id'])
        self.assertEqual(order.status, 'pending_payment')
        self.assertIsNone(order.user_id)
        self.assertEqual(order.guest_email, guest_email)

        init_res = self.client.post(
            '/api/users/payments/payme/init/',
            {
                'order_id': order.id,
                'guest_email': guest_email,
                'success_url': 'https://example.test/checkout/payme/success',
                'failure_url': 'https://example.test/checkout/payme/failure',
            },
            format='json',
        )

        self.assertEqual(init_res.status_code, 200, init_res.data)
        self.assertEqual(init_res.data['redirect_url'], 'https://testpay.payme.io/hosted/guest-checkout')
        order.refresh_from_db()
        self.assertEqual(order.payme_transaction_id, 'payme_guest_txn_001')
