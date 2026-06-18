"""
End-to-end customer journey: reserve → order → PayMe init → form-urlencoded webhook → dashboard.

Validates the real PayMe callback format (application/x-www-form-urlencoded), not JSON.

Run:
  cd backend && python manage.py test tests.test_payme_form_webhook_customer_journey -v 2
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch
from urllib.parse import urlencode

from django.test import override_settings

from tests.test_payme_e2e_ledger import (
    PAYME_SANDBOX_BUYER_EMAIL,
    WEBHOOK_URL,
    PayMeMarketplaceE2EBase,
)

DASHBOARD_URL = '/api/users/dashboard/'


@override_settings(
    PAYME_SELLER_ID='MPL-E2E-FORM-SELLER',
    PAYME_API_URL='https://testpay.payme.io/api',
    PAYME_IS_SANDBOX=True,
    PAYME_SANDBOX_ACCOUNT_EMAIL=PAYME_SANDBOX_BUYER_EMAIL,
    PAYME_WEBHOOK_SECRET='whsec_test',
)
class PayMeFormWebhookCustomerJourneyTests(PayMeMarketplaceE2EBase):
    """Full buyer journey with PayMe webhook sent as form-urlencoded POST (real PSP format)."""

    @patch('users.payme_views.generate_payme_sale_for_order')
    def test_customer_journey_form_webhook_finalizes_and_shows_in_dashboard(self, mock_generate):
        # 1–2. Reserve ticket and create pending order
        self._buyer_reserves_ticket()
        order = self._buyer_creates_pending_order()

        # 3. PayMe init checkout
        self._init_payme_checkout(order, mock_generate, transaction_id='SALE1781-form-journey')
        order.refresh_from_db()

        # 4. Simulate PayMe success callback as form-urlencoded (NOT JSON).
        # Live PayMe sends several IDs; any one may be the value saved during init.
        sale_price_minor = int(Decimal(order.total_paid_by_buyer or order.total_amount) * 100)
        form_payload = {
            'payme_sale_code': '15974993',
            'payme_sale_id': order.payme_transaction_id,
            'payme_transaction_id': 'TRAN1781-form-journey',
            'status': 'success',
            'price': str(sale_price_minor),
            'currency': order.currency or 'ILS',
        }
        form_body = urlencode(form_payload)

        webhook_res = self.client.post(
            WEBHOOK_URL,
            form_body,
            content_type='application/x-www-form-urlencoded',
        )

        # 5. Webhook must succeed without JSONDecodeError
        self.assertEqual(
            webhook_res.status_code,
            200,
            f'Expected 200 OK, got {webhook_res.status_code}: {webhook_res.content!r}',
        )
        self.assertNotIn(b'JSONDecodeError', webhook_res.content)
        self.assertNotIn(b'invalid json', webhook_res.content.lower())
        self.assertTrue(webhook_res.data.get('finalized'), webhook_res.data)

        # 6. Order finalized in database
        order.refresh_from_db()
        self.ticket.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.payme_status, 'success')
        self.assertEqual(self.ticket.status, 'sold')

        # 7. Buyer dashboard / my-tickets area shows the purchase
        self.client.force_authenticate(self.buyer)
        dash_res = self.client.get(DASHBOARD_URL)
        self.assertEqual(dash_res.status_code, 200, dash_res.content)

        purchases = dash_res.data.get('purchases') or []
        mine = next((p for p in purchases if p.get('id') == order.id), None)
        self.assertIsNotNone(mine, f'Order {order.id} missing from buyer dashboard purchases')
        self.assertEqual(mine['status'], 'paid')

        ticket_ids_in_purchase = {t.get('id') for t in (mine.get('tickets') or [])}
        if not ticket_ids_in_purchase and mine.get('ticket'):
            ticket_ids_in_purchase = {mine['ticket']}
        self.assertIn(
            self.ticket.id,
            ticket_ids_in_purchase,
            f'Ticket {self.ticket.id} not found in dashboard purchase: {mine}',
        )
        ticket_details = mine.get('ticket_details') or {}
        if ticket_details:
            self.assertEqual(ticket_details.get('event_name') or ticket_details.get('event'), self.event.name)
