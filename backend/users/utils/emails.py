"""
Email utilities for OTP, offer notifications, receipts, and branded test emails.
All customer-facing messages are sent as HTML with a plain-text fallback.
"""
import logging
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _frontend_origin() -> str:
    return (getattr(settings, 'FRONTEND_ORIGIN', '') or '').strip().rstrip('/')


def _dashboard_url() -> str:
    base = _frontend_origin()
    return f'{base}/dashboard' if base else ''


def _login_url() -> str:
    base = _frontend_origin()
    return f'{base}/login' if base else ''


def _site_context(extra: dict | None = None) -> dict:
    ctx = {
        'site_name': 'TradeTix',
        'frontend_origin': _frontend_origin(),
        'dashboard_url': _dashboard_url(),
        'login_url': _login_url(),
        'support_email': getattr(settings, 'SUPPORT_EMAIL', '') or getattr(settings, 'DEFAULT_FROM_EMAIL', ''),
    }
    if extra:
        ctx.update(extra)
    return ctx


def build_branded_email(template_basename: str, context: dict) -> tuple[str, str]:
    ctx = _site_context(context)
    text_body = render_to_string(f'emails/{template_basename}.txt', ctx).strip()
    html_body = render_to_string(f'emails/{template_basename}.html', ctx)
    return text_body, html_body


def send_branded_email(
    *,
    subject: str,
    to_email: str,
    template_basename: str,
    context: dict | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
    fail_silently: bool = False,
) -> int:
    recipient = (to_email or '').strip()
    if not recipient:
        logger.warning('send_branded_email: empty recipient for template=%s', template_basename)
        return 0

    text_body, html_body = build_branded_email(template_basename, context or {})
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    msg.attach_alternative(html_body, 'text/html')
    for filename, content, mimetype in attachments or []:
        msg.attach(filename, content, mimetype)
    return msg.send(fail_silently=fail_silently)


def _collect_pdf_files_from_order(order):
    """
    Collect PDF file contents from tickets in an order.
    Returns list of (filename, bytes) tuples for send_receipt_with_pdf.
    """
    from ..models import Ticket

    ticket_ids = getattr(order, 'ticket_ids', None) or []
    if not ticket_ids and order.ticket_id:
        ticket_ids = [order.ticket_id]
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


def _order_ticket_ids(order):
    ids = list(getattr(order, 'ticket_ids', None) or [])
    if not ids and order.ticket_id:
        ids = [order.ticket_id]
    return ids


def _build_download_link_rows(order):
    """Absolute signed URLs for download_pdf; empty if API_PUBLIC_ORIGIN unset."""
    from ..ticket_download_tokens import build_ticket_download_token

    api_base = (getattr(settings, 'API_PUBLIC_ORIGIN', '') or '').strip().rstrip('/')
    if not api_base:
        return []
    oid = int(getattr(order, 'id', 0) or 0)
    rows = []
    for tid in _order_ticket_ids(order):
        token = build_ticket_download_token(int(tid), oid)
        url = f'{api_base}/api/users/tickets/{int(tid)}/download_pdf/?dl={quote(token)}'
        label = f'הורדת כרטיס #{tid} (קישור חתום ומוגבל בזמן)'
        rows.append((label, url))
    return rows


def _receipt_email_context(order, recipient_is_guest: bool):
    from ..notifications import format_money_for_email

    raw_event = getattr(order, 'event_name', None) or (
        order.ticket.event.name if getattr(order, 'ticket', None) and order.ticket.event else 'הזמנתך'
    )
    cur = (getattr(order, 'currency', None) or 'ILS').strip().upper()
    paid = order.total_paid_by_buyer if order.total_paid_by_buyer is not None else order.total_amount
    total_disp = format_money_for_email(paid, cur)
    qty = int(getattr(order, 'quantity', 1) or 1)
    order_id = getattr(order, 'id', '')

    link_rows = _build_download_link_rows(order)
    subject = f'TradeTix — הקבלה והכרטיסים שלך עבור {raw_event} (הזמנה #{order_id})'
    return subject, {
        'event_name': raw_event,
        'quantity': qty,
        'currency_code': cur,
        'total_display': total_disp,
        'order_id': order_id,
        'download_links': [{'label': label, 'url': url} for label, url in link_rows],
        'recipient_is_guest': recipient_is_guest,
        'has_attachments': True,
    }


