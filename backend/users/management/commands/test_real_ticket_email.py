"""Send a real ticket-receipt email with a signed PDF download link.

Finds the newest paid Order that has a Ticket (+ PDF) attached. If none exist,
creates a dummy sold Ticket with a valid PDF and a paid Order so the signed
URL in the email can be verified on Render.

Usage:
  python manage.py test_real_ticket_email
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from users.models import Artist, Event, Order, Ticket
from users.secure_ticket_storage import random_ticket_storage_name
from users.ticket_download_tokens import build_ticket_download_token
from users.utils.emails import send_receipt_with_pdf

User = get_user_model()

TEST_RECIPIENT = 'shohamyaccov@gmail.com'
DUMMY_SELLER_USERNAME = 'test_real_ticket_email_bot'
DUMMY_EVENT_NAME = 'TradeTix download-link QA (dummy)'

MINIMAL_PDF_BYTES = (
    b'%PDF-1.4\n'
    b'1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n'
    b'2 0 obj<< /Type /Pages /Kids [] /Count 0 >>endobj\n'
    b'trailer<< /Root 1 0 R >>\n'
    b'%%EOF\n'
)


class Command(BaseCommand):
    help = (
        'Send the paid-order ticket email to shohamyaccov@gmail.com using a real '
        'ticket PDF (or a dummy ticket if none exist) so the signed download URL can be verified.'
    )

    def handle(self, *args, **options):
        created_dummy = False
        order = _latest_paid_order_with_ticket()
        if order is None:
            self.stdout.write('No paid order with an attached ticket PDF found. Creating a dummy ticket + order...')
            order = _create_dummy_paid_order()
            created_dummy = True

        ticket = order.ticket
        self.stdout.write(
            f'Using order #{order.pk} ticket #{ticket.pk} '
            f'(created_dummy={created_dummy}, pdf={bool(ticket.pdf_file)}).'
        )
        self.stdout.write(f'Sending receipt via Resend HTTP to {TEST_RECIPIENT}...')

        try:
            send_receipt_with_pdf(TEST_RECIPIENT, order)
        except Exception as exc:
            raise CommandError(f'Failed to send: {exc.__class__.__name__}: {exc}') from exc

        download_url = _signed_download_url(order, ticket)
        self.stdout.write(self.style.SUCCESS(
            f'Email sent to {TEST_RECIPIENT} for order #{order.pk} / ticket #{ticket.pk}.'
        ))
        if download_url:
            self.stdout.write(f'Signed download URL:\n{download_url}')
        else:
            self.stdout.write(
                self.style.WARNING(
                    'API_PUBLIC_ORIGIN is unset, so the email may not include an absolute download link. '
                    'Set it (e.g. https://safeticket-api.onrender.com) and re-run.'
                )
            )


def _latest_paid_order_with_ticket():
    return (
        Order.objects.filter(status='paid', ticket_id__isnull=False)
        .exclude(ticket__pdf_file='')
        .select_related('ticket', 'user')
        .order_by('-id')
        .first()
    )


def _create_dummy_paid_order() -> Order:
    seller, _ = User.objects.get_or_create(
        username=DUMMY_SELLER_USERNAME,
        defaults={
            'email': 'test-real-ticket-email-bot@tradetix.local',
            'role': 'seller',
        },
    )
    event = Event.objects.order_by('-id').first()
    if event is None:
        artist, _ = Artist.objects.get_or_create(name='TradeTix QA Artist')
        event = Event.objects.create(
            artist=artist,
            name=DUMMY_EVENT_NAME,
            date=timezone.now() + timedelta(days=30),
            venue='ישראל',
            city='תל אביב',
            country='IL',
        )

    ticket = Ticket(
        seller=seller,
        event=event,
        event_name=event.name,
        event_date=event.date,
        venue=event.venue,
        original_price=Decimal('50.00'),
        asking_price=Decimal('50.00'),
        status='sold',
        available_quantity=0,
        custom_section_text='QA download test',
        row='1',
        seat_numbers='1',
    )
    ticket.pdf_file.save(
        random_ticket_storage_name('.pdf'),
        ContentFile(MINIMAL_PDF_BYTES),
        save=False,
    )
    ticket.save()

    order = Order.objects.create(
        user=None,
        guest_email=TEST_RECIPIENT,
        ticket=ticket,
        status='paid',
        quantity=1,
        total_amount=Decimal('50.00'),
        total_paid_by_buyer=Decimal('50.00'),
        ticket_ids=[ticket.pk],
        event_name=event.name,
        currency='ILS',
    )
    return order


def _signed_download_url(order: Order, ticket: Ticket) -> str:
    api_base = (getattr(settings, 'API_PUBLIC_ORIGIN', '') or '').strip().rstrip('/')
    token = build_ticket_download_token(int(ticket.pk), int(order.pk))
    path = f'/api/users/tickets/{int(ticket.pk)}/download_pdf/?dl={quote(token)}'
    if api_base:
        return f'{api_base}{path}'
    return path
