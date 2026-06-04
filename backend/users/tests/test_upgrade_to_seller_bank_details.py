import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()

UPGRADE_URL = '/api/users/me/upgrade-to-seller/'


def _valid_payload(**overrides):
    base = {
        'phone_number': '0501234567',
        'account_holder_name': 'ישראל ישראלי',
        'id_number': '123456782',
        'bank_name_or_code': '10',
        'branch_number': '123',
        'account_number': '987654',
        'accepted_escrow_terms': True,
    }
    base.update(overrides)
    return base


class UpgradeToSellerBankDetailsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user(
            username='buyer-bank',
            email='buyer-bank@example.com',
            password='pass',
            role='buyer',
        )

    def test_upgrade_stores_json_in_payout_details(self):
        self.client.force_authenticate(self.buyer)
        res = self.client.post(UPGRADE_URL, _valid_payload(), format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.role, 'seller')
        data = json.loads(self.buyer.payout_details)
        self.assertEqual(data['account_holder_name'], 'ישראל ישראלי')
        self.assertEqual(data['id_number'], '123456782')
        self.assertEqual(data['bank_name_or_code'], '10')
        self.assertEqual(data['branch_number'], '123')
        self.assertEqual(data['account_number'], '987654')
        self.assertEqual(self.buyer.account_holder_name, 'ישראל ישראלי')
        self.assertEqual(self.buyer.bank_name, '10')
        self.assertEqual(self.buyer.branch_number, '123')
        self.assertEqual(self.buyer.account_number, '987654')

    def test_rejects_invalid_id_number(self):
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            UPGRADE_URL,
            _valid_payload(id_number='12ab'),
            format='json',
        )
        self.assertEqual(res.status_code, 400)

    def test_rejects_non_digit_branch(self):
        self.client.force_authenticate(self.buyer)
        res = self.client.post(
            UPGRADE_URL,
            _valid_payload(branch_number='12a'),
            format='json',
        )
        self.assertEqual(res.status_code, 400)

    def test_rejects_when_already_seller(self):
        self.buyer.role = 'seller'
        self.buyer.save(update_fields=['role'])
        self.client.force_authenticate(self.buyer)
        res = self.client.post(UPGRADE_URL, _valid_payload(), format='json')
        self.assertEqual(res.status_code, 400)
