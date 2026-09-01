from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from users.models import Order, Ticket

logger = logging.getLogger(__name__)

# Short cart hold (browse → reserve). Pending PayMe handoff uses a wider grace window.
DEFAULT_PENDING_PAYMENT_GRACE_MINUTES = 60

PAYME_COMPLETED_STATUS_TOKENS = (
    'success',
    'succeeded',
    'completed',
    'paid',
    'captured',
    'approved',
    'authorized',
    'authorised',
    'pre_auth',
    'preauth',
    'admin_force_paid',
)

# Explicit failure tokens from PayMe webhook / status fields — only then may we cancel a sale-id order.
PAYME_FAILED_STATUS_TOKENS = (
    'fail',
    'failed',
    'declined',
    'error',
    'reject',
    'rejected',
    'void',
    'cancelled',
    'canceled',
)


@dataclass(frozen=True)
class AbandonedOrderCleanupResult:
    inspected: int
    cancelled: int
    restored_quantity: int
    released_tickets: int
    skipped_payme_completed: int
    skipped_payme_sale_pending: int = 0


def payme_status_looks_completed(raw_status: str | None) -> bool:
    status = (raw_status or '').strip().lower()
    if not status or payme_status_looks_failed(status):
        return False
    return any(token in status for token in PAYME_COMPLETED_STATUS_TOKENS)


def payme_status_looks_failed(raw_status: str | None) -> bool:
    status = (raw_status or '').strip().lower().replace('-', '_')
    if not status:
        return False
    # Whole-segment match avoids 'authorized' containing nothing from fail list;
    # 'cancel' would false-positive inside unrelated strings — use explicit tokens.
    return any(token in status for token in PAYME_FAILED_STATUS_TOKENS)


def payme_sale_explicitly_failed(order: Order) -> bool:
    """
    True only with positive evidence the PayMe sale failed.

    Primary signal: payme_status from webhook (failed/declined/…).
    Optional: settings.PAYME_CONFIRM_FAILURE_VIA_API + users.payments.query_payme_sale_failed.
    Never treat missing/initialized status as failure — that is the Apple Pay delay case.
    """
    if payme_status_looks_failed(order.payme_status):
        return True

    if not getattr(settings, 'PAYME_CONFIRM_FAILURE_VIA_API', False):
        return False

    try:
        from users import payments as payme_payments

        query_fn = getattr(payme_payments, 'query_payme_sale_failed', None)
        if not callable(query_fn):
            return False
        return bool(query_fn(order))
    except Exception:
        logger.exception(
            'PayMe failure confirmation failed for order %s; refusing abandoned cancel',
            getattr(order, 'pk', None),
        )
        return False


def _restore_held_ticket(order: Order) -> int:
    """Restore quantity held by a pending_payment order on a single ticket row."""
    if not order.held_ticket_id or not order.held_quantity:
        return 0

    ticket = Ticket.objects.select_for_update().filter(pk=order.held_ticket_id).first()
    if not ticket:
        return 0

    restored = int(order.held_quantity)
    ticket.available_quantity = (ticket.available_quantity or 0) + restored
    if (ticket.available_quantity or 0) > 0:
        ticket.status = 'active'
    ticket.reserved_at = None
    ticket.locked_until = None
    ticket.reserved_by = None
    ticket.reservation_email = None
    ticket.save(
        update_fields=[
            'available_quantity',
            'status',
            'reserved_at',
            'locked_until',
            'reserved_by',
            'reservation_email',
            'updated_at',
        ]
    )
    return restored


def _release_reserved_ticket_ids(ticket_ids) -> int:
    released = 0
    normalized_ids = []
    for tid in ticket_ids or []:
        try:
            normalized_ids.append(int(tid))
        except (TypeError, ValueError):
            continue

    for ticket in Ticket.objects.select_for_update().filter(pk__in=sorted(set(normalized_ids))):
        if ticket.status != 'reserved':
            continue
        ticket.status = 'active'
        ticket.reserved_at = None
        ticket.locked_until = None
        ticket.reserved_by = None
        ticket.reservation_email = None
        ticket.save(
            update_fields=[
                'status',
                'reserved_at',
                'locked_until',
                'reserved_by',
                'reservation_email',
                'updated_at',
            ]
        )
        released += 1
    return released


