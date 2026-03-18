"""
Email utilities for OTP, offer notifications, and receipts with PDF attachments.
"""
import logging
from django.core.mail import EmailMessage
from django.conf import settings

logger = logging.getLogger(__name__)


def _collect_pdf_files_from_order(order):
    """
    Collect PDF file contents from tickets in an order.
    Returns list of (filename, bytes) tuples for send_receipt_with_pdf.
    """
    from ..models import Ticket

    ticket_ids = getattr(order, 'ticket_ids', None) or []
    if not ticket_ids and order.ticket:
        ticket_ids = [order.ticket.id]
    pdf_files = []
    for tid in ticket_ids:
        try:
            t = Ticket.objects.get(id=tid)
            if t.pdf_file:
                t.pdf_file.open('rb')
                content = t.pdf_file.read()
                t.pdf_file.close()
                filename = t.pdf_file.name.split('/')[-1] if '/' in t.pdf_file.name else t.pdf_file.name or f'ticket_{tid}.pdf'
                pdf_files.append((filename, content))
        except Exception as e:
            logger.warning(f'Could not attach PDF for ticket {tid}: {e}')
    return pdf_files


def send_otp_email(user, otp):
    """
    Send OTP verification email to the user.
    """
    subject = 'SafeTicket - Verify your email'
    body = f'''Hello {user.username or user.email},

Your verification code is: {otp}

This code expires in 10 minutes. Enter it on the verification page to activate your account.

If you did not register for SafeTicket, please ignore this email.

— SafeTicket Team
'''
    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.send(fail_silently=False)
        logger.info(f'OTP email sent to {user.email}')
    except Exception as e:
        logger.exception(f'Failed to send OTP email to {user.email}: {e}')
        raise


def send_offer_notification(recipient_email, offer_details):
    """
    Notify the recipient when an offer is made on their listing.
    offer_details: dict with keys like event_name, amount, buyer_username, etc.
    """
    event_name = offer_details.get('event_name', 'Unknown Event')
    amount = offer_details.get('amount', 'N/A')
    buyer_username = offer_details.get('buyer_username', 'A buyer')
    subject = f'SafeTicket - New offer on {event_name}'
    body = f'''Hello,

{buyer_username} has made an offer of ₪{amount} on your listing for {event_name}.

Log in to SafeTicket to accept or reject the offer.

— SafeTicket Team
'''
    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        msg.send(fail_silently=False)
        logger.info(f'Offer notification sent to {recipient_email}')
    except Exception as e:
        logger.exception(f'Failed to send offer notification to {recipient_email}: {e}')
        raise


def send_receipt_with_pdf(recipient_email, order, pdf_files=None):
    """
    Send order receipt email with PDF ticket attachments.
    pdf_files: list of (filename, file_content_bytes) tuples, or list of open file handles.
    """
    event_name = getattr(order, 'event_name', None) or (order.ticket.event_name if order.ticket else 'Your Order')
    total = getattr(order, 'total_amount', 'N/A')
    quantity = getattr(order, 'quantity', 1)
    subject = f'SafeTicket - Receipt for {event_name}'
    body = f'''Hello,

Thank you for your purchase!

Order details:
- Event: {event_name}
- Quantity: {quantity} ticket(s)
- Total: ₪{total}

Your ticket(s) are attached to this email. You can also download them from your SafeTicket account.

— SafeTicket Team
'''
    if pdf_files is None:
        pdf_files = _collect_pdf_files_from_order(order)
    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        for item in pdf_files:
            if isinstance(item, tuple):
                filename, content = item
                msg.attach(filename, content, 'application/pdf')
            elif hasattr(item, 'read'):
                item.seek(0)
                msg.attach(item.name.split('/')[-1] if hasattr(item, 'name') else 'ticket.pdf', item.read(), 'application/pdf')
        msg.send(fail_silently=False)
        logger.info(f'Receipt with PDF sent to {recipient_email}')
    except Exception as e:
        logger.exception(f'Failed to send receipt to {recipient_email}: {e}')
        raise
