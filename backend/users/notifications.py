"""
Transactional marketplace emails (offers + seller post-sale).
Dispatched explicitly from view code after commits where noted — keeps one clear path
and correct transaction boundaries (OfferViewSet, confirm_order_payment).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone as django_timezone

from .currency import currency_symbol, iso4217_for_ticket_listing, money_amount_for_api

logger = logging.getLogger(__name__)


def _frontend_origin() -> str:
    return (getattr(settings, 'FRONTEND_ORIGIN', '') or '').strip().rstrip('/')


def dashboard_url() -> str:
    base = _frontend_origin()
    return f'{base}/dashboard' if base else ''


def format_money_for_email(amount, currency_iso: str) -> str:
    """Human-readable amount + symbol for templates (aligned with API money rules)."""
    iso = (currency_iso or 'ILS').strip().upper()
    sym = currency_symbol(iso)
    try:
        api_val = money_amount_for_api(Decimal(str(amount)), iso)
    except Exception:
        api_val = amount
    if iso == 'ILS':
        return f'{sym}{api_val}'
    return f'{sym}{api_val} ({iso})'


def _event_name_from_ticket(ticket) -> str:
    if not ticket:
        return 'Unknown event'
    if ticket.event:
        return ticket.event.name or 'Unknown event'
    return (ticket.event_name or '').strip() or 'Unknown event'


def _send_notification(
    subject: str,
    template_basename: str,
    to_email: str,
    context: dict,
    *,
    fail_silently: bool = True,
) -> None:
    if not (to_email or '').strip():
        logger.info('notifications: skip send — empty recipient for %s', template_basename)
        return
    ctx = {
        'site_name': 'TradeTix',
        'dashboard_url': dashboard_url(),
        **context,
    }
    try:
        text_body = render_to_string(f'emails/{template_basename}.txt', ctx)
        html_body = render_to_string(f'emails/{template_basename}.html', ctx)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email.strip()],
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=fail_silently)
        logger.info('notifications: sent %s to %s', template_basename, to_email)
    except Exception:
        logger.exception('notifications: failed %s to %s', template_basename, to_email)


def notify_new_offer(offer) -> None:
    """Buyer created an initial offer — email the seller."""
    ticket = offer.ticket
    seller = ticket.seller if ticket else None
    if not seller or not (seller.email or '').strip():
        return
    cur = (offer.currency or iso4217_for_ticket_listing(ticket)).strip().upper()
    buyer = offer.buyer
    ctx = {
        'event_name': _event_name_from_ticket(ticket),
        'amount_display': format_money_for_email(offer.amount, cur),
        'currency_code': cur,
        'counterparty_name': buyer.username if buyer else 'A buyer',
        'offer_id': offer.id,
    }
    subject = f'TradeTix — New offer on {ctx["event_name"]}'
    _send_notification(subject, 'offer_new', seller.email, ctx)


def notify_counter_offer(new_offer, previous_offer) -> None:
    """A counter-offer was created. Email the recipient (the party who must respond next)."""
    ticket = new_offer.ticket
    round_count = int(new_offer.offer_round_count or 0)
    # After seller counters (round 1), buyer receives. After buyer counters (round 2), seller receives.
    if round_count == 1:
        recipient = new_offer.buyer
        role_hint = 'the seller has sent you a counter-offer'
    elif round_count == 2:
        recipient = ticket.seller if ticket else None
        role_hint = 'the buyer has sent you a counter-offer'
    else:
        return
    if not recipient or not (recipient.email or '').strip():
        return
    cur = (new_offer.currency or iso4217_for_ticket_listing(ticket)).strip().upper()
    ctx = {
        'event_name': _event_name_from_ticket(ticket),
        'amount_display': format_money_for_email(new_offer.amount, cur),
        'currency_code': cur,
        'role_hint': role_hint,
        'offer_id': new_offer.id,
        'quantity': new_offer.quantity or 1,
    }
    subject = f'TradeTix — Counter-offer for {ctx["event_name"]}'
    _send_notification(subject, 'offer_counter', recipient.email, ctx)


def notify_offer_accepted(offer) -> None:
    """Offer accepted — tell the buyer to complete payment before checkout expires."""
    buyer = offer.buyer
    if not buyer or not (buyer.email or '').strip():
        return
    ticket = offer.ticket
    cur = (offer.currency or iso4217_for_ticket_listing(ticket)).strip().upper()
    checkout_deadline = offer.checkout_expires_at
    checkout_str = None
    if checkout_deadline is not None:
        checkout_str = django_timezone.localtime(checkout_deadline).strftime('%Y-%m-%d %H:%M %Z')
    ctx = {
        'event_name': _event_name_from_ticket(ticket),
        'amount_display': format_money_for_email(offer.amount, cur),
        'currency_code': cur,
        'offer_id': offer.id,
        'checkout_expires_at': checkout_str,
    }
    subject = f'TradeTix — Offer accepted — complete payment for {ctx["event_name"]}'
    _send_notification(subject, 'offer_accepted', buyer.email, ctx)


def notify_seller_ticket_sold_escrow(order) -> None:
    """After payment: seller knows sale is final and payout is escrowed."""
    ticket = getattr(order, 'ticket', None)
    if ticket is None and getattr(order, 'ticket_id', None):
        from .models import Ticket

        ticket = Ticket.objects.filter(pk=order.ticket_id).select_related('seller', 'event').first()
    if ticket is None and (getattr(order, 'ticket_ids', None) or []):
        from .models import Ticket

        first_id = order.ticket_ids[0]
        ticket = Ticket.objects.filter(pk=first_id).select_related('seller', 'event').first()
    if not ticket:
        return
    seller = ticket.seller
    if not seller or not (seller.email or '').strip():
        return
    cur = (order.currency or 'ILS').strip().upper()
    paid = order.total_paid_by_buyer if order.total_paid_by_buyer is not None else order.total_amount
    ctx = {
        'event_name': (order.event_name or '').strip() or _event_name_from_ticket(ticket),
        'order_id': order.id,
        'buyer_paid_display': format_money_for_email(paid, cur),
        'currency_code': cur,
        'quantity': order.quantity or 1,
    }
    subject = f'TradeTix — Your tickets sold (order #{order.id})'
    _send_notification(subject, 'order_seller_escrow', seller.email, ctx)
