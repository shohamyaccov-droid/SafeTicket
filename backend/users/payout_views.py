"""
Admin payout management and seller wallet APIs.
"""
from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Order, SellerPayout
from .pricing import compute_payout_eligible_date
from .views import _admin_staff_or_superuser, csrf_required
from wallets.services import mark_seller_payout_paid, release_eligible_wallet_payouts


def _quantize(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal('0.01'))


def _sum_seller_obligation(qs) -> Decimal:
    totals = qs.aggregate(net=Sum('net_payout'), bonus=Sum('seller_bonus_amount'))
    return _quantize(Decimal(totals['net'] or 0) + Decimal(totals['bonus'] or 0))


def _seller_bank_payload(user) -> dict:
    return {
        'account_holder_name': (user.account_holder_name or '').strip() or None,
        'bank_name': (user.bank_name or '').strip() or None,
        'branch_number': (user.branch_number or '').strip() or None,
        'account_number': (user.account_number or '').strip() or None,
        'email': (user.email or '').strip() or None,
        'phone': (user.phone_number or '').strip() or None,
    }


def _order_escrow_status(order: Order | None) -> str:
    if order is None:
        return 'unknown'
    return (order.payout_status or 'locked').strip()


def _platform_fee_percent(payout: SellerPayout) -> str | None:
    """
    Historical fee percent applied to THIS order, derived from amounts frozen on
    the order/payout rows at purchase time (never from live GlobalFeeSettings).

    Base = listing amount the fee was charged on:
      prefer order.final_negotiated_price (stored at checkout),
      else total_paid − buyer_service_fee, else net_payout.
    """
    fee = _quantize(payout.platform_fee)
    order = payout.order

    base = None
    if order is not None and order.final_negotiated_price is not None:
        base = _quantize(order.final_negotiated_price)
    if (base is None or base <= 0) and order is not None and order.buyer_service_fee is not None:
        base = _quantize((payout.total_paid or 0) - order.buyer_service_fee)
    if base is None or base <= 0:
        base = _quantize(payout.net_payout)
    if base <= 0:
        return None

    percent = (fee / base * Decimal('100')).quantize(Decimal('0.01'))
    # Display-friendly: '15.00' → '15', '7.50' → '7.5'
    text = format(percent, 'f').rstrip('0').rstrip('.')
    return text or '0'


def _promote_orders_past_escrow_threshold(*, seller=None) -> int:
    qs = (
        Order.objects.select_related('ticket__event')
        .filter(
            payout_status='locked',
            payout_eligible_date__isnull=False,
            payout_eligible_date__lte=timezone.now(),
        )
    )
    if seller is not None:
        qs = qs.filter(seller_payout__seller=seller)

    promoted_ids = []
    now = timezone.now()
    for order in qs.iterator():
        if order.ticket_id is None:
            continue
        eligible_at = compute_payout_eligible_date(order.ticket)
        if eligible_at and now > eligible_at:
            promoted_ids.append(order.pk)

    if not promoted_ids:
        return 0
    return Order.objects.filter(pk__in=promoted_ids, payout_status='locked').update(payout_status='eligible')


def _admin_payout_summary() -> dict:
    base = SellerPayout.objects.exclude(payout_status=SellerPayout.PayoutStatus.CANCELLED)
    pending_qs = base.filter(payout_status=SellerPayout.PayoutStatus.PENDING)
    available_qs = pending_qs.filter(order__payout_status='eligible')
    transferred_qs = base.filter(payout_status=SellerPayout.PayoutStatus.TRANSFERRED)

    pending_net = _sum_seller_obligation(pending_qs)
    available_net = _sum_seller_obligation(available_qs)
    pending_fees = _quantize(pending_qs.aggregate(s=Sum('platform_fee'))['s'])
    total_revenue = _quantize(base.aggregate(s=Sum('platform_fee'))['s'])
    total_transferred = _sum_seller_obligation(transferred_qs)

    return {
        'total_pending_owed': str(pending_net),
        'total_available_owed': str(available_net),
        'total_pending_platform_fees': str(pending_fees),
        'total_platform_revenue': str(total_revenue),
        'total_transferred_to_sellers': str(total_transferred),
        'pending_count': pending_qs.count(),
        'transferred_count': transferred_qs.count(),
    }


def _serialize_admin_payout(payout: SellerPayout) -> dict:
    seller = payout.seller
    order = payout.order
    return {
        'id': payout.pk,
        'order_id': payout.order_id,
        'event_name': (order.event_name or '').strip() if order else None,
        'order_status': order.status if order else None,
        'order_escrow_status': _order_escrow_status(order),
        'seller_id': payout.seller_id,
        'seller_username': seller.username if seller else None,
        'seller_email': seller.email if seller else None,
        'seller_bank': _seller_bank_payload(seller) if seller else {},
        'total_paid': str(payout.total_paid),
        'platform_fee': str(payout.platform_fee),
        'platform_fee_percent': _platform_fee_percent(payout),
        'seller_ticket_net': str(payout.net_payout),
        'seller_bonus_amount': str(payout.seller_bonus_amount),
        'net_payout': str(payout.net_payout),
        'total_seller_payout': str(payout.total_seller_payout),
        'payout_status': payout.payout_status,
        'created_at': payout.created_at.isoformat() if payout.created_at else None,
        'transferred_at': payout.transferred_at.isoformat() if payout.transferred_at else None,
    }


