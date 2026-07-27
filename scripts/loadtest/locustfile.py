"""
TradeTix / SafeTicket Locust load test — browse → reserve → guest checkout → mock pay.

SAFE TO RUN ONLY against a local (or dedicated staging) backend with DEBUG=True.
Never point this at production: it creates real orders and finalizes via mock payment.

Prerequisites:
  - Local Django running (e.g. python manage.py runserver 0.0.0.0:8000)
  - Seeded events/tickets (python manage.py seed_checkout_test_tickets or similar)
  - DEBUG=True so POST /api/payments/mock-success/ works
  - Enough active tickets for your user count (otherwise expect many 400 "held" responses)

Install:
  pip install -r scripts/loadtest/requirements.txt

Run (web UI):
  cd scripts/loadtest
  locust -f locustfile.py --host http://127.0.0.1:8000

Run (headless 100 users, 10 spawn/s, 2 minutes):
  locust -f locustfile.py --host http://127.0.0.1:8000 \\
    --users 100 --spawn-rate 10 --run-time 2m --headless

Env overrides:
  LOCUST_EVENT_ID   — pin to one event (optional)
  LOCUST_BUY_RATIO  — 0.0–1.0 fraction of users that attempt checkout (default 0.25)
"""
from __future__ import annotations

import os
import random
import string
import time
from decimal import Decimal, ROUND_HALF_UP

from locust import HttpUser, between, events, task


BUY_RATIO = float(os.environ.get('LOCUST_BUY_RATIO', '0.25'))
PINNED_EVENT_ID = (os.environ.get('LOCUST_EVENT_ID') or '').strip()


def _unique_email(prefix: str = 'load') -> str:
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f'{prefix}.{suffix}@loadtest.local'


