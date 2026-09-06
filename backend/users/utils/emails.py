"""
Email utilities for OTP, offer notifications, receipts, and branded test emails.
All customer-facing messages are sent as HTML with a plain-text fallback.
"""
import base64
import logging
import os
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

RESEND_FROM_EMAIL = 'TradeTix <onboarding@resend.dev>'
RESEND_API_URL = 'https://api.resend.com/emails'


def _resend_from_email() -> str:
    """Prefer a verified domain From; sandbox onboarding@resend.dev can only mail the Resend account owner."""
    env_from = (os.environ.get('RESEND_FROM_EMAIL') or '').strip()
    if env_from:
        return env_from
    settings_from = (getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip()
    return settings_from or RESEND_FROM_EMAIL


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


def _resend_attachment_payloads(attachments: list[tuple[str, bytes, str]] | None) -> list[dict]:
    payloads = []
    for filename, content, _mimetype in attachments or []:
        raw = content.encode('utf-8') if isinstance(content, str) else bytes(content or b'')
        payloads.append({
            'filename': filename,
            'content': base64.b64encode(raw).decode('ascii'),
        })
    return payloads


def _resend_api_key() -> str:
    if 'RESEND_API_KEY' in os.environ:
        return (os.environ.get('RESEND_API_KEY') or '').strip()
    return (getattr(settings, 'RESEND_API_KEY', '') or '').strip()


def _smtp_configured() -> bool:
    host = (getattr(settings, 'EMAIL_HOST', '') or '').strip()
    user = (getattr(settings, 'EMAIL_HOST_USER', '') or '').strip()
    return bool(host and user)


def buyer_deliverable_email(order) -> str:
    """Real buyer inbox: registered user email, else guest email. Skip cart-token placeholders."""
    from users.cart_identity import is_cart_token_email

    registered = ''
    if getattr(order, 'user_id', None):
        registered = (getattr(getattr(order, 'user', None), 'email', None) or '').strip()
    guest = (getattr(order, 'guest_email', None) or '').strip()
    for candidate in (registered, guest):
        if candidate and '@' in candidate and not is_cart_token_email(candidate):
            return candidate
    return ''


def send_paid_order_receipt(order_or_id, *, source: str = '') -> tuple[bool, str]:
    """
    Same synchronous ticket/receipt send as the PayMe webhook and send_order_receipt.
    Returns (ok, message) and never raises — callers show `message` in admin/CLI.
    Reloads the order from DB so admin/webhook instances are not missing relations.
    """
    order_id = getattr(order_or_id, 'pk', None) or getattr(order_or_id, 'id', None) or order_or_id
    try:
        from users.models import Order

        order = (
            Order.objects.select_related('user', 'ticket', 'ticket__event', 'ticket__seller')
            .filter(pk=order_id)
            .first()
        )
        if not order:
            msg = f'Order #{order_id} not found.'
            logger.error('send_paid_order_receipt: %s source=%s', msg, source)
            return False, msg
        if getattr(order, 'status', None) not in ('paid', 'completed'):
            msg = f'Order #{order.pk} status={order.status!r} (expected paid/completed).'
            logger.error('send_paid_order_receipt: %s source=%s', msg, source)
            return False, msg
        recipient = buyer_deliverable_email(order)
        if not recipient:
            msg = f'Order #{order.pk} has no deliverable buyer email.'
            logger.error('send_paid_order_receipt: %s source=%s', msg, source)
            return False, msg
        send_receipt_with_pdf(recipient, order)
        logger.info(
            'send_paid_order_receipt: sent order_id=%s source=%s recipient=%s',
            order.pk,
            source,
            recipient,
        )
        return True, f'Email sent successfully to {recipient} (order #{order.pk}).'
    except Exception as exc:
        msg = f'Order #{order_id}: {exc}'
        logger.error(
            'send_paid_order_receipt failed order_id=%s source=%s error=%s',
            order_id,
            source,
            (str(exc) or repr(exc))[:500],
            exc_info=True,
        )
        return False, msg


def dispatch_paid_order_receipt_email(order_or_id, *, source: str = '') -> bool:
    """Webhook-safe wrapper: send receipt, never raise."""
    ok, _message = send_paid_order_receipt(order_or_id, source=source)
    return ok


def queue_paid_order_receipt_email(order_or_id, *, source: str = '') -> None:
    """Send the paid-order receipt after the current request/transaction commits.

    PayMe webhooks must return 200 quickly. SMTP/Resend/PDF generation is slow and
    used to block the Gunicorn worker, which made the buyer's status poll time out.
    Tests keep the send synchronous so assertions stay deterministic.
    """
    import threading

    from django.db import close_old_connections, transaction

    order_id = getattr(order_or_id, 'pk', None) or getattr(order_or_id, 'id', None) or order_or_id

    if getattr(settings, 'TESTING', False):
        dispatch_paid_order_receipt_email(order_or_id, source=source)
        return

    def _run():
        close_old_connections()
        try:
            dispatch_paid_order_receipt_email(order_id, source=source)
        except Exception:
            logger.error(
                'queued paid receipt email crashed order_id=%s source=%s',
                order_id,
                source,
                exc_info=True,
            )
        finally:
            close_old_connections()

    def _start():
        threading.Thread(
            target=_run,
            name=f'tradetix-paid-receipt-{order_id}',
            daemon=False,
        ).start()

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_start)
    else:
        _start()


