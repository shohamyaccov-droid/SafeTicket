"""
One-off / ops recovery: force-finalize a stuck PayMe order (Apple Pay webhook miss).

Usage on Render Shell (from backend/):

  python manage.py force_finalize_payme_order --order-id 111
  python manage.py force_finalize_payme_order --email sagi.sabag.19@gmail.com
  python manage.py force_finalize_payme_order --order-id 111 --dry-run

Requires a stored payme_transaction_id. Uses the same force_from_admin path as the
Django admin action (paid + sold tickets + payout ledger + receipt).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from users.models import Order, Ticket
from users.payments import finalize_pending_order_to_paid

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Force-finalize a stuck PayMe order (pending_payment/cancelled → paid) '
        'and mark associated tickets sold for the buyer dashboard.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--order-id', type=int, default=None, help='Order primary key (e.g. 111).')
        parser.add_argument(
            '--email',
            type=str,
            default='',
            help='Buyer / guest email to locate the stuck order (e.g. sagi.sabag.19@gmail.com).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be finalized without writing.',
        )

    def handle(self, *args, **options):
        order_id = options.get('order_id')
        email = (options.get('email') or '').strip().lower()
        dry_run = bool(options.get('dry_run'))

        if not order_id and not email:
            raise CommandError('Provide --order-id and/or --email.')

        order = self._resolve_order(order_id=order_id, email=email)
        self._print_order(order)

        if not (order.payme_transaction_id or '').strip():
            raise CommandError(
                f'Order #{order.pk} has no payme_transaction_id — refuse to force-finalize '
                '(confirm the PayMe sale id was stored at checkout init).'
            )

        if order.status == 'paid':
            self.stdout.write(self.style.WARNING(f'Order #{order.pk} is already paid — re-fulfilling ticket rows.'))

        if dry_run:
            ticket_ids = list(order.ticket_ids or [])
            if not ticket_ids and order.ticket_id:
                ticket_ids = [order.ticket_id]
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] Would force-finalize order #{order.pk} '
                    f'status={order.status} → paid, ticket_ids={ticket_ids}'
                )
            )
            return

        # Link registered buyer by email when order is guest-only so dashboard ownership is clear.
        if not order.user_id and email:
            buyer = User.objects.filter(email__iexact=email).first()
            if buyer:
                order.user = buyer
                order.save(update_fields=['user', 'updated_at'])
                self.stdout.write(f'Linked order #{order.pk} to user id={buyer.pk} email={buyer.email}')

        ok, err = finalize_pending_order_to_paid(
            order.pk,
            source=f'management_force_finalize:email={email or "n/a"}',
            force_from_admin=True,
        )
        if not ok:
            raise CommandError(f'Finalize failed for order #{order.pk}: {err}')

        order.refresh_from_db()
        ticket_ids = list(order.ticket_ids or [])
        if not ticket_ids and order.ticket_id:
            ticket_ids = [order.ticket_id]
        tickets = list(Ticket.objects.filter(pk__in=ticket_ids)) if ticket_ids else []

        self.stdout.write(self.style.SUCCESS(f'Order #{order.pk} status={order.status} payme_status={order.payme_status}'))
        for t in tickets:
            self.stdout.write(
                f'  ticket #{t.pk} status={t.status} available_quantity={t.available_quantity}'
            )
        self.stdout.write(self.style.SUCCESS('Done. Buyer dashboard should show paid order / downloadable PDFs.'))

    def _resolve_order(self, *, order_id: int | None, email: str) -> Order:
        if order_id:
            order = Order.objects.filter(pk=order_id).first()
            if not order:
                raise CommandError(f'Order #{order_id} not found.')
            if email:
                order_email = (
                    (order.guest_email or '')
                    or (order.user.email if order.user_id else '')
                    or ''
                ).strip().lower()
                if order_email and order_email != email:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Order #{order_id} email={order_email!r} does not match --email={email!r}; continuing anyway.'
                        )
                    )
            return order

        # Prefer non-paid stuck orders for this email, newest first.
        qs = Order.objects.filter(
            Q(guest_email__iexact=email) | Q(user__email__iexact=email)
        ).order_by('-id')
        stuck = qs.filter(status__in=('pending_payment', 'cancelled', 'canceled', 'pending')).first()
        if stuck:
            return stuck
        any_order = qs.first()
        if not any_order:
            raise CommandError(f'No orders found for email={email!r}.')
        self.stdout.write(
            self.style.WARNING(
                f'No stuck pending/cancelled order for {email!r}; using newest order #{any_order.pk} '
                f'status={any_order.status}.'
            )
        )
        return any_order

    def _print_order(self, order: Order) -> None:
        buyer = order.guest_email or (order.user.email if order.user_id else None) or '—'
        self.stdout.write(
            f'Found order #{order.pk} status={order.status} buyer={buyer} '
            f'payme_tid={order.payme_transaction_id!r} ticket_ids={order.ticket_ids} '
            f'total={order.total_paid_by_buyer or order.total_amount} {order.currency}'
        )
