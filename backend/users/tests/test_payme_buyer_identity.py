"""PayMe buyer identity from authenticated user profile (dashboard checkout)."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from services.payme_service import build_standard_generate_sale_body, resolve_buyer_details_for_order
from users.models import Artist, Event, Order, Ticket

User = get_user_model()


class PaymeBuyerIdentityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='payme_id_buyer',
            email='payme-id-buyer@example.test',
            password='SafePass123!',
            role='buyer',
        )
        self.seller = User.objects.create_user(
            username='payme_id_seller',
            email='payme-id-seller@example.test',
            password='SafePass123!',
            role='seller',
        )
        artist = Artist.objects.create(name='Payme ID Artist')
        event = Event.objects.create(
            artist=artist,
            name='Payme ID Event',
            date=timezone.now() + timedelta(days=20),
            venue='Arena',
            city='Tel Aviv',
            country='IL',
            category='concert',
            status='פעיל',
        )
        self.ticket = Ticket.objects.create(
            seller=self.seller,
            event=event,
            original_price=Decimal('100.00'),
            asking_price=Decimal('100.00'),
            available_quantity=1,
            status='active',
            verification_status='מאומת',
            pdf_file='tickets/pdfs/payme-id.pdf',
        )
        self.order = Order.objects.create(
            user=self.user,
            ticket=self.ticket,
            quantity=1,
            total_amount=Decimal('107.00'),
            total_paid_by_buyer=Decimal('107.00'),
            status='pending_payment',
            event_name=event.name,
            currency='ILS',
            ticket_ids=[self.ticket.id],
        )
        self.client.force_authenticate(user=self.user)

    def test_profile_patch_updates_name_and_phone(self):
        res = self.client.patch(
            '/api/users/profile/',
            {
                'first_name': 'ישראל',
                'last_name': 'ישראלי',
                'phone_number': '0501234567',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'ישראל')
        self.assertEqual(self.user.last_name, 'ישראלי')
        self.assertEqual(self.user.phone_number, '0501234567')
        self.assertEqual(res.data['user']['full_name'], 'ישראל ישראלי')
        self.assertIn('first_name', res.data['user'])
        self.assertIn('phone_number', res.data['user'])

    def test_resolve_buyer_details_reads_profile_and_bit_phone_fallback(self):
        self.user.first_name = ''
        self.user.last_name = ''
        self.user.phone_number = ''
        self.user.bit_phone_number = '0527654321'
        self.user.first_name = 'Dana'
        self.user.last_name = 'Cohen'
        self.user.save()
        details = resolve_buyer_details_for_order(self.order)
        self.assertEqual(details['buyer_full_name'], 'Dana Cohen')
        self.assertEqual(details['buyer_phone'], '0527654321')
        self.assertEqual(details['buyer_phone_number'], details['buyer_phone'])
        self.assertEqual(details['buyer_first_name'], 'Dana')
        self.assertEqual(details['buyer_last_name'], 'Cohen')

    def test_generate_sale_body_includes_name_and_phone_aliases(self):
        body = build_standard_generate_sale_body(
            amount=Decimal('107.00'),
            ticket_name='TradeTix test',
            customer_email='buyer@example.test',
            order_id='99',
            buyer_name='Dana Cohen',
            buyer_phone='0501234567',
        )
        self.assertEqual(body['buyer_name'], 'Dana Cohen')
        self.assertEqual(body['buyer_full_name'], 'Dana Cohen')
        self.assertEqual(body['buyer_phone'], '0501234567')
        self.assertEqual(body['buyer_phone_number'], '0501234567')
        self.assertEqual(body['first_name'], 'Dana')
        self.assertEqual(body['last_name'], 'Cohen')
        self.assertEqual(body['phone'], '0501234567')

    @patch('users.payme_views.generate_payme_sale_for_order')
    def test_payme_init_accepts_body_identity_and_persists(self, mock_generate):
        mock_generate.return_value = {
            'payme_sale_url': 'https://testpay.payme.io/hosted/x',
            'transaction_id': 'txn_profile_1',
        }
        self.user.first_name = ''
        self.user.last_name = ''
        self.user.phone_number = ''
        self.user.save()

        with self.settings(PAYME_SELLER_ID='seller-test'):
            res = self.client.post(
                '/api/users/payments/payme/init/',
                {
                    'order_id': self.order.id,
                    'success_url': 'https://example.test/ok',
                    'failure_url': 'https://example.test/fail',
                    'buyer_full_name': 'Noa Levi',
                    'buyer_phone_number': '0509988776',
                },
                format='json',
            )
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Noa')
        self.assertEqual(self.user.last_name, 'Levi')
        self.assertEqual(self.user.phone_number, '0509988776')
        kwargs = mock_generate.call_args.kwargs
        self.assertEqual(kwargs['buyer_name'], 'Noa Levi')
        self.assertTrue(str(kwargs['buyer_phone']).endswith('509988776') or '0509988776' in str(kwargs['buyer_phone']))