def send_otp_email(user, otp):
    """
    Send OTP verification email to the user.
    """
    subject = 'TradeTix — קוד אימות למייל שלך'
    try:
        send_branded_email(
            subject=subject,
            to_email=user.email,
            template_basename='otp_verification',
            context={
                'user_name': user.username or user.email,
                'otp': otp,
                'expires_minutes': 10,
                'cta_url': _login_url(),
                'cta_label': 'התחבר למערכת',
            },
        )
        logger.info(f'OTP email sent to {user.email}')
    except Exception as e:
        logger.exception(f'Failed to send OTP email to {user.email}: {e}')
        raise


def send_offer_notification(recipient_email, offer_details):
    """
    Legacy entry point — prefer users.notifications.notify_new_offer(offer).
    Kept for backwards compatibility; does not load an Offer instance here.
    """
    logger.warning('send_offer_notification(dict) is deprecated; use notify_new_offer(offer)')
    event_name = offer_details.get('event_name', 'Unknown Event')
    amount = offer_details.get('amount', 'N/A')
    buyer_username = offer_details.get('buyer_username', 'A buyer')
    subject = f'TradeTix — התקבלה הצעה חדשה עבור {event_name}'
    try:
        send_branded_email(
            subject=subject,
            to_email=recipient_email,
            template_basename='offer_legacy',
            context={
                'event_name': event_name,
                'amount_display': amount,
                'counterparty_name': buyer_username,
                'cta_url': _dashboard_url(),
                'cta_label': 'צפה בהצעה',
            },
        )
        logger.info(f'Offer notification sent to {recipient_email}')
    except Exception as e:
        logger.exception(f'Failed to send offer notification to {recipient_email}: {e}')
        raise


def send_receipt_with_pdf(recipient_email, order, pdf_files=None):
    """
    Send order receipt (Hebrew HTML + text) with PDF ticket attachments.
    pdf_files: list of (filename, file_content_bytes) tuples; default loads from order tickets.
    """
    if not recipient_email:
        logger.warning('send_receipt_with_pdf: no recipient email; skipping')
        return

    recipient_is_guest = not getattr(order, 'user_id', None)
    subject, context = _receipt_email_context(order, recipient_is_guest)

    if pdf_files is None:
        pdf_files = _collect_pdf_files_from_order(order)

    try:
        attachments = []
        for item in pdf_files:
            if isinstance(item, tuple):
                filename, content = item
                attachments.append((filename, content, 'application/pdf'))
            elif hasattr(item, 'read'):
                item.seek(0)
                attachments.append((
                    item.name.split('/')[-1] if hasattr(item, 'name') else 'ticket.pdf',
                    item.read(),
                    'application/pdf',
                ))
        send_branded_email(
            subject=subject,
            to_email=recipient_email,
            template_basename='purchase_receipt',
            context=context,
            attachments=attachments,
        )
        logger.info(f'Receipt with PDF sent to {recipient_email} (order {getattr(order, "id", "?")})')
    except Exception as e:
        logger.exception(f'Failed to send receipt to {recipient_email}: {e}')
        raise


def send_test_welcome_email(email_address: str) -> int:
    """Used by the send_test_email management command to verify SMTP + HTML rendering."""
    return send_branded_email(
        subject='TradeTix — ברוכים הבאים לחוויית כרטיסים בטוחה',
        to_email=email_address,
        template_basename='welcome_test',
        context={
            'user_name': 'חבר/ת TradeTix',
            'cta_url': _frontend_origin() or _dashboard_url(),
            'cta_label': 'בקרו ב-TradeTix',
        },
    )