def _send_django_email(
    *,
    subject: str,
    to_email: str,
    html_body: str,
    text_body: str = '',
    attachments: list[tuple[str, bytes, str]] | None = None,
    template_basename: str = '',
    fail_silently: bool = False,
) -> int:
    from_email = (getattr(settings, 'DEFAULT_FROM_EMAIL', '') or '').strip() or RESEND_FROM_EMAIL
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body or html_body,
        from_email=from_email,
        to=[to_email],
    )
    if html_body:
        message.attach_alternative(html_body, 'text/html')
    for filename, content, mimetype in attachments or []:
        raw = content.encode('utf-8') if isinstance(content, str) else bytes(content or b'')
        message.attach(filename, raw, mimetype or 'application/pdf')
    try:
        sent = message.send(fail_silently=False)
        logger.info(
            'send_django_email: sent template=%s recipient=%s backend=%s',
            template_basename,
            to_email,
            getattr(settings, 'EMAIL_BACKEND', ''),
        )
        return int(sent or 0)
    except Exception as exc:
        logger.error(
            'send_django_email: SMTP failed template=%s recipient=%s subject=%s error=%s',
            template_basename,
            to_email,
            subject,
            (str(exc) or repr(exc))[:500],
            exc_info=True,
        )
        if fail_silently:
            return 0
        raise


def _post_resend_http(api_key: str, payload: dict) -> dict:
    """POST to Resend's HTTPS API. Never uses Django's SMTP backend."""
    import requests

    response = requests.post(
        RESEND_API_URL,
        json=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f'Resend HTTP {response.status_code}: {(response.text or "")[:400]}'
        )
    try:
        data = response.json() if response.content else {}
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {'id': 'sent'}


