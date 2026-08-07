"""
Signals for ticket alerts.

Marketplace offer/order emails are not sent via signals: see users.notifications
(dispatch from OfferViewSet and confirm_order_payment) to control timing vs DB transactions.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Order, Ticket, TicketAlert
from .payout_ledger import ensure_seller_payout_for_order
from .ticket_alert_matching import (
    listing_available_quantity,
    matching_alerts_filter,
    prioritize_alerts,
)

logger = logging.getLogger(__name__)


def _notify_matching_alerts(alerts_qs, available: int, scope_label: str):
    """Mark matching waitlist entries as notified, specific quantities first."""
    matching = alerts_qs.filter(matching_alerts_filter(available))
    for alert in prioritize_alerts(matching):
        print(
            f'Alerting {alert.email} ({scope_label}) '
            f'desired={alert.desired_quantity!r} available={available}'
        )
        alert.notified = True
        alert.notified_at = timezone.now()
        alert.save(update_fields=['notified', 'notified_at'])


@receiver(post_save, sender=Ticket)
def notify_ticket_alerts(sender, instance, created, **kwargs):
    """
    When a new ticket is created for an event, notify event-level and artist-level
    subscribers whose desired_quantity fits the listing size (null/0 = any).
    """
    try:
        if created and instance.status == 'active' and instance.event:
            event = instance.event
            available = listing_available_quantity(instance)
            _notify_matching_alerts(
                TicketAlert.objects.filter(event=event, notified=False),
                available,
                f'event {event.pk}',
            )

            if event.artist_id:
                _notify_matching_alerts(
                    TicketAlert.objects.filter(
                        artist_id=event.artist_id,
                        event__isnull=True,
                        notified=False,
                    ),
                    available,
                    f'artist {event.artist_id}',
                )
    except Exception:
        logger.exception('notify_ticket_alerts: suppressed error (ticket save must not fail)')

@receiver(post_save, sender=Order)
def create_seller_payout_ledger_on_paid_order(sender, instance, **kwargs):
    """When an order is paid, ensure a Payout ledger row exists for admin manual settlement."""
    if instance.status not in ('paid', 'completed'):
        return
    try:
        ensure_seller_payout_for_order(instance)
    except Exception:
        logger.exception(
            'create_seller_payout_ledger_on_paid_order: suppressed error order_id=%s',
            instance.pk,
        )