def _buyer_total_from_asking(asking: Decimal | float | str, qty: int = 1) -> str:
    """Match default 7% buyer fee used in TradeTix pricing (quantize like backend)."""
    base = Decimal(str(asking)) * Decimal(qty)
    total = (base * Decimal('1.07')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return str(total)


class TradeTixUser(HttpUser):
    """
    Weighted traffic mix approximating marketplace browsing + a smaller checkout cohort.
    """

    wait_time = between(0.5, 2.5)

    def on_start(self):
        self.guest_email = _unique_email()
        self.guest_phone = '050' + ''.join(random.choices(string.digits, k=7))
        self._event_cache: list[dict] = []
        self._ticket_cache: list[dict] = []

    # --- Browse / arena map style traffic (majority) ---

    @task(8)
    def health(self):
        self.client.get('/api/health/', name='GET /api/health/')

    @task(12)
    def list_events(self):
        with self.client.get('/api/users/events/', name='GET /api/users/events/', catch_response=True) as res:
            if res.status_code != 200:
                res.failure(f'events list {res.status_code}')
                return
            data = res.json()
            rows = data if isinstance(data, list) else data.get('results') or data.get('events') or []
            if isinstance(rows, list) and rows:
                self._event_cache = [r for r in rows if isinstance(r, dict)][:40]
            res.success()

    @task(10)
    def event_detail_and_tickets(self):
        event_id = PINNED_EVENT_ID
        if not event_id and self._event_cache:
            event_id = str(self._event_cache[random.randrange(len(self._event_cache))].get('id') or '')
        if not event_id:
            # Warm cache
            self.list_events()
            if self._event_cache:
                event_id = str(self._event_cache[0].get('id') or '')
        if not event_id:
            return

        self.client.get(f'/api/users/events/{event_id}/', name='GET /api/users/events/:id/')

        # Ticket inventory for the event (arena / listing browse)
        with self.client.get(
            f'/api/users/events/{event_id}/tickets/',
            name='GET /api/users/events/:id/tickets/',
            catch_response=True,
        ) as res:
            if res.status_code != 200:
                # Some deployments filter differently; try unfiltered active list
                res.failure(f'tickets {res.status_code}')
                return
            data = res.json()
            rows = data if isinstance(data, list) else data.get('results') or []
            active = [
                t
                for t in rows
                if isinstance(t, dict) and t.get('status') == 'active' and (t.get('available_quantity') or 0) > 0
            ]
            self._ticket_cache = active[:80]
            res.success()

        # Venue sections (seat map / arena metadata) when present on event payload
        if self._event_cache:
            # no-op warm: pricing settings (frontend checkout reads this)
            self.client.get('/api/users/pricing/settings/', name='GET /api/users/pricing/settings/')

    @task(4)
    def shabbat_and_promo(self):
        self.client.get('/api/users/shabbat/status/', name='GET /api/users/shabbat/status/')
        self.client.get('/api/users/promotions/launch/', name='GET /api/users/promotions/launch/')

    # --- Contended purchase path (minority of users) ---

    @task(3)
    def reserve_and_maybe_checkout(self):
        if random.random() > BUY_RATIO:
            # Still poke reserve contention lightly without checkout
            ticket = self._pick_active_ticket()
            if not ticket:
                return
            tid = ticket['id']
            self.client.post(
                f'/api/users/tickets/{tid}/reserve/',
                json={'email': self.guest_email},
                name='POST /api/users/tickets/:id/reserve/ (browse-hold)',
            )
            return

        ticket = self._pick_active_ticket()
        if not ticket:
            self.event_detail_and_tickets()
            ticket = self._pick_active_ticket()
        if not ticket:
            return

        tid = ticket['id']
        asking = ticket.get('asking_price') or ticket.get('price') or '100.00'
        qty = 1
        total = _buyer_total_from_asking(asking, qty)

        # 1) Reserve (row lock)
        with self.client.post(
            f'/api/users/tickets/{tid}/reserve/',
            json={'email': self.guest_email},
            name='POST /api/users/tickets/:id/reserve/',
            catch_response=True,
        ) as res:
            if res.status_code in (200, 201):
                res.success()
            elif res.status_code == 400:
                # Expected under contention — ticket held by another virtual user
                res.success()
                return
            else:
                res.failure(f'reserve {res.status_code}: {res.text[:200]}')
                return

        # 2) Guest checkout → pending_payment
        payload = {
            'ticket_id': tid,
            'guest_email': self.guest_email,
            'guest_phone': self.guest_phone,
            'guest_first_name': 'Load',
            'guest_last_name': 'Test',
            'total_amount': total,
            'quantity': qty,
            'accepted_terms': True,
        }
        order_id = None
        with self.client.post(
            '/api/users/orders/guest/',
            json=payload,
            name='POST /api/users/orders/guest/',
            catch_response=True,
        ) as res:
            if res.status_code in (200, 201):
                body = res.json()
                order_id = body.get('id') or (body.get('order') or {}).get('id')
                if not order_id:
                    res.failure('guest checkout missing order id')
                    return
                res.success()
            elif res.status_code == 400:
                # Inventory race / reservation mismatch — acceptable under load
                res.success()
                return
            else:
                res.failure(f'guest checkout {res.status_code}: {res.text[:240]}')
                return

        # 3) Mock PayMe success (DEBUG only) — same finalize path as webhook
        with self.client.post(
            '/api/payments/mock-success/',
            json={'order_id': order_id, 'guest_email': self.guest_email},
            name='POST /api/payments/mock-success/',
            catch_response=True,
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 403:
                res.failure('mock-success forbidden — is DEBUG=True on the target host?')
            else:
                res.failure(f'mock pay {res.status_code}: {res.text[:240]}')

        # Rotate identity so the next attempt is a "new" buyer
        self.guest_email = _unique_email()
        time.sleep(0.05)

    def _pick_active_ticket(self) -> dict | None:
        if not self._ticket_cache:
            return None
        return random.choice(self._ticket_cache)


@events.init_command_line_parser.add_listener
def _add_cli_args(parser):
    parser.add_argument(
        '--buy-ratio',
        type=float,
        env_var='LOCUST_BUY_RATIO',
        default=BUY_RATIO,
        help='Fraction of reserve tasks that proceed to checkout (0-1)',
    )


@events.test_start.add_listener
def _on_test_start(environment, **_kwargs):
    host = getattr(environment, 'host', None) or ''
    if 'onrender.com' in host or 'tradetix.co.il' in host:
        raise RuntimeError(
            f'Refusing to load-test production-like host {host!r}. '
            'Use http://127.0.0.1:8000 (or a dedicated staging API).'
        )