def send_resend_email(
    *,
    subject: str,
    to_email: str,
    html_body: str,
    text_body: str = '',
    attachments: list[tuple[str, bytes, str]] | None = None,
    template_basename: str = '',
    fail_silently: bool = False,
) -> int:
    recipient = (to_email or '').strip()
    if not recipient:
        logger.warning('send_resend_email: empty recipient for template=%s', template_basename)
        return 0

    api_key = _resend_api_key()
    if not api_key:
        msg = 'RESEND_API_KEY is not configured'
        logger.error('send_resend_email: %s template=%s recipient=%s', msg, template_basename, recipient)
        if fail_silently:
            return 0
        raise RuntimeError(msg)

    payload = {
        'from': _resend_from_email(),
        'to': [recipient],
        'subject': subject,
        'html': html_body,
    }
    if text_body:
        payload['text'] = text_body
    attachment_payloads = _resend_attachment_payloads(attachments)
    if attachment_payloads:
        payload['attachments'] = attachment_payloads

    try:
        result = _post_resend_http(api_key, payload)
        logger.info(
            'send_resend_email: sent template=%s recipient=%s resend_id=%s',
            template_basename,
            recipient,
            (result or {}).get('id'),
        )
        return 1
    except Exception as exc:
        logger.error(
            'send_resend_email: Resend HTTP API failed template=%s recipient=%s subject=%s error=%s',
            template_basename,
            recipient,
            subject,
            (str(exc) or repr(exc))[:500],
            exc_info=True,
        )
        if fail_silently:
            return 0
        raise


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
    kwargs = {
        'subject': subject,
        'to_email': recipient,
        'html_body': html_body,
        'text_body': text_body,
        'attachments': attachments,
        'template_basename': template_basename,
        'fail_silently': fail_silently,
    }
    smtp_ok = _smtp_configured()
    resend_ok = bool(_resend_api_key())

    def _send_via_resend_http() -> int:
        # Named args only — never reuse SMTP kwargs / never call _send_django_email.
        return send_resend_email(
            subject=subject,
            to_email=recipient,
            html_body=html_body,
            text_body=text_body,
            attachments=attachments,
            template_basename=template_basename,
            fail_silently=False,
        )

    # Render blocks outbound SMTP (Errno 101 Network is unreachable). When a
    # Resend API key is present, send only via HTTPS — do not touch Django SMTP.
    if resend_ok:
        try:
            sent = _send_via_resend_http()
            if sent:
                return sent
        except Exception:
            logger.error(
                'send_branded_email: Resend HTTP failed template=%s recipient=%s',
                template_basename,
                recipient,
                exc_info=True,
            )
            if fail_silently:
                return 0
            raise
        if fail_silently:
            return 0
        raise RuntimeError('Resend send failed')

    if smtp_ok:
        try:
            sent = _send_django_email(**kwargs)
            if sent:
                return sent
        except Exception:
            logger.error(
                'send_branded_email: SMTP failed and RESEND_API_KEY is not set '
                'template=%s recipient=%s',
                template_basename,
                recipient,
                exc_info=True,
            )
            if fail_silently:
                return 0
            raise
        if fail_silently:
            return 0
        raise RuntimeError('SMTP send returned 0')

    if getattr(settings, 'TESTING', False):
        return _send_django_email(**kwargs)
    logger.error(
        'send_branded_email: no email transport (set EMAIL_HOST + EMAIL_HOST_USER or RESEND_API_KEY) '
        'template=%s recipient=%s',
        template_basename,
        recipient,
    )
    if fail_silently:
        return 0
    raise RuntimeError('No email transport configured')


def _collect_pdf_files_from_order(order):
    """
    Collect ticket file bytes for the receipt email.
    Uses the same Cloudinary-authenticated fetch as download_pdf — FieldFile.open()
    fails/hangs on private assets and used to abort or stall the whole send.
    A missing PDF must not block the email; signed download links still go out.
    """
    from users.secure_ticket_storage import fetch_ticket_file_field_bytes

    from ..models import Ticket

    ticket_ids = _order_ticket_ids(order)
    pdf_files = []
    for tid in ticket_ids:
        try:
            ticket = Ticket.objects.filter(pk=tid).first()
            if not ticket or not ticket.pdf_file:
                continue
            content = fetch_ticket_file_field_bytes(ticket.pdf_file, validate_magic=False)
            if not content:
                continue
            head = bytes(content)[:8]
            if head.startswith(b'%PDF'):
                filename = f'ticket_{tid}.pdf'
            elif head.startswith(b'\xff\xd8\xff'):
                filename = f'ticket_{tid}.jpg'
            elif len(head) >= 8 and head.startswith(b'\x89PNG\r\n\x1a\n'):
                filename = f'ticket_{tid}.png'
            else:
                filename = f'ticket_{tid}.bin'
            pdf_files.append((filename, bytes(content)))
        except Exception as e:
            logger.warning('Could not attach PDF for ticket %s: %s', tid, e)
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
        sent = send_branded_email(
            subject=subject,
            to_email=recipient_email,
            template_basename='purchase_receipt',
            context=context,
            attachments=attachments,
        )
        if not sent:
            raise RuntimeError(
                f'Email provider accepted 0 messages for {recipient_email} (order {getattr(order, "id", "?")}).'
            )
        logger.info(f'Receipt with PDF sent to {recipient_email} (order {getattr(order, "id", "?")})')
    except Exception as e:
        logger.error(
            'Failed to send receipt to %s (order %s): %s',
            recipient_email,
            getattr(order, 'id', '?'),
            e,
            exc_info=True,
        )
        raise


def send_test_welcome_email(email_address: str) -> int:
    """Used by the send_test_email management command to verify Resend + HTML rendering."""
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