def _wallet_summary_for_seller(user) -> dict:
    from wallets.models import UserWallet

    wallet = UserWallet.objects.filter(user=user).first()
    base = SellerPayout.objects.filter(seller=user).exclude(
        payout_status=SellerPayout.PayoutStatus.CANCELLED
    )
    transferred = base.filter(payout_status=SellerPayout.PayoutStatus.TRANSFERRED)

    total_earned = _sum_seller_obligation(transferred)
    pending_funds = _quantize(getattr(wallet, 'locked_balance', Decimal('0.00')))
    available_funds = _quantize(getattr(wallet, 'available_balance', Decimal('0.00')))

    return {
        'total_earned': str(total_earned),
        'pending_funds': str(pending_funds),
        'available_funds': str(available_funds),
        'currency': 'ILS',
    }


def _serialize_wallet_transaction(payout: SellerPayout) -> dict:
    from wallets.models import WalletTransaction

    order = payout.order
    escrow = _order_escrow_status(order)
    if payout.payout_status == SellerPayout.PayoutStatus.TRANSFERRED:
        display_status = 'paid'
    elif payout.payout_status == SellerPayout.PayoutStatus.CANCELLED:
        display_status = 'cancelled'
    else:
        credit_tx = (
            WalletTransaction.objects.filter(
                seller_payout=payout,
                transaction_type=WalletTransaction.TransactionType.SALE_CREDIT,
            )
            .only('status')
            .first()
        )
        credit_is_available = bool(credit_tx and credit_tx.status == WalletTransaction.Status.COMPLETED)
        if credit_is_available:
            display_status = 'available'
        else:
            display_status = 'pending_event'

    return {
        'id': payout.pk,
        'order_id': payout.order_id,
        'event_name': (order.event_name or '').strip() if order else None,
        'ticket_price': str(payout.total_paid),
        'platform_fee': str(payout.platform_fee),
        'seller_bonus_amount': str(payout.seller_bonus_amount),
        'net_earnings': str(payout.net_payout),
        'total_earnings': str(payout.total_seller_payout),
        'payout_status': payout.payout_status,
        'display_status': display_status,
        'order_escrow_status': escrow,
        'created_at': payout.created_at.isoformat() if payout.created_at else None,
        'transferred_at': payout.transferred_at.isoformat() if payout.transferred_at else None,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_payouts_list(request):
    """List seller payouts for admin financial dashboard."""
    if not _admin_staff_or_superuser(request):
        return Response({'error': 'Permission denied. Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    _promote_orders_past_escrow_threshold()
    release_eligible_wallet_payouts()

    status_filter = (request.query_params.get('status') or 'pending').strip().lower()
    qs = (
        SellerPayout.objects.select_related('seller', 'order')
        .order_by('-created_at')
    )
    if status_filter and status_filter != 'all':
        qs = qs.filter(payout_status=status_filter)

    limit = int(request.query_params.get('limit') or 500)
    limit = max(1, min(limit, 2000))
    rows = [_serialize_admin_payout(p) for p in qs[:limit]]

    return Response({
        'summary': _admin_payout_summary(),
        'payouts': rows,
        'count': len(rows),
    })


@csrf_required
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_payout_mark_paid(request, payout_id: int):
    """Mark a seller payout as transferred (paid to seller bank account)."""
    if not _admin_staff_or_superuser(request):
        return Response({'error': 'Permission denied. Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    payout = SellerPayout.objects.select_related('seller', 'order').filter(pk=payout_id).first()
    if not payout:
        return Response({'error': 'Payout not found.'}, status=status.HTTP_404_NOT_FOUND)

    if payout.payout_status == SellerPayout.PayoutStatus.TRANSFERRED:
        return Response({
            'message': 'Payout already marked as paid.',
            'payout': _serialize_admin_payout(payout),
        })

    if payout.payout_status == SellerPayout.PayoutStatus.CANCELLED:
        return Response({'error': 'Cannot mark a cancelled payout as paid.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payout = mark_seller_payout_paid(payout)
    except ValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    payout.refresh_from_db()
    return Response({
        'message': 'Payout marked as paid.',
        'payout': _serialize_admin_payout(payout),
        'summary': _admin_payout_summary(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_wallet(request):
    """Authenticated seller wallet: earnings summary + transaction history."""
    user = request.user

    _promote_orders_past_escrow_threshold(seller=user)
    release_eligible_wallet_payouts(seller=user)

    payouts = (
        SellerPayout.objects.filter(seller=user)
        .select_related('order')
        .order_by('-created_at')
    )

    return Response({
        'summary': _wallet_summary_for_seller(user),
        'transactions': [_serialize_wallet_transaction(p) for p in payouts],
    })
