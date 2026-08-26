from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from users.models import Order
from users.views import ADMIN_BUYER_PHONE_UNSPECIFIED, order_buyer_phone_display


User = get_user_model()


class AdminTransactionsBuyerPhoneTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin-tx-phone',
            email='admin-tx-phone@example.com',
            password='pass',
            is_staff=True,
        )
        self.client.force_authenticate(self.admin)

    def test_guest_order_returns_guest_phone(self):
        Order.objects.create(
            guest_email='guest-phone@example.com',
            guest_phone='0501112233',
            total_amount=Decimal('150.00'),
            status='paid',
            event_name='Guest Phone Show',
        )

        res = self.client.get('/api/users/admin/transactions/')
        self.assertEqual(res.status_code, 200, res.content)
        row = next(r for r in res.data['transactions'] if r['event_name'] == 'Guest Phone Show')
        self.assertEqual(row['buyer_phone'], '0501112233')

    def test_registered_user_returns_profile_phone(self):
        buyer = User.objects.create_user(
            username='buyer-with-phone',
            email='buyer-with-phone@example.com',
            password='pass',
            role='buyer',
            phone_number='0527654321',
        )
        Order.objects.create(
            user=buyer,
            total_amount=Decimal('200.00'),
            status='paid',
            event_name='Registered Phone Show',
        )

        res = self.client.get('/api/users/admin/transactions/')
        self.assertEqual(res.status_code, 200, res.content)
        row = next(r for r in res.data['transactions'] if r['event_name'] == 'Registered Phone Show')
        self.assertEqual(row['buyer_phone'], '0527654321')

    def test_missing_phone_returns_unspecified_label(self):
        buyer = User.objects.create_user(
            username='buyer-no-phone',
            email='buyer-no-phone@example.com',
            password='pass',
            role='buyer',
        )
        Order.objects.create(
            user=buyer,
            total_amount=Decimal('80.00'),
            status='paid',
            event_name='No Phone Show',
        )

        res = self.client.get('/api/users/admin/transactions/')
        self.assertEqual(res.status_code, 200, res.content)
        row = next(r for r in res.data['transactions'] if r['event_name'] == 'No Phone Show')
        self.assertEqual(row['buyer_phone'], ADMIN_BUYER_PHONE_UNSPECIFIED)

    def test_guest_order_without_phone_returns_unspecified_label(self):
        Order.objects.create(
            guest_email='guest-nophone@example.com',
            total_amount=Decimal('90.00'),
            status='paid',
            event_name='Guest No Phone Show',
        )

        res = self.client.get('/api/users/admin/transactions/')
        self.assertEqual(res.status_code, 200, res.content)
        row = next(r for r in res.data['transactions'] if r['event_name'] == 'Guest No Phone Show')
        self.assertEqual(row['buyer_phone'], ADMIN_BUYER_PHONE_UNSPECIFIED)

    def test_helper_does_not_raise_when_user_lookup_fails(self):
        class BrokenOrder:
            user_id = 99
            guest_phone = '0500000000'

            @property
            def user(self):
                raise User.DoesNotExist

        self.assertEqual(order_buyer_phone_display(BrokenOrder()), '0500000000')
