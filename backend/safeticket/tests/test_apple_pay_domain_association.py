from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse


class ApplePayDomainAssociationTests(SimpleTestCase):
    def test_well_known_endpoint_returns_exact_verification_file(self):
        expected = (
            Path(__file__).resolve().parent.parent.parent
            / '.well-known'
            / 'apple-developer-merchantid-domain-association'
        ).read_text(encoding='utf-8')

        response = self.client.get(
            reverse('apple_pay_domain_association'),
            HTTP_HOST='localhost',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertEqual(response.content.decode('utf-8'), expected)
        self.assertNotIn('<html', response.content.decode('utf-8').lower())
