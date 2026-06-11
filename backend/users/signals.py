"""
Signals for ticket alerts.

Marketplace offer/order emails are not sent via signals: see users.notifications
(dispatch from OfferViewSet and confirm_order_payment) to control timing vs DB transactions.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order, Ticket, TicketAlert
from .payout_ledger import ensure_seller_payout_for_order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Ticket)
def notify_ticket_alerts(sender, instance, created, **kwargs):
    """
    When a new ticket is created for an event, notify event-level and artist-level subscribers.
    """
    try:
        if created and instance.status == 'active' and instance.event:
            event = instance.event
            alerts = TicketAlert.objects.filter(
                event=event,
                notified=False,
            )
            for alert in alerts:
                print(f'Alerting {alert.email} (event {event.pk})')
                alert.notified = True
                from django.utils import timezone
                alert.notified_at = timezone.now()
                alert.save(update_fields=['notified', 'notified_at'])

            if event.artist_id:
                artist_alerts = TicketAlert.objects.filter(
                    artist_id=event.artist_id,
                    event__isnull=True,
                    notified=False,
                )
                for alert in artist_alerts:
                    print(f'Alerting {alert.email} (artist {event.artist_id})')
                    alert.notified = True
                    from django.utils import timezone
                    alert.notified_at = timezone.now()
                    alert.save(update_fields=['notified', 'notified_at'])
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



