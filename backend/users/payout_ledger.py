"""
Seller payout ledger helpers — create Payout rows when orders are paid.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from django.db import transaction

from .models import Order, Payout, User

logger = logging.getLogger(__name__)


def _decimal_or_zero(value) -> Decimal:
    if value is None:
        return Decimal('0.00')
    return Decimal(value).quantize(Decimal('0.01'))


def resolve_order_seller(order: Order) -> User | None:
    """Return the ticket seller for this order, if resolvable."""
    ticket = order.ticket
    if ticket is None and order.ticket_ids:
        from .models import Ticket

        ticket = Ticket.objects.filter(pk=order.ticket_ids[0]).select_related('seller').first()
    if ticket is None:
        return None
    return ticket.seller


def payout_amounts_from_order(order: Order) -> tuple[Decimal, Decimal, Decimal] | None:
    """
    Derive (total_sale_amount, platform_commission, net_payout) from order pricing fields.
    Returns None when the order is not ready for a ledger row.
    """
    if order.status not in ('paid', 'completed'):
        return None

    total = order.total_paid_by_buyer or order.total_amount
    if total is None:
        return None

    buyer_fee = _decimal_or_zero(order.buyer_service_fee)
    seller_fee = _decimal_or_zero(order.seller_service_fee)
    commission = (buyer_fee + seller_fee).quantize(Decimal('0.01'))

    if order.net_seller_revenue is not None:
        net = _decimal_or_zero(order.net_seller_revenue)
    else:
        net = (_decimal_or_zero(total) - commission).quantize(Decimal('0.01'))

    return _decimal_or_zero(total), commission, net


def ensure_payout_for_order(order: Order) -> Payout | None:
    """
    Create a PENDING Payout for a paid order if one does not exist.
    Idempotent for the same order.
    """
    if order.pk is None:
        return None

    amounts = payout_amounts_from_order(order)
    if amounts is None:
        return None

    seller = resolve_order_seller(order)
    if seller is None:
        logger.warning('ensure_payout_for_order: no seller for order_id=%s', order.pk)
        return None

    total_sale_amount, platform_commission, net_payout = amounts

    with transaction.atomic():
        existing = Payout.objects.filter(order_id=order.pk).first()
        if existing:
            return existing

        payout = Payout(
            order=order,
            seller=seller,
            total_sale_amount=total_sale_amount,
            platform_commission=platform_commission,
            net_payout=net_payout,
            status=Payout.Status.PENDING,
        )
        payout.full_clean()
        payout.save()
        logger.info(
            'Created Payout id=%s order_id=%s seller_id=%s net=%s',
            payout.pk,
            order.pk,
            seller.pk,
            net_payout,
        )
        return payout


def sync_user_bank_fields_from_payout_details(user: User) -> bool:
    """
    Copy structured bank fields from legacy payout_details JSON when columns are empty.
    Returns True if any field was updated.
    """
    raw = (getattr(user, 'payout_details', None) or '').strip()
    if not raw:
        return False
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, dict):
        return False

    updates = {}
    if not (user.account_holder_name or '').strip() and data.get('account_holder_name'):
        updates['account_holder_name'] = str(data['account_holder_name']).strip()[:200]
    bank_src = data.get('bank_name') or data.get('bank_name_or_code')
    if not (user.bank_name or '').strip() and bank_src:
        updates['bank_name'] = str(bank_src).strip()[:120]
    if not (user.branch_number or '').strip() and data.get('branch_number'):
        updates['branch_number'] = str(data['branch_number']).strip()[:20]
    if not (user.account_number or '').strip() and data.get('account_number'):
        updates['account_number'] = str(data['account_number']).strip()[:30]

    if not updates:
        return False
    for key, val in updates.items():
        setattr(user, key, val)
    user.save(update_fields=list(updates.keys()) + ['updated_at'])
    return True
