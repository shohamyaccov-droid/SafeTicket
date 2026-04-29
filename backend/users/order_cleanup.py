from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from users.models import Order, Ticket

logger = logging.getLogger(__name__)

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
)


@dataclass(frozen=True)
class AbandonedOrderCleanupResult:
    inspected: int
    cancelled: int
    restored_quantity: int
    released_tickets: int
    skipped_payme_completed: int


def payme_status_looks_completed(raw_status: str | None) -> bool:
    status = (raw_status or '').strip().lower()
    return bool(status) and any(token in status for token in PAYME_COMPLETED_STATUS_TOKENS)


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
    ticket.reserved_by = None
    ticket.reservation_email = None
    ticket.save(
        update_fields=[
            'available_quantity',
            'status',
            'reserved_at',
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
        ticket.reserved_by = None
        ticket.reservation_email = None
        ticket.save(update_fields=['status', 'reserved_at', 'reserved_by', 'reservation_email', 'updated_at'])
        released += 1
    return released


def cancel_abandoned_pending_payment_orders(
    *,
    older_than_minutes: int = 15,
    dry_run: bool = False,
) -> AbandonedOrderCleanupResult:
    """
    Cancel pending_payment orders abandoned after checkout handoff and release inventory.

    Orders with a PayMe status that already looks successful/authorized are skipped so a delayed
    webhook can still finalize them instead of losing a real payment.
    """
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

            if dry_run:
                cancelled += 1
                restored_quantity += int(order.held_quantity or 0)
                released_tickets += len(order.ticket_ids or [])
                continue

            restored_quantity += _restore_held_ticket(order)
            released_tickets += _release_reserved_ticket_ids(order.ticket_ids or [])

            order.status = 'cancelled'
            order.payment_confirm_token = None
            order.held_ticket = None
            order.held_quantity = 0
            order.save(
                update_fields=[
                    'status',
                    'payment_confirm_token',
                    'held_ticket',
                    'held_quantity',
                    'updated_at',
                ]
            )
            cancelled += 1
            logger.info('Cancelled abandoned pending_payment order %s and released held inventory', order.id)

    return AbandonedOrderCleanupResult(
        inspected=inspected,
        cancelled=cancelled,
        restored_quantity=restored_quantity,
        released_tickets=released_tickets,
        skipped_payme_completed=skipped_payme_completed,
    )