def ticket_ids_for_pending_order(order: Order) -> list[int]:
    ids = []
    seen = set()
    for raw in list(getattr(order, 'ticket_ids', None) or []):
        try:
            tid = int(raw)
        except (TypeError, ValueError):
            continue
        if tid not in seen:
            seen.add(tid)
            ids.append(tid)
    extra = getattr(order, 'ticket_id', None)
    if extra:
        tid = int(extra)
        if tid not in seen:
            ids.append(tid)
    return ids


def release_pending_payment_inventory(order: Order) -> tuple[int, int]:
    """Restore held quantity and flip reserved rows back to active. Caller holds the row lock."""
    restored = _restore_held_ticket(order)
    released = _release_reserved_ticket_ids(ticket_ids_for_pending_order(order))
    return restored, released


def mark_pending_payment_cancelled(order: Order, *, clear_confirm_token: bool = True) -> None:
    """Mark a locked pending_payment order cancelled and drop the PayMe confirm token."""
    order.status = 'cancelled'
    update_fields = ['status', 'held_ticket', 'held_quantity', 'updated_at']
    if clear_confirm_token:
        order.payment_confirm_token = None
        update_fields.append('payment_confirm_token')
    order.held_ticket = None
    order.held_quantity = 0
    order.save(update_fields=update_fields)
    from users.coupons import release_coupon_redemption

    release_coupon_redemption(order)


def cancel_abandoned_pending_payment_orders(
    *,
    older_than_minutes: int | None = None,
    dry_run: bool = False,
) -> AbandonedOrderCleanupResult:
    """
    Cancel pending_payment orders abandoned after checkout handoff and release inventory.

    Protections for Apple Pay / delayed webhooks:
    - Default grace window is 60 minutes (not the 10-minute cart hold).
    - Orders with payme_status that looks successful/authorized are skipped.
    - Orders with a stored payme_transaction_id are NOT cancelled unless PayMe has
      explicitly confirmed failure (failed/declined status). Ambiguous 'initialized'
      sales stay open so a late webhook can still finalize.
    """
    if older_than_minutes is None:
        older_than_minutes = int(
            getattr(settings, 'PAYME_PENDING_PAYMENT_GRACE_MINUTES', DEFAULT_PENDING_PAYMENT_GRACE_MINUTES)
        )
    if older_than_minutes < 1:
        older_than_minutes = DEFAULT_PENDING_PAYMENT_GRACE_MINUTES

    cutoff = timezone.now() - timedelta(minutes=older_than_minutes)
    candidate_ids = list(
        Order.objects.filter(status='pending_payment', created_at__lt=cutoff)
        .order_by('id')
        .values_list('id', flat=True)
    )

    inspected = len(candidate_ids)
    cancelled = 0
    restored_quantity = 0
    released_tickets = 0
    skipped_payme_completed = 0
    skipped_payme_sale_pending = 0

    for order_id in candidate_ids:
        with transaction.atomic():
            order = Order.objects.select_for_update().filter(pk=order_id, status='pending_payment').first()
            if not order:
                continue

            if payme_status_looks_completed(order.payme_status):
                skipped_payme_completed += 1
                logger.warning(
                    'Skipping abandoned cleanup for order %s because PayMe status is %r',
                    order.id,
                    order.payme_status,
                )
                continue

            has_payme_sale = bool((order.payme_transaction_id or '').strip())
            if has_payme_sale and not payme_sale_explicitly_failed(order):
                skipped_payme_sale_pending += 1
                logger.warning(
                    'Skipping abandoned cleanup for order %s: payme_transaction_id set and '
                    'PayMe has not explicitly confirmed failure (status=%r)',
                    order.id,
                    order.payme_status,
                )
                continue

            if dry_run:
                cancelled += 1
                restored_quantity += int(order.held_quantity or 0)
                released_tickets += len(order.ticket_ids or [])
                continue

            restored, released = release_pending_payment_inventory(order)
            restored_quantity += restored
            released_tickets += released
            mark_pending_payment_cancelled(order)
            cancelled += 1
            logger.info('Cancelled abandoned pending_payment order %s and released held inventory', order.id)

    return AbandonedOrderCleanupResult(
        inspected=inspected,
        cancelled=cancelled,
        restored_quantity=restored_quantity,
        released_tickets=released_tickets,
        skipped_payme_completed=skipped_payme_completed,
        skipped_payme_sale_pending=skipped_payme_sale_pending,
    )
