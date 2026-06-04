from django.test import TestCase


class GrowPaymentWebhookTest(TestCase):
    def test_post_returns_200_without_auth(self):
        response = self.client.post(
            '/api/payments/webhook/',
            {'event': 'payment.updated'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'received'})
