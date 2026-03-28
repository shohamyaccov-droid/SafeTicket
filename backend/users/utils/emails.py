"""
Email utilities for OTP, offer notifications, and receipts with PDF attachments.
Receipts: Hebrew HTML + plain text; secure per-ticket download links; SMTP-ready.
"""
import html
import logging
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


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
    """Absolute API URLs for download_pdf (guest: email query); empty if API_PUBLIC_ORIGIN unset."""
    api_base = (getattr(settings, 'API_PUBLIC_ORIGIN', '') or '').strip().rstrip('/')
    if not api_base:
        return []
    guest_email = (getattr(order, 'guest_email', None) or '').strip()
    rows = []
    for tid in _order_ticket_ids(order):
        if guest_email:
            url = f'{api_base}/api/users/tickets/{tid}/download_pdf/?email={quote(guest_email)}'
            label = f'הורדת כרטיס #{tid} (קישור מאובטח לאימייל זה)'
        else:
            url = f'{api_base}/api/users/tickets/{tid}/download_pdf/'
            label = f'הורדת כרטיס #{tid} (לאחר התחברות לאתר עם אותו חשבון)'
        rows.append((label, url))
    return rows


def _receipt_subject_body_html(order, recipient_is_guest: bool):
    raw_event = getattr(order, 'event_name', None) or (
        order.ticket.event.name if getattr(order, 'ticket', None) and order.ticket.event else 'הזמנתך'
    )
    event_name = html.escape(str(raw_event))
    total = html.escape(str(getattr(order, 'total_amount', '')))
    qty = int(getattr(order, 'quantity', 1) or 1)
    order_id = getattr(order, 'id', '')
    frontend = (getattr(settings, 'FRONTEND_ORIGIN', '') or '').strip().rstrip('/')
    dash_link = f'{frontend}/dashboard' if frontend else ''

    link_rows = _build_download_link_rows(order)
    links_html = ''
    if link_rows:
        items = ''.join(
            f'<li style="margin:8px 0;"><a href="{html.escape(url)}">{html.escape(label)}</a></li>'
            for label, url in link_rows
        )
        links_html = f'<ul style="padding-right:20px;" dir="rtl">{items}</ul>'
    elif not recipient_is_guest and dash_link:
        links_html = (
            f'<p>ניתן להוריד את הכרטיסים מעמוד <a href="{html.escape(dash_link)}">הדשבורד</a> לאחר התחברות.</p>'
        )

    guest_note = ''
    if recipient_is_guest:
        guest_note = (
            '<p style="color:#334155;font-size:14px;">שמרו מייל זה: הקישורים למעלה תקפים עבור כתובת האימייל '
            'שהוזנה בעת הרכישה.</p>'
        )
    elif dash_link:
        guest_note = (
            f'<p style="color:#334155;font-size:14px;">מומלץ גם להתחבר ל־<a href="{html.escape(dash_link)}">האתר</a> '
            'וניהול ההזמנות תחת &quot;הרכישות שלי&quot;.</p>'
        )

    html_body = f'''<!DOCTYPE html>
<html lang="he"><head><meta charset="utf-8" /></head>
<body style="font-family:Arial,sans-serif;direction:rtl;text-align:right;background:#f8fafc;color:#0f172a;line-height:1.5;">
<div style="max-width:560px;margin:0 auto;padding:24px;background:#ffffff;border-radius:12px;border:1px solid #e2e8f0;">
  <h1 style="font-size:20px;color:#0f766e;margin:0 0 12px;">SafeTicket — תודה שרכשתם אצלנו</h1>
  <p style="margin:0 0 16px;">שלום,</p>
  <p style="margin:0 0 16px;">זוהי <strong>קבלה עבור הרכישה</strong> שלכם. פרטי ההזמנה מוצגים למטה.</p>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:15px;" dir="rtl">
    <tr><td style="padding:6px 0;color:#64748b;">אירוע</td><td style="padding:6px 0;font-weight:600;">{event_name}</td></tr>
    <tr><td style="padding:6px 0;color:#64748b;">כמות כרטיסים</td><td style="padding:6px 0;">{qty}</td></tr>
    <tr><td style="padding:6px 0;color:#64748b;">סכום כולל</td><td style="padding:6px 0;">₪{total}</td></tr>
    <tr><td style="padding:6px 0;color:#64748b;">מספר הזמנה</td><td style="padding:6px 0;">#{html.escape(str(order_id))}</td></tr>
  </table>
  <h2 style="font-size:16px;margin:24px 0 8px;color:#0f172a;">כרטיסים (קובץ PDF)</h2>
  <p style="margin:0 0 8px;">צורפו קבצי PDF למייל זה. בנוסף, אפשר להוריד דרך הקישורים הבאים:</p>
  {links_html or '<p style="color:#64748b;">המערכת תשלח את הכרטיסים כצרופות; אם אין קישורים — התחברו לאתר לצפייה בהורדות.</p>'}
  {guest_note}
  <p style="margin:24px 0 0;font-size:13px;color:#94a3b8;">בברכה,<br/>צוות SafeTicket</p>
</div></body></html>'''

    text_lines = [
        'SafeTicket — קבלה והודעת תודה',
        '',
        f'אירוע: {raw_event}',
        f'כמות: {qty}',
        f'סכום כולל: ₪{order.total_amount}',
        f'מספר הזמנה: #{order_id}',
        '',
        'צורפו קבצי PDF למייל (אם קיימים).',
    ]
    for label, url in link_rows:
        text_lines.append(f'{label}: {url}')
    if not link_rows and dash_link and not recipient_is_guest:
        text_lines.append(f'דשבורד: {dash_link}')
    text_lines.extend(['', '— צוות SafeTicket'])
    text_body = '\n'.join(text_lines)

    subject = f'SafeTicket — קבלה עבור {raw_event} (הזמנה #{order_id})'
    return subject, text_body, html_body


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
        msg = EmailMultiAlternatives(
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
        msg = EmailMultiAlternatives(
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
    Send order receipt (Hebrew HTML + text) with PDF ticket attachments.
    pdf_files: list of (filename, file_content_bytes) tuples; default loads from order tickets.
    """
    if not recipient_email:
        logger.warning('send_receipt_with_pdf: no recipient email; skipping')
        return

    recipient_is_guest = not getattr(order, 'user_id', None)
    subject, text_body, html_body = _receipt_subject_body_html(order, recipient_is_guest)

    if pdf_files is None:
        pdf_files = _collect_pdf_files_from_order(order)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        msg.attach_alternative(html_body, 'text/html')
        for item in pdf_files:
            if isinstance(item, tuple):
                filename, content = item
                msg.attach(filename, content, 'application/pdf')
            elif hasattr(item, 'read'):
                item.seek(0)
                msg.attach(
                    item.name.split('/')[-1] if hasattr(item, 'name') else 'ticket.pdf',
                    item.read(),
                    'application/pdf',
                )
        msg.send(fail_silently=False)
        logger.info(f'Receipt with PDF sent to {recipient_email} (order {getattr(order, "id", "?")})')
    except Exception as e:
        logger.exception(f'Failed to send receipt to {recipient_email}: {e}')
        raise
