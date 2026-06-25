"""
Seller payout ledger — create SellerPayout rows when orders are paid.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from django.db import transaction

from .models import Order, SellerPayout, User

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
    Derive (total_paid, platform_fee, net_payout) from order pricing fields.
    The buyer pays seller price + buyer Security Fee. Seller payout must therefore
    preserve the seller net amount, not re-charge 15% against the gross PayMe amount.
    Returns None when the order is not ready for a ledger row.
    """
    if order.status not in ('paid', 'completed'):
        return None

    total_paid = order.total_paid_by_buyer or order.total_amount
    if total_paid is None:
        return None

    total_paid = _decimal_or_zero(total_paid)
    seller_net = order.net_seller_revenue
    if seller_net is None:
        seller_net = order.final_negotiated_price
    if seller_net is None:
        # Legacy fallback for old paid orders without populated pricing fields.
        _total, _fee, seller_net = SellerPayout.compute_amounts(total_paid)
    seller_net = _decimal_or_zero(seller_net)

    explicit_fee = order.buyer_service_fee or Decimal('0.00')
    explicit_fee += order.seller_service_fee or Decimal('0.00')
    platform_fee = _decimal_or_zero(explicit_fee)
    if platform_fee == Decimal('0.00'):
        platform_fee = _decimal_or_zero(total_paid - seller_net)

    return total_paid, platform_fee, seller_net


def ensure_seller_payout_for_order(order: Order) -> SellerPayout | None:
    """
    Create a pending SellerPayout for a paid order if one does not exist.
    Idempotent for the same order.
    """
    if order.pk is None:
        return None

    amounts = payout_amounts_from_order(order)
    if amounts is None:
        return None

    seller = resolve_order_seller(order)
    if seller is None:
        logger.warning('ensure_seller_payout_for_order: no seller for order_id=%s', order.pk)
        return None

    total_paid, platform_fee, net_payout = amounts

    with transaction.atomic():
        existing = SellerPayout.objects.select_for_update().filter(order_id=order.pk).first()
        if existing:
            amount_fields_changed = (
                existing.total_paid != total_paid
                or existing.platform_fee != platform_fee
                or existing.net_payout != net_payout
            )
            if amount_fields_changed and existing.payout_status == SellerPayout.PayoutStatus.PENDING:
                previous_net = existing.net_payout
                existing.total_paid = total_paid
                existing.platform_fee = platform_fee
                existing.net_payout = net_payout
                existing.full_clean()
                existing.save(update_fields=['total_paid', 'platform_fee', 'net_payout'])
                try:
                    from wallets.services import reconcile_wallet_credit_for_seller_payout

                    reconcile_wallet_credit_for_seller_payout(existing, previous_net)
                except Exception:
                    logger.exception(
                        'Failed to reconcile seller wallet amount for payout_id=%s order_id=%s',
                        existing.pk,
                        order.pk,
                    )
            try:
                from wallets.services import credit_wallet_for_seller_payout

                credit_wallet_for_seller_payout(existing)
            except Exception:
                logger.exception('Failed to reconcile seller wallet for payout_id=%s order_id=%s', existing.pk, order.pk)
            return existing

        payout = SellerPayout(
            order=order,
            seller=seller,
            total_paid=total_paid,
            platform_fee=platform_fee,
            net_payout=net_payout,
            payout_status=SellerPayout.PayoutStatus.PENDING,
        )
        payout.full_clean()
        payout.save()
        logger.info(
            'Created SellerPayout id=%s order_id=%s seller_id=%s net=%s fee=%s',
            payout.pk,
            order.pk,
            seller.pk,
            net_payout,
            platform_fee,
        )
        try:
            from wallets.services import credit_wallet_for_seller_payout

            credit_wallet_for_seller_payout(payout)
        except Exception:
            logger.exception('Failed to credit seller wallet for payout_id=%s order_id=%s', payout.pk, order.pk)
        return payout


# Backward-compatible alias
ensure_payout_for_order = ensure_seller_payout_for_order


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
