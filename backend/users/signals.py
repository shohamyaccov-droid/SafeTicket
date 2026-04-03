"""
Signals for ticket alerts.

Marketplace offer/order emails are not sent via signals: see users.notifications
(dispatch from OfferViewSet and confirm_order_payment) to control timing vs DB transactions.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Ticket, TicketAlert


@receiver(post_save, sender=Ticket)
def notify_ticket_alerts(sender, instance, created, **kwargs):
    """
    When a new ticket is created for an event, notify all users who signed up for alerts
    """
    # Only process if this is a new ticket (created=True) and it's active
    if created and instance.status == 'active' and instance.event:
        # Find all alerts for this event that haven't been notified yet
        alerts = TicketAlert.objects.filter(
            event=instance.event,
            notified=False
        )
        
        # Print alert message for each email
        for alert in alerts:
            print(f'Alerting {alert.email}')
            
            # Mark as notified (but don't send actual email yet - just console print as requested)
            alert.notified = True
            from django.utils import timezone
            alert.notified_at = timezone.now()
            alert.save()




