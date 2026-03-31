from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.middleware.csrf import get_token


def csrf_required(view):
    """Override DRF's csrf_exempt so CSRF is enforced for cookie-based auth."""
    view.csrf_exempt = False
    return view
from rest_framework import generics, status, viewsets
from rest_framework.throttling import ScopedRateThrottle
from .throttles import (
    AuthLoginScopedThrottle,
    AuthRegisterScopedThrottle,
    OffersMutationScopedThrottle,
)
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.db.models import F, Q, Count, Sum, Exists, OuterRef, Value, Prefetch
from django.db.models.functions import Coalesce
from django.db import transaction
from django.conf import settings as dj_settings
from django.core.files.base import ContentFile
import io
import logging
import secrets
import traceback
import uuid
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


def _apply_order_pricing_fields(order, negotiated_offer, ticket, order_quantity):
    """Persist breakdown after order row exists (create_order / guest_checkout)."""
    breakdown = compute_order_price_breakdown(
        order.total_amount,
        negotiated_offer,
        ticket,
        order_quantity,
    )
    order.final_negotiated_price = breakdown['final_negotiated_price']
    order.buyer_service_fee = breakdown['buyer_service_fee']
    order.total_paid_by_buyer = breakdown['total_paid_by_buyer']
    order.net_seller_revenue = breakdown['net_seller_revenue']
    order.related_offer = negotiated_offer if negotiated_offer else None
    ped = compute_payout_eligible_date(ticket)
    order.payout_eligible_date = ped
    order.payout_status = 'locked'
    if ped is not None and timezone.now() >= ped:
        order.payout_status = 'eligible'
    order.save(
        update_fields=[
            'final_negotiated_price',
            'buyer_service_fee',
            'total_paid_by_buyer',
            'net_seller_revenue',
            'related_offer',
            'payout_eligible_date',
            'payout_status',
            'updated_at',
        ]
    )


def _log_cloudinary_or_storage_error(exc: BaseException, context: str) -> str:
    """Log full exception for ops; return a short message for API (no secrets)."""
    msg = str(exc).strip() or repr(exc)
    logger.exception('Ticket/media upload failed [%s]: %s', context, msg)
    # Common Cloudinary HTTP body is in exc.args or attached message
    for attr in ('http_body', 'message', 'args'):
        raw = getattr(exc, attr, None)
        if raw and isinstance(raw, str) and len(raw) < 2000:
            logger.error('Cloudinary detail [%s] %s=%r', context, attr, raw)
    return msg


def _rollback_tickets(created):
    for t in created:
        try:
            t.delete()
        except Exception:
            logger.warning('Rollback: could not delete ticket pk=%s', getattr(t, 'pk', None), exc_info=True)


def _ticket_pdf_persisted(ticket) -> bool:
    """
    Ticket row must reference a PDF that storage can see.
    Prevents 'ghost' listings when multipart was wrong or upload silently failed.

    Cloudinary RawMediaCloudinaryStorage.exists() uses HTTP HEAD on the delivery URL; many
    raw PDF URLs return 403/405 to HEAD while GET (and Django FieldFile.open) still works.
    Treat failed exists + readable %PDF magic as persisted.
    """
    try:
        ticket.refresh_from_db()
        pf = getattr(ticket, 'pdf_file', None)
        if pf is None:
            return False
        name = (getattr(pf, 'name', None) or '').strip()
        if not name:
            return False
        storage = getattr(pf, 'storage', None)
        use_cloudinary = getattr(settings, 'USE_CLOUDINARY', False)

        if storage is not None and hasattr(storage, 'exists'):
            exists_ok = False
            exists_failed = False
            try:
                exists_ok = bool(storage.exists(name))
            except Exception:
                exists_failed = True
                logger.warning('storage.exists failed ticket pk=%s', ticket.pk, exc_info=True)

            if exists_ok:
                return True

            if use_cloudinary or exists_failed:
                try:
                    pf.open('rb')
                    try:
                        magic = pf.read(5)
                    finally:
                        pf.close()
                    if magic.startswith(b'%PDF'):
                        return True
                except Exception:
                    logger.warning('pdf persistence verify read failed pk=%s', ticket.pk, exc_info=True)

                if use_cloudinary:
                    try:
                        import cloudinary.api

                        public_id = name.replace('\\', '/')
                        cloudinary.api.resource(public_id, resource_type='raw')
                        return True
                    except Exception:
                        logger.warning('cloudinary.api.resource failed pk=%s', ticket.pk, exc_info=True)
                return False
            return False
        return True
    except Exception:
        logger.warning('_ticket_pdf_persisted failed pk=%s', getattr(ticket, 'pk', None), exc_info=True)
        return False
from .serializers import (
    UserRegistrationSerializer, 
    UserSerializer,
    CustomTokenObtainPairSerializer,
    OrderSerializer,
    GuestCheckoutSerializer,
    TicketSerializer,
    TicketListSerializer,
    ProfileOrderSerializer,
    ProfileListingSerializer,
    UpgradeToSellerSerializer,
    EventSerializer,
    EventListSerializer,
    ArtistSerializer,
    ArtistListSerializer,
    TicketAlertSerializer,
    OfferSerializer,
    ContactMessageSerializer,
    EventRequestSerializer,
    build_profile_orders_serialization_context,
    build_listing_primary_order_map,
)
from .models import Order, Ticket, Event, Artist, TicketAlert, Offer, ContactMessage, EventRequest
from .pricing import (
    buyer_charge_from_base_amount,
    compute_order_price_breakdown,
    compute_payout_eligible_date,
    decimal_money,
    expected_buy_now_total,
    expected_negotiated_total_from_offer_base,
    list_price_checkout_amounts,
    payment_amounts_match,
)
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import os

User = get_user_model()


def _user_payload_for_auth_response(request, user):
    """
    Serialize user for login/register/verify responses. Image/storage errors must not 500 the auth flow.
    """
    if user is None:
        return None
    try:
        return UserSerializer(user, context={'request': request}).data
    except Exception:
        logger.exception('UserSerializer failed in auth response for user pk=%s', user.pk)
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'phone_number': user.phone_number or '',
            'payout_details': user.payout_details or '',
            'accepted_escrow_terms': user.accepted_escrow_terms,
            'profile_image': None,
            'is_verified_seller': user.is_verified_seller,
            'is_email_verified': user.is_email_verified,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        }


def _user_from_access_token_str(access_token_str):
    """Map JWT access string to User (matches the account that just authenticated)."""
    if not access_token_str:
        return None
    from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
    from rest_framework_simplejwt.state import token_backend

    try:
        payload = token_backend.decode(str(access_token_str), verify=True)
        uid = payload.get(jwt_api_settings.USER_ID_CLAIM)
        if uid is None:
            return None
        return User.objects.get(**{jwt_api_settings.USER_ID_FIELD: uid})
    except Exception:
        logger.exception('Could not resolve User from access token for login response')
        return None


def _order_pending_checkout_response(order, request):
    """JSON for create_order / guest_checkout: include one-time payment_confirm_token while pending."""
    data = OrderSerializer(order, context={'request': request}).data
    tok = (getattr(order, 'payment_confirm_token', None) or '').strip()
    if order.status == 'pending_payment' and tok:
        data['payment_confirm_token'] = tok
    return Response(data, status=status.HTTP_201_CREATED)


# Cart abandonment timeout (minutes)
RESERVATION_TIMEOUT_MINUTES = 10


def _reject_pending_offers_for_ticket_ids(ticket_ids):
    """When inventory is sold, invalidate competing pending offers on those rows."""
    if not ticket_ids:
        return 0
    return Offer.objects.filter(
        ticket_id__in=list(ticket_ids),
        status='pending',
    ).update(status='rejected')


def _sync_expired_cart_reservation(ticket):
    """
    If reservation TTL passed, release the row so checkout can proceed fairly.
    Mutates and saves ticket when expired.
    """
    if ticket.status != 'reserved' or not ticket.reserved_at:
        return
    cutoff = timezone.now() - timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
    if ticket.reserved_at < cutoff:
        ticket.status = 'active'
        ticket.reserved_at = None
        ticket.reserved_by = None
        ticket.reservation_email = None
        ticket.save(
            update_fields=['status', 'reserved_at', 'reserved_by', 'reservation_email']
        )


def _reservation_blocks_seller_accept_offer(ticket, offer) -> bool:
    """
    True if an active cart reservation should block the seller from accepting this offer.
    Never block when the holder is the same human as offer.buyer (by user pk or guest email).
    """
    if ticket.status != 'reserved' or not ticket.reserved_at:
        return False
    cutoff = timezone.now() - timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
    if ticket.reserved_at < cutoff:
        return False
    rb = ticket.reserved_by_id
    ob = offer.buyer_id
    if rb is not None and ob is not None:
        try:
            return int(rb) != int(ob)
        except (TypeError, ValueError):
            return True
    guest_email = (ticket.reservation_email or '').strip().lower()
    if rb is None and guest_email:
        buyer_email = ''
        if getattr(offer, 'buyer_id', None):
            try:
                buyer_email = (getattr(offer.buyer, 'email', None) or '').strip().lower()
            except Exception:
                buyer_email = ''
        if buyer_email and buyer_email == guest_email:
            return False
        if buyer_email and buyer_email != guest_email:
            return True
    return False


def _group_reservation_blocks_seller_accept_offer(anchor_ticket, offer) -> bool:
    """True if any row in the listing group has a conflicting active reservation vs offer.buyer."""
    if not anchor_ticket.listing_group_id:
        return _reservation_blocks_seller_accept_offer(anchor_ticket, offer)
    for t in Ticket.objects.filter(
        listing_group_id=anchor_ticket.listing_group_id,
        seller_id=anchor_ticket.seller_id,
    ):
        if _reservation_blocks_seller_accept_offer(t, offer):
            return True
    return False


def _group_available_units_for_offer_accept(anchor_ticket, offer) -> int:
    """
    For grouped listings: sum seats the offer buyer can still count toward this offer
    (active rows + rows reserved by the same buyer).
    """
    if not anchor_ticket.listing_group_id:
        return int(anchor_ticket.available_quantity or 0)
    ob = offer.buyer_id
    buyer_email = ''
    if getattr(offer, 'buyer', None):
        buyer_email = (getattr(offer.buyer, 'email', None) or '').strip().lower()
    total = 0
    for t in Ticket.objects.filter(
        listing_group_id=anchor_ticket.listing_group_id,
        seller_id=anchor_ticket.seller_id,
    ).exclude(status__in=('sold', 'rejected', 'pending_payout', 'paid_out')):
        if t.status == 'active':
            total += int(t.available_quantity or 0)
        elif t.status == 'reserved':
            same = False
            if t.reserved_by_id and ob is not None:
                try:
                    same = int(t.reserved_by_id) == int(ob)
                except (TypeError, ValueError):
                    same = False
            if (
                not same
                and not t.reserved_by_id
                and (t.reservation_email or '').strip()
            ):
                ge = (t.reservation_email or '').strip().lower()
                same = bool(buyer_email and ge and buyer_email == ge)
            if same:
                total += int(t.available_quantity or 0)
    return total


class PdfFetchError(Exception):
    """All strategies to load PDF bytes from Cloudinary failed; carries per-strategy errors for diagnostics."""

    def __init__(self, errors):
        self.errors = errors


def _download_ticket_pdf_bytes(ticket):
    """
    Load PDF bytes from Cloudinary-backed FileField. Tries public URL, then signed URL, then storage open().
    """
    import os as _os
    import requests
    import cloudinary.api
    import cloudinary.utils
    from cloudinary.utils import private_download_url

    public_id = (ticket.pdf_file.name or '').replace('\\', '/')

    def _public_id_variants(pid: str):
        """django-cloudinary-storage PREFIX (MEDIA_URL) may or may not match Cloudinary public_id."""
        pid = pid.strip().strip('/')
        if not pid:
            return []
        out = [pid]
        media_prefix = (getattr(settings, 'MEDIA_URL', 'media/') or '').strip().strip('/')
        if media_prefix and pid.startswith(media_prefix + '/'):
            out.append(pid[len(media_prefix) + 1 :])
        elif media_prefix and not pid.startswith(media_prefix):
            out.append(f'{media_prefix}/{pid}')
        seen = set()
        uniq = []
        for x in out:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq

    errors = []

    def _http_get_bytes(label, url):
        if not url or not str(url).startswith('http'):
            return None
        r = requests.get(
            url,
            timeout=90,
            headers={'User-Agent': 'TradeTix-PDF/1.0'},
        )
        r.raise_for_status()
        return r.content

    def _try_pdf_bytes(label, url):
        """Fetch URL; require PDF magic so HTML/JSON error pages do not count as success."""
        body = _http_get_bytes(label, url)
        if body is None:
            return None
        body = body.lstrip(b'\xef\xbb\xbf \t\r\n')
        if not body.startswith(b'%PDF'):
            raise ValueError(f'{label}: response_not_pdf')
        return body

    # 0a) Signed Admin download URL → api.cloudinary.com (works when res.cloudinary.com delivery returns 401)
    if public_id:
        for pid in _public_id_variants(public_id):
            ext = (_os.path.splitext(pid)[1].lstrip('.') or 'pdf').lower()
            try:
                api_dl = private_download_url(pid, ext, resource_type='raw', type='upload')
                return _try_pdf_bytes('private_download_api', api_dl)
            except Exception as e:
                errors.append(('private_download_api', str(e)[:400]))

    # 0) Admin API + delivery URL matrix (version + signature algorithm vary by account)
    if public_id:
        for pid in _public_id_variants(public_id):
            try:
                info = cloudinary.api.resource(pid, resource_type='raw')
            except Exception as e:
                errors.append(('api_resource', str(e)[:400]))
                continue
            cid = (info or {}).get('public_id') or pid
            ver = (info or {}).get('version')

            url_jobs = []
            seen_u = set()
            for u in filter(None, [(info or {}).get('secure_url'), (info or {}).get('url')]):
                if u not in seen_u:
                    seen_u.add(u)
                    url_jobs.append(('api_delivery', u))

            for sign in (True, False):
                for sig_alg in (None, 'sha1', 'sha256'):
                    opts = {
                        'resource_type': 'raw',
                        'type': 'upload',
                        'sign_url': sign,
                        'secure': True,
                    }
                    if ver is not None:
                        opts['version'] = ver
                    if sig_alg:
                        opts['signature_algorithm'] = sig_alg
                    try:
                        url, _ = cloudinary.utils.cloudinary_url(cid, **opts)
                        if url not in seen_u:
                            seen_u.add(url)
                            url_jobs.append((f"cf_{'sig' if sign else 'uns'}_{sig_alg or 'cfg'}", url))
                    except Exception as e:
                        errors.append((f'cf_build', str(e)[:200]))

            for sign in (True, False):
                try:
                    url, _ = cloudinary.utils.cloudinary_url(
                        cid,
                        resource_type='raw',
                        type='upload',
                        sign_url=sign,
                        secure=True,
                        force_version=False,
                    )
                    if url not in seen_u:
                        seen_u.add(url)
                        url_jobs.append((f'cf_nover_{sign}', url))
                except Exception as e:
                    errors.append((f'cf_nover_{sign}', str(e)[:200]))

            if ver is not None:
                try:
                    url, _ = cloudinary.utils.cloudinary_url(
                        cid,
                        resource_type='raw',
                        type='upload',
                        sign_url=True,
                        secure=True,
                        version=ver,
                        long_url_signature=True,
                    )
                    if url not in seen_u:
                        seen_u.add(url)
                        url_jobs.append(('cf_long_sig', url))
                except Exception as e:
                    errors.append(('cf_long_sig', str(e)[:200]))

            for label, url in url_jobs:
                try:
                    return _try_pdf_bytes(label, url)
                except Exception as e:
                    errors.append((label, str(e)[:400]))
            break

    # 1) Public delivery URL (CloudinaryResource / FileField.url)
    try:
        url = ticket.pdf_file.url
        return _try_pdf_bytes('public', url)
    except Exception as e:
        errors.append(('public_url', str(e)[:400]))

    # 2) Explicit unsigned cloudinary_url (raw)
    try:
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type='raw',
            type='upload',
            sign_url=False,
            secure=True,
        )
        return _try_pdf_bytes('unsigned', url)
    except Exception as e:
        errors.append(('unsigned', str(e)[:400]))

    # 3) Signed delivery URL
    try:
        url, _ = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type='raw',
            type='upload',
            sign_url=True,
            secure=True,
        )
        return _try_pdf_bytes('signed', url)
    except Exception as e:
        errors.append(('signed', str(e)[:400]))

    # 4) django-cloudinary-storage FileField (uses requests inside _open)
    try:
        ticket.pdf_file.open('rb')
        try:
            raw = ticket.pdf_file.read()
            if raw and not raw.startswith(b'%PDF'):
                raise ValueError('storage_open: not_pdf')
            return raw
        finally:
            ticket.pdf_file.close()
    except Exception as e:
        errors.append(('storage_open', str(e)[:400]))

    logger.error(
        'download_pdf: all fetch strategies failed for ticket %s (strategy names: %s)',
        ticket.pk,
        [e[0] for e in errors],
    )
    raise PdfFetchError(errors)


def _pdf_magic_bytes_ok(uploaded_file) -> bool:
    """True if file starts with %PDF (PDF signature)."""
    uploaded_file.seek(0)
    head = uploaded_file.read(8)
    uploaded_file.seek(0)
    return bool(head.startswith(b'%PDF'))


def _upload_mime_allowed(uploaded_file, relax: bool) -> bool:
    """
    Strict: application/pdf only (+ magic bytes %PDF).
    Relaxed (testing): also allow common browser fallbacks for real PDFs (octet-stream, empty).
    Reject obvious non-PDF MIME families (images, HTML, etc.) even if magic bytes were spoofed.
    """
    ct = (getattr(uploaded_file, 'content_type', '') or '').strip().lower()
    if ct and not relax:
        blocked_prefixes = ('image/', 'text/', 'video/', 'audio/', 'multipart/')
        if any(ct.startswith(p) for p in blocked_prefixes):
            return False
    if ct == 'application/pdf':
        return _pdf_magic_bytes_ok(uploaded_file)
    if relax and ct in ('application/octet-stream', 'binary/octet-stream', 'application/x-download', ''):
        return _pdf_magic_bytes_ok(uploaded_file)
    return False


def _pdf_reader_for_upload(uploaded_file, relax: bool) -> PdfReader:
    """Page count / split; relaxed mode uses non-strict parser and empty-password decrypt if encrypted."""
    uploaded_file.seek(0)
    reader = PdfReader(uploaded_file, strict=not relax)
    if relax and getattr(reader, 'is_encrypted', False):
        try:
            reader.decrypt('')
        except Exception:
            pass
    return reader


def _is_event_past(ticket):
    """Return True if the ticket's event has already passed."""
    event_date = None
    if ticket.event:
        event_date = ticket.event.date
    elif ticket.event_date:
        event_date = ticket.event_date
    if event_date is None:
        return False  # Legacy ticket without event - allow
    return event_date < timezone.now()


def release_abandoned_carts():
    """
    Self-healing: Release expired ticket reservations and cancel stale pending orders.
    Call lazily at the top of Event/Ticket list endpoints so inventory cleans itself.
    """
    from django.db.models import Q
    cutoff = timezone.now() - timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
    released = 0
    # 1. Expired ticket reservations -> back to active
    expired_tickets = Ticket.objects.filter(
        status='reserved',
        reserved_at__lt=cutoff
    )
    count = expired_tickets.update(
        status='active',
        reserved_at=None,
        reserved_by=None,
        reservation_email=None
    )
    released += count
    # 2. Pending orders older than timeout -> cancelled (if any exist)
    stale_orders = Order.objects.filter(
        status='pending',
        created_at__lt=cutoff
    )
    for order in stale_orders:
        if order.ticket_id:
            Ticket.objects.filter(id=order.ticket_id).update(
                status='active',
                reserved_at=None,
                reserved_by=None,
                reservation_email=None
            )
        for tid in (order.ticket_ids or []):
            Ticket.objects.filter(id=tid).update(
                status='active',
                reserved_at=None,
                reserved_by=None,
                reservation_email=None
            )
    stale_count = stale_orders.update(status='cancelled')
    released += stale_count

    # 3. payment pending orders: release inventory like abandoned carts
    stale_pending = list(
        Order.objects.filter(status='pending_payment', created_at__lt=cutoff)
        .only('id', 'held_ticket_id', 'held_quantity', 'ticket_ids')
    )
    for po in stale_pending:
        _restore_order_held_inventory(po)
        _release_pending_payment_group_reservations(po.ticket_ids or [])
    if stale_pending:
        released += Order.objects.filter(
            pk__in=[x.pk for x in stale_pending]
        ).update(status='cancelled')
    return released


def _restore_order_held_inventory(order):
    """Restore single-row partial quantity held on pending_payment orders."""
    hid = getattr(order, 'held_ticket_id', None) or getattr(order, 'held_ticket', None)
    hq = getattr(order, 'held_quantity', None) or 0
    if hid and hq:
        pk = hid if isinstance(hid, int) else hid.pk
        t = Ticket.objects.filter(pk=pk).first()
        if t:
            t.available_quantity = (t.available_quantity or 0) + int(hq)
            if t.status == 'reserved' and (t.available_quantity or 0) > 0:
                t.status = 'active'
            t.reserved_at = None
            t.reserved_by = None
            t.reservation_email = None
            t.save(
                update_fields=[
                    'available_quantity',
                    'status',
                    'reserved_at',
                    'reserved_by',
                    'reservation_email',
                    'updated_at',
                ]
            )


def _release_pending_payment_group_reservations(ticket_ids):
    for tid in ticket_ids or []:
        Ticket.objects.filter(pk=tid, status='reserved').update(
            status='active',
            reserved_at=None,
            reserved_by=None,
            reservation_email=None,
        )


def _guest_offer_email_matches(negotiated_offer, guest_email: str) -> bool:
    if not negotiated_offer:
        return True
    ge = (guest_email or '').strip().lower()
    be = (negotiated_offer.buyer.email or '').strip().lower()
    return bool(be) and ge == be


def _reserve_rows_for_pending_checkout(available_tickets, user=None, guest_email: str = ''):
    """Hold inventory: active -> reserved; existing reservation must match buyer."""
    guest_email = (guest_email or '').strip()
    now = timezone.now()
    for t in available_tickets:
        if t.status == 'active':
            t.status = 'reserved'
            t.reserved_at = now
            if user and getattr(user, 'is_authenticated', False):
                t.reserved_by = user
                t.reservation_email = None
            else:
                t.reserved_by = None
                t.reservation_email = guest_email or None
            t.save(
                update_fields=[
                    'status',
                    'reserved_at',
                    'reserved_by',
                    'reservation_email',
                    'updated_at',
                ]
            )
        elif t.status == 'reserved':
            if user and getattr(user, 'is_authenticated', False):
                if t.reserved_by_id != user.id:
                    raise PermissionDenied('Reservation does not belong to this buyer.')
            else:
                if (t.reservation_email or '').strip().lower() != guest_email.lower():
                    raise PermissionDenied('Reservation does not belong to this guest email.')
        else:
            raise ValueError('ticket_not_available')


def _verify_reservations_fresh(reserved_before, user=None, guest_email: str = ''):
    """Ensure checkout reservations have not expired (RESERVATION_TIMEOUT_MINUTES)."""
    cutoff = timezone.now() - timedelta(minutes=RESERVATION_TIMEOUT_MINUTES)
    guest_email = (guest_email or '').strip()
    for t in reserved_before:
        t.refresh_from_db()
        if t.status != 'reserved':
            raise ValueError('ticket_state_changed')
        if not t.reserved_at or t.reserved_at < cutoff:
            raise ValueError('reservation_expired')
        if user and getattr(user, 'is_authenticated', False):
            if t.reserved_by_id != user.id:
                raise PermissionDenied('Reservation owner mismatch.')
        else:
            if (t.reservation_email or '').strip().lower() != guest_email.lower():
                raise PermissionDenied('Reservation email mismatch.')


def _finalize_group_sale_ticket_rows(ticket_ids):
    for tid in ticket_ids or []:
        t = Ticket.objects.select_for_update().get(pk=tid)
        t.status = 'sold'
        t.available_quantity = 0
        t.reserved_at = None
        t.reserved_by = None
        t.reservation_email = None
        t.save(
            update_fields=[
                'status',
                'available_quantity',
                'reserved_at',
                'reserved_by',
                'reservation_email',
                'updated_at',
            ]
        )


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint. Returns JWT tokens immediately for instant login.
    OTP verification flow is dormant and can be re-enabled when needed.
    Cross-origin iOS/Safari: JWT in JSON body — CSRF cookie is unreliable under ITP; do not require it here.
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    throttle_classes = [AuthRegisterScopedThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # OTP flow kept dormant for future use (send_otp_email commented to reduce noise)
        # import random
        # from django.core.cache import cache
        # from .utils.emails import send_otp_email
        # otp = str(random.randint(100000, 999999))
        # cache.set(f'otp:{user.email}', otp, timeout=600)
        # send_otp_email(user, otp)

        # Return JWT tokens as HttpOnly cookies + user in body
        token_serializer = CustomTokenObtainPairSerializer()
        token_data = token_serializer.get_token(user)
        response = Response({
            'user': _user_payload_for_auth_response(request, user),
        }, status=status.HTTP_201_CREATED)
        from .authentication import set_jwt_cookies
        set_jwt_cookies(response, token_data.access_token, token_data)
        # iOS / cross-origin: SPA must read tokens from JSON (cookies are unreliable).
        response.data['access'] = str(token_data.access_token)
        response.data['refresh'] = str(token_data)
        return response


@csrf_required
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """
    Verify email with OTP. Marks user as verified on success.
    Expects: { "email": "...", "otp": "123456" }
    """
    from django.core.cache import cache

    email = (request.data.get('email') or '').strip()
    otp = (request.data.get('otp') or '').strip()

    if not email or not otp:
        return Response(
            {'error': 'email and otp are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    cache_key = f'otp:{email}'
    stored_otp = cache.get(cache_key)
    if not stored_otp or stored_otp != otp:
        return Response(
            {'error': 'Invalid or expired OTP'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    user.is_email_verified = True
    user.save(update_fields=['is_email_verified'])
    cache.delete(cache_key)

    token_serializer = CustomTokenObtainPairSerializer()
    token_data = token_serializer.get_token(user)
    return Response({
        'user': _user_payload_for_auth_response(request, user),
        'access': str(token_data.access_token),
        'refresh': str(token_data),
        'message': 'Email verified successfully.',
    }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom login endpoint. Sets JWT tokens as HttpOnly cookies (XSS-safe).
    JSON body also returns tokens for Bearer clients. CSRF exempt: Safari ITP drops cross-site
    csrftoken; auth is credential-based (password → JWT), not session-cookie CSRF semantics.
    """
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AuthLoginScopedThrottle]

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code != 200:
                return response
            from .authentication import set_jwt_cookies

            raw_data = getattr(response, 'data', None)
            body = {}
            if isinstance(raw_data, dict):
                body = {k: raw_data[k] for k in raw_data}
            else:
                try:
                    body = dict(raw_data) if raw_data is not None else {}
                except Exception:
                    logger.exception('login: could not copy response.data')
                    body = {}

            access = body.get('access')
            refresh = body.get('refresh')
            if access and refresh:
                try:
                    set_jwt_cookies(response, str(access), str(refresh))
                except Exception:
                    logger.exception('login: set_jwt_cookies failed (JSON body tokens still returned)')
                body['access'] = str(access)
                body['refresh'] = str(refresh)

            user = _user_from_access_token_str(access)
            if user is None:
                raw = request.data.get(User.USERNAME_FIELD) or request.data.get('username')
                if raw is not None and not isinstance(raw, str):
                    raw = str(raw)
                uname = (raw or '').strip()
                if uname:
                    try:
                        user = User.objects.get(username=uname)
                    except User.DoesNotExist:
                        user = None

            payload = _user_payload_for_auth_response(request, user)
            if payload is not None:
                body['user'] = payload

            response.data = body
            return response
        except Exception as e:
            traceback.print_exc()
            return Response(
                {'detail': f'Server Crash: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(csrf_required, name='dispatch')
class CookieTokenRefreshView(TokenRefreshView):
    """
    Token refresh that reads refresh token from HttpOnly cookie.
    Sets new access (and refresh if rotated) as cookies; does not return tokens in body.
    """
    def post(self, request, *args, **kwargs):
        from .authentication import (
            REFRESH_TOKEN_COOKIE,
            set_jwt_cookies,
            clear_jwt_cookies,
        )
        # TokenRefreshSerializer expects 'refresh' in the data payload
        data = dict(request.data) if request.data else {}
        refresh_cookie = request.COOKIES.get(REFRESH_TOKEN_COOKIE)
        if refresh_cookie:
            data['refresh'] = refresh_cookie
        if not data.get('refresh'):
            return Response(
                {'detail': 'Refresh token required (cookie or body).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = TokenRefreshSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response({'detail': 'Token is invalid or expired.'}, status=status.HTTP_401_UNAUTHORIZED)
            clear_jwt_cookies(response)
            return response
        data = serializer.validated_data
        access = data.get('access')
        new_refresh = data.get('refresh')
        refresh_out = new_refresh or refresh_cookie
        response = Response({'detail': 'Token refreshed.'}, status=status.HTTP_200_OK)
        set_jwt_cookies(response, access, refresh_out)
        if access:
            response.data['access'] = str(access)
            if refresh_out:
                response.data['refresh'] = str(refresh_out)
        return response


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def csrf_token_view(request):
    """
    Double-submit cookie: sets csrftoken on the API host + returns token in JSON.
    Cross-origin SPAs cannot read document.cookie for the API domain; the body value
    is used for X-CSRFToken while the browser still sends the cookie with credentials.
    """
    token = get_token(request)
    return Response({'success': True, 'csrfToken': token})


@csrf_required
@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """
    Logout: clear JWT HttpOnly cookies.
    """
    response = Response({'detail': 'Logged out successfully.'}, status=status.HTTP_200_OK)
    from .authentication import clear_jwt_cookies
    clear_jwt_cookies(response)
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Get current user profile with orders and listings
    Always returns minimum structure: {'user': {...}, 'orders': [], 'listings': []}
    """
    try:
        user = request.user
        
        # Get user basic info
        user_serializer = UserSerializer(user)
        
        # Get user's orders (purchases) - ensure we always return a list
        try:
            po_ctx, orders_list = build_profile_orders_serialization_context(
                request,
                Order.objects.filter(user=user, status__in=['paid', 'completed']).order_by('-created_at'),
            )
            orders_serializer = ProfileOrderSerializer(orders_list, many=True, context=po_ctx)
            orders_data = orders_serializer.data if orders_serializer.data else []
        except Exception as e:
            # If serialization fails, return empty list
            orders_data = []
        
        # Get user's ticket listings (only if seller) - ensure we always return a list
        listings_data = []
        if user.role == 'seller':
            try:
                listings = list(
                    Ticket.objects.filter(seller=user)
                    .order_by('-created_at')
                    .select_related('event')
                    .prefetch_related(
                        Prefetch('orders', queryset=Order.objects.only('id', 'ticket_id', 'status'))
                    )
                )
                l_ctx = {
                    'request': request,
                    'listing_primary_order_map': build_listing_primary_order_map(listings),
                }
                listings_serializer = ProfileListingSerializer(listings, many=True, context=l_ctx)
                listings_data = listings_serializer.data if listings_serializer.data else []
            except Exception as e:
                # If serialization fails, return empty list
                listings_data = []
        
        return Response({
            'user': user_serializer.data,
            'orders': orders_data if isinstance(orders_data, list) else [],
            'listings': listings_data if isinstance(listings_data, list) else [],
        })
    except Exception as e:
        # Fallback: return minimum structure even if everything fails
        return Response({
            'user': {'id': request.user.id, 'username': request.user.username, 'email': request.user.email, 'role': getattr(request.user, 'role', 'buyer')},
            'orders': [],
            'listings': [],
        }, status=status.HTTP_200_OK)


@csrf_required
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_to_seller(request):
    """
    Buyer → seller onboarding: payout + escrow acceptance, then role=seller.
    """
    if getattr(request.user, 'role', '') == 'seller':
        return Response({'detail': 'כבר מוגדר כמוכר.'}, status=status.HTTP_400_BAD_REQUEST)
    ser = UpgradeToSellerSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    u = request.user
    u.phone_number = ser.validated_data['phone_number']
    u.payout_details = ser.validated_data['payout_details']
    u.accepted_escrow_terms = True
    u.escrow_terms_accepted_at = timezone.now()
    u.role = 'seller'
    u.save(
        update_fields=[
            'phone_number',
            'payout_details',
            'accepted_escrow_terms',
            'escrow_terms_accepted_at',
            'role',
            'updated_at',
        ]
    )
    return Response(UserSerializer(u).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_activity(request):
    """
    Comprehensive dashboard endpoint returning purchases and listings separately
    Returns: {'purchases': [...], 'listings': {'active': [...], 'sold': [...]}}
    """
    try:
        user = request.user

        # Escrow: promote locked → eligible when payout window opens
        Order.objects.filter(
            payout_status='locked',
            payout_eligible_date__isnull=False,
            payout_eligible_date__lte=timezone.now(),
        ).update(payout_status='eligible')
        
        # Get purchases (orders)
        po_ctx, purchases_list = build_profile_orders_serialization_context(
            request,
            Order.objects.filter(user=user, status__in=['paid', 'completed']).order_by('-created_at'),
        )
        purchases_serializer = ProfileOrderSerializer(purchases_list, many=True, context=po_ctx)
        
        # Get listings - show ALL tickets where seller=user (regardless of role)
        # Fix: Previously only showed when user.role=='seller'; tickets could exist but not display
        # if role was mis-set. Now we always fetch by seller=user so dashboard matches Event page.
        active_listings = []
        sold_listings = []
        
        all_listings = list(
            Ticket.objects.filter(seller=user)
            .order_by('-created_at')
            .select_related('event')
            .prefetch_related(
                Prefetch('orders', queryset=Order.objects.only('id', 'ticket_id', 'status'))
            )
        )
        l_ctx = {
            'request': request,
            'listing_primary_order_map': build_listing_primary_order_map(all_listings),
        }
        listings_serializer = ProfileListingSerializer(all_listings, many=True, context=l_ctx)
        
        for listing in listings_serializer.data:
            # Include both 'active' and 'pending_verification' in active_listings
            # This allows sellers to see their tickets awaiting verification
            if listing.get('status') in ['active', 'pending_verification']:
                active_listings.append(listing)
            elif listing.get('status') in ['sold', 'pending_payout', 'paid_out']:
                sold_listings.append(listing)
        
        return Response({
            'purchases': purchases_serializer.data,
            'listings': {
                'active': active_listings,
                'sold': sold_listings,
            },
            'summary': {
                'total_purchases': len(purchases_serializer.data),
                'active_listings_count': len(active_listings),
                'sold_listings_count': len(sold_listings),
                'total_expected_payout': sum(
                    float(l.get('expected_payout', 0) or 0) 
                    for l in sold_listings 
                    if l.get('expected_payout')
                ),
            }
        })
    except Exception as e:
        return Response({
            'purchases': [],
            'listings': {'active': [], 'sold': []},
            'summary': {
                'total_purchases': 0,
                'active_listings_count': 0,
                'sold_listings_count': 0,
                'total_expected_payout': 0,
            }
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_receipt(request, order_id):
    """
    Generate and return a receipt for an order (PDF or HTML)
    IDOR PROTECTION: Only fetch orders the user owns - never expose others' orders
    """
    # IDOR FIX: Filter by owner first - never fetch orders we don't own
    if request.user.is_authenticated:
        order = (
            Order.objects.filter(user=request.user, id=order_id)
            .select_related('ticket', 'ticket__event', 'ticket__event__artist')
            .first()
        )
    else:
        order = None
    if not order:
        # Guest order: require email param to verify ownership
        guest_email = request.query_params.get('email', '').strip()
        if not guest_email:
            return Response(
                {'error': 'Authentication or email required for guest order receipts'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        order = (
            Order.objects.filter(
                guest_email__iexact=guest_email,
                id=order_id,
                status__in=['paid', 'completed'],
            )
            .select_related('ticket', 'ticket__event', 'ticket__event__artist')
            .first()
        )
    if not order:
        return Response(
            {'error': 'Order not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # For now, return JSON receipt data
    # In production, you might want to generate a PDF
    receipt_data = {
        'order_id': order.id,
        'order_date': order.created_at,
        'status': order.status,
        'total_amount': str(order.total_amount),
        'total_paid_by_buyer': str(order.total_paid_by_buyer) if order.total_paid_by_buyer is not None else str(order.total_amount),
        'final_negotiated_price': str(order.final_negotiated_price) if order.final_negotiated_price is not None else None,
        'buyer_service_fee': str(order.buyer_service_fee) if order.buyer_service_fee is not None else None,
        'net_seller_revenue': str(order.net_seller_revenue) if order.net_seller_revenue is not None else None,
        'quantity': order.quantity,
        'event_name': order.event_name or (order.ticket.event.name if order.ticket and order.ticket.event else 'Unknown Event'),
        'ticket_details': {
            'section': order.ticket.section if order.ticket else None,
            'row': order.ticket.row if order.ticket else None,
            'venue': order.ticket.event.venue if order.ticket and order.ticket.event else (order.ticket.venue if order.ticket else None),
        } if order.ticket else {},
    }
    
    return Response(receipt_data, status=status.HTTP_200_OK)


def _pending_payment_blocks_price_edit(ticket: Ticket) -> bool:
    """True if any awaiting-payment order still holds this listing (row or group)."""
    candidate_ids = {ticket.id}
    if ticket.listing_group_id:
        candidate_ids = set(
            Ticket.objects.filter(
                listing_group_id=ticket.listing_group_id,
                seller_id=ticket.seller_id,
            ).values_list('id', flat=True)
        )
    for order in Order.objects.filter(status='pending_payment').iterator():
        for tid in candidate_ids:
            if order.covers_ticket(tid):
                return True
    return False


@csrf_required
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_ticket_price(request, ticket_id):
    """
    Update ticket price (only for active listings owned by the user)
    Bulk update: If ticket belongs to a group (listing_group_id), update ALL tickets in that group
    Note: In production, you might want to add restrictions on price changes
    """
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        # Security check: only ticket owner can update
        if ticket.seller != request.user:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Only allow updates to active tickets
        if ticket.status != 'active':
            return Response(
                {'error': 'Can only update active listings'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if _pending_payment_blocks_price_edit(ticket):
            return Response(
                {
                    'error': (
                        'מחיר לא ניתן לשינוי כרגע — קיימת הזמנה הממתינה לתשלום על רשימה זו. '
                        'נסה שוב לאחר שהעסקה תושלם או תבוטל.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        
        # Update price
        new_price = request.data.get('original_price')
        if new_price:
            try:
                from decimal import Decimal, ROUND_HALF_UP
                # Round to 2 decimal places to match model's save() behavior
                new_price_decimal = Decimal(str(new_price)).quantize(
                    Decimal('1'), rounding=ROUND_HALF_UP
                )
                
                # Determine which tickets to update
                if ticket.listing_group_id:
                    # Bulk update: Update all tickets in the same group that belong to this user and are active
                    tickets_to_update = Ticket.objects.filter(
                        listing_group_id=ticket.listing_group_id,
                        seller=request.user,
                        status='active'
                    )
                    
                    # Update all tickets in the group
                    # Using .update() bypasses model's save(), so we set both original_price and asking_price
                    updated_count = tickets_to_update.update(
                        original_price=new_price_decimal,
                        asking_price=new_price_decimal  # asking_price equals original_price per model logic
                    )
                    
                    # Refresh the original ticket to get updated data
                    ticket.refresh_from_db()
                else:
                    # Single ticket update (no group)
                    ticket.original_price = new_price_decimal
                    ticket.save()  # This will automatically set asking_price = original_price
                    updated_count = 1
                
                # Return the updated ticket data
                serializer = ProfileListingSerializer(ticket, context={'request': request})
                response_data = serializer.data
                # Include count of updated tickets if it's a bulk update
                if ticket.listing_group_id and updated_count > 1:
                    response_data['updated_count'] = updated_count
                
                return Response(response_data, status=status.HTTP_200_OK)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'Invalid price format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(
            {'error': 'original_price is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Ticket.DoesNotExist:
        return Response(
            {'error': 'Ticket not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@csrf_required
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """
    Create order for authenticated user after payment
    """
    # Include user in the data so serializer validation passes
    order_data = request.data.copy()
    order_data['user'] = request.user.id
    offer_id = request.data.get('offer_id')

    serializer = OrderSerializer(data=order_data)
    if serializer.is_valid():
        ticket_id = request.data.get('ticket')
        if not ticket_id:
            return Response(
                {'error': 'ticket is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get listing_group_id if provided (for grouped tickets)
        listing_group_id = request.data.get('listing_group_id')
        print(f"create_order - Ticket ID: {ticket_id}, Listing Group ID: {listing_group_id}, Quantity: {request.data.get('quantity', 1)}, Offer ID: {offer_id}")
        
        # Get quantity from request (default to 1 if not provided)
        order_quantity = int(request.data.get('quantity', 1))
        
        # Prevent negative inventory: Validate quantity doesn't exceed available
        if order_quantity < 1:
            return Response(
                {'error': 'Quantity must be at least 1'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # CRITICAL: Use transaction.atomic + select_for_update to prevent double-selling (race conditions)
        with transaction.atomic():
            release_abandoned_carts()
            negotiated_offer = None
            if offer_id not in (None, '', []):
                try:
                    oid = int(offer_id)
                except (TypeError, ValueError):
                    return Response({'error': 'Invalid offer_id.'}, status=status.HTTP_400_BAD_REQUEST)
                negotiated_offer = Offer.objects.select_for_update().filter(
                    id=oid,
                    buyer=request.user,
                    status='accepted',
                ).first()
                if not negotiated_offer:
                    return Response(
                        {
                            'error': 'Invalid or ineligible offer for checkout (must be accepted and belong to you).',
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                print(
                    f"Negotiated offer found: ID={oid}, Amount={negotiated_offer.amount}, Quantity={negotiated_offer.quantity}"
                )
                expected_total = expected_negotiated_total_from_offer_base(negotiated_offer.amount)
                received_total = decimal_money(request.data.get('total_amount', 0))
                if not payment_amounts_match(received_total, expected_total):
                    return Response(
                        {
                            'error': (
                                f'Amount mismatch. Expected {expected_total:.2f} (base + 10% fee), '
                                f'got {received_total}'
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            # If listing_group_id is provided, IGNORE the specific ticket_id and find any active tickets in the group
            if listing_group_id:
                print(f"Checking availability for Group: {listing_group_id}")
                # CRITICAL: When listing_group_id is provided, IGNORE the specific ticket_id status
                # Find ANY active tickets from the group, regardless of which ticket_id was sent
                try:
                    # Get a reference ticket to get the price and seller (any ticket from the group will do)
                    reference_ticket = Ticket.objects.filter(
                        listing_group_id=listing_group_id
                    ).first()

                    if not reference_ticket:
                        print(f"Group {listing_group_id} not found")
                        return Response(
                            {'error': 'Ticket group not found'},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    print(f"Reference ticket found: ID={reference_ticket.id}, status={reference_ticket.status}, price={reference_ticket.original_price}")
                    # Validate total_amount ONLY when NOT a negotiated offer (offer_id overrides ticket price)
                    if not negotiated_offer:
                        try:
                            sent_total = decimal_money(request.data.get('total_amount', 0))
                            expected_total = expected_buy_now_total(reference_ticket.asking_price, order_quantity)
                            if not payment_amounts_match(sent_total, expected_total):
                                return Response(
                                    {'error': f'Invalid total amount. Expected {expected_total}, got {sent_total}'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except Exception as e:
                            print(f"Error validating total_amount for grouped tickets: {e}")
                    print(f"IGNORING ticket_id {ticket_id} - looking for active tickets in group {listing_group_id}")

                    # Prevent sellers from buying their own tickets
                    if reference_ticket.seller == request.user:
                        return Response(
                            {'error': 'You cannot purchase your own tickets'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Block purchases for past events
                    if _is_event_past(reference_ticket):
                        return Response(
                            {'error': 'This event has already passed.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Find all available tickets in the same listing group
                    # IMPORTANT: We completely ignore the ticket_id that was sent - we only care about the group
                    # Allow both 'active' and 'reserved' tickets (user just reserved and now wants to buy)
                    available_tickets_query = Ticket.objects.filter(
                        listing_group_id=listing_group_id,
                        status__in=['active', 'reserved']
                    )
                    available_count = available_tickets_query.count()
                    print(f"Available tickets in group {listing_group_id}: {available_count}, Requested: {order_quantity}")

                    # Enforce split logic for grouped listings based on split_type
                    split_type_raw = (reference_ticket.split_type or '').strip()
                    split_type_norm = split_type_raw.lower()

                    # Map Hebrew display values to internal keys
                    if split_type_norm in ['כל כמות', 'any']:
                        split_key = 'any'
                    elif split_type_norm in ['זוגות בלבד', 'pairs']:
                        split_key = 'pairs'
                    elif split_type_norm in ['מכור הכל יחד', 'all']:
                        split_key = 'all'
                    else:
                        split_key = 'any'

                    if split_key == 'all' and order_quantity != available_count:
                        return Response(
                            {'error': 'You must buy all tickets together'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    if split_key == 'pairs' and order_quantity % 2 != 0:
                        return Response(
                            {'error': 'Tickets can only be bought in pairs'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    if available_count < order_quantity:
                        return Response(
                            {'error': f'Not enough tickets available in this listing. Available: {available_count}, Requested: {order_quantity}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Get the requested quantity of available tickets (prioritize active, then reserved)
                    # CRITICAL: select_for_update() locks rows to prevent double-selling (race conditions)
                    active_tickets = list(available_tickets_query.filter(status='active').select_for_update().order_by('id')[:order_quantity])
                    remaining_needed = order_quantity - len(active_tickets)

                    if remaining_needed > 0:
                        # Only get reserved tickets that belong to the current user (with row lock)
                        if request.user.is_authenticated:
                            reserved_tickets = list(available_tickets_query.filter(
                                status='reserved',
                                reserved_by=request.user
                            ).select_for_update().order_by('id')[:remaining_needed])
                        else:
                            # Guest: can't use reserved tickets (would need email check)
                            reserved_tickets = []
                        available_tickets = active_tickets + reserved_tickets
                    else:
                        available_tickets = active_tickets

                    # Final check: make sure we have enough tickets
                    if len(available_tickets) < order_quantity:
                        return Response(
                            {'error': f'Not enough tickets available. Found {len(available_tickets)}, Requested: {order_quantity}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # Re-verify status after lock: prevent double-sell if another transaction just sold it
                    for t in available_tickets:
                        if t.status not in ['active', 'reserved']:
                            return Response(
                                {'error': 'This ticket was just sold to someone else.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    ticket_ids = [t.id for t in available_tickets]
                    try:
                        _reserve_rows_for_pending_checkout(available_tickets, user=request.user)
                    except PermissionDenied as e:
                        return Response(
                            {'error': getattr(e, 'detail', str(e))},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    except ValueError:
                        return Response(
                            {'error': 'Ticket is no longer available.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    # Use the first ticket as the base ticket for the order
                    ticket = available_tickets[0]
                    print(f"Order will be linked to ticket {ticket.id} from group {listing_group_id}")
                except Ticket.DoesNotExist:
                    return Response(
                        {'error': 'Ticket group not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                except Exception as e:
                    print(f"Error processing group purchase: {str(e)}")
                    return Response(
                        {'error': f'Error processing purchase: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                # Single ticket purchase (backward compatibility)
                print(f"Single ticket purchase (no listing_group_id)")
                try:
                    ticket = Ticket.objects.select_for_update().get(id=ticket_id)
                    print(f"Single ticket found: ID={ticket.id}, status={ticket.status}, available_quantity={ticket.available_quantity}")
                    if not negotiated_offer:
                        try:
                            sent_total = decimal_money(request.data.get('total_amount', 0))
                            expected_total = expected_buy_now_total(ticket.asking_price, order_quantity)
                            if not payment_amounts_match(sent_total, expected_total):
                                return Response(
                                    {'error': f'Invalid total amount. Expected {expected_total}, got {sent_total}'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except Exception as e:
                            print(f"Error validating total_amount for single ticket: {e}")
                except Ticket.DoesNotExist:
                    print(f"Ticket {ticket_id} not found")
                    return Response(
                        {'error': 'Ticket not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                _sync_expired_cart_reservation(ticket)
                ticket.refresh_from_db()
                if ticket.status == 'reserved':
                    if ticket.reserved_by_id and ticket.reserved_by_id != request.user.id:
                        return Response(
                            {
                                'error': 'This ticket is reserved by another buyer. Please refresh.',
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # Prevent sellers from buying their own tickets
                if ticket.seller == request.user:
                    return Response(
                        {'error': 'You cannot purchase your own tickets'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Block purchases for past events
                if _is_event_past(ticket):
                    return Response(
                        {'error': 'This event has already passed.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Enforce split logic for single-ticket listings (legacy path)
                split_type_raw = (ticket.split_type or '').strip()
                split_type_norm = split_type_raw.lower()
                if split_type_norm in ['כל כמות', 'any']:
                    split_key = 'any'
                elif split_type_norm in ['זוגות בלבד', 'pairs']:
                    split_key = 'pairs'
                elif split_type_norm in ['מכור הכל יחד', 'all']:
                    split_key = 'all'
                else:
                    split_key = 'any'
                if split_key == 'all' and order_quantity != (ticket.available_quantity or 1):
                    return Response(
                        {'error': 'You must buy all tickets together'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if split_key == 'pairs' and order_quantity % 2 != 0:
                    return Response(
                        {'error': 'Tickets can only be bought in pairs'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if ticket.status not in ['active', 'reserved']:
                    print(f"ERROR: Ticket {ticket_id} status is {ticket.status}, not 'active' or 'reserved'")
                    return Response(
                        {'error': 'Ticket is no longer available'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if order_quantity > (ticket.available_quantity or 1):
                    return Response(
                        {'error': f'Not enough tickets available. Available: {ticket.available_quantity or 1}, Requested: {order_quantity}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                held_qty = 0
                if order_quantity == 1:
                    try:
                        _reserve_rows_for_pending_checkout([ticket], user=request.user)
                    except PermissionDenied as e:
                        return Response(
                            {'error': getattr(e, 'detail', str(e))},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    except ValueError:
                        return Response(
                            {'error': 'Ticket is no longer available.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    ticket_ids = [ticket.id]
                else:
                    ticket.available_quantity -= order_quantity
                    held_qty = order_quantity
                    ticket.reserved_at = timezone.now()
                    ticket.reserved_by = request.user
                    ticket.reservation_email = None
                    if ticket.available_quantity <= 0:
                        ticket.available_quantity = 0
                        ticket.status = 'reserved'
                    else:
                        ticket.status = 'active'
                    ticket.save()
                    ticket_ids = [ticket.id]

            if negotiated_offer:
                if int(negotiated_offer.quantity or 1) != int(order_quantity):
                    return Response(
                        {'error': 'Order quantity must match the accepted offer.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if listing_group_id:
                    og = negotiated_offer.ticket.listing_group_id
                    if str(og or '') != str(listing_group_id):
                        return Response(
                            {'error': 'Offer does not apply to this listing.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    if int(negotiated_offer.ticket_id) != int(ticket_id):
                        return Response(
                            {'error': 'Offer does not apply to this ticket.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            order = serializer.save(status='pending_payment', quantity=order_quantity)
            order.ticket_ids = ticket_ids
            order.pending_offer = negotiated_offer
            if listing_group_id:
                order.held_ticket = None
                order.held_quantity = 0
            elif order_quantity == 1:
                order.held_ticket = None
                order.held_quantity = 0
            else:
                order.held_ticket = ticket
                order.held_quantity = held_qty
            order.payment_confirm_token = secrets.token_urlsafe(32)
            order.save(
                update_fields=[
                    'ticket_ids',
                    'pending_offer',
                    'held_ticket',
                    'held_quantity',
                    'payment_confirm_token',
                    'updated_at',
                ]
            )

        order.refresh_from_db()
        return _order_pending_checkout_response(order, request)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_required
@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_order_payment(request, order_id):
    """
    Second step after create_order / guest_checkout: PSP / mock webhook confirms funds,
    then inventory is finalized, escrow fields applied, and receipt email sent.
    """
    order = Order.objects.filter(pk=order_id).first()
    if not order or order.status != 'pending_payment':
        return Response(
            {'error': 'Order not found or not awaiting payment.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    webhook_secret = (os.environ.get('MOCK_PAYMENT_WEBHOOK_SECRET') or '').strip()
    mock_ack = request.data.get('mock_payment_ack') is True or str(
        request.data.get('mock_payment_ack', '')
    ).lower() in ('true', '1', 'yes')
    supplied_secret = (
        (request.data.get('payment_secret') or request.headers.get('X-Payment-Secret') or '')
    ).strip()
    body_token = (request.data.get('payment_confirm_token') or '').strip()
    stored_tok = (order.payment_confirm_token or '').strip()

    payment_ok = False
    if webhook_secret and supplied_secret and secrets.compare_digest(webhook_secret, supplied_secret):
        payment_ok = True
    elif not webhook_secret and mock_ack:
        payment_ok = True
    elif stored_tok and body_token and secrets.compare_digest(stored_tok, body_token):
        payment_ok = True

    if not payment_ok:
        if webhook_secret:
            return Response(
                {
                    'error': (
                        'Invalid payment confirmation. Pass payment_secret, '
                        'or the payment_confirm_token from the order response.'
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                'error': (
                    'Payment not confirmed. Send mock_payment_ack=true, '
                    'payment_confirm_token from the create-order response, '
                    'or set MOCK_PAYMENT_WEBHOOK_SECRET and pass payment_secret / X-Payment-Secret.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if order.user_id:
        if not request.user.is_authenticated or order.user_id != request.user.id:
            return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
    else:
        body_email = (request.data.get('guest_email') or '').strip().lower()
        order_email = (order.guest_email or '').strip().lower()
        if not body_email or body_email != order_email:
            return Response(
                {'error': 'guest_email must match this order.'},
                status=status.HTTP_403_FORBIDDEN,
            )

    try:
        with transaction.atomic():
            release_abandoned_carts()
            order = Order.objects.select_for_update().filter(pk=order_id, status='pending_payment').first()
            if not order:
                return Response(
                    {'error': 'Order not found or not awaiting payment.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            negotiated_offer = order.pending_offer
            ticket_ref = order.ticket

            if order.held_ticket_id and order.held_quantity:
                t = Ticket.objects.select_for_update().get(pk=order.held_ticket_id)
                if timezone.now() - order.created_at > timedelta(
                    minutes=RESERVATION_TIMEOUT_MINUTES + 5
                ):
                    raise ValueError('checkout_expired')
                if (t.available_quantity or 0) <= 0:
                    t.status = 'sold'
                t.reserved_at = None
                t.reserved_by = None
                t.reservation_email = None
                t.save(
                    update_fields=[
                        'status',
                        'available_quantity',
                        'reserved_at',
                        'reserved_by',
                        'reservation_email',
                        'updated_at',
                    ]
                )
                ticket_ref = t
            else:
                tix = list(
                    Ticket.objects.select_for_update()
                    .filter(pk__in=(order.ticket_ids or []))
                    .order_by('id')
                )
                if len(tix) != len(order.ticket_ids or []):
                    raise ValueError('ticket_mismatch')
                user_obj = order.user if order.user_id else None
                ge = (order.guest_email or '').strip()
                _verify_reservations_fresh(tix, user=user_obj, guest_email=ge)
                _finalize_group_sale_ticket_rows(order.ticket_ids)

            _reject_pending_offers_for_ticket_ids(list(order.ticket_ids or []))
            order.status = 'paid'
            order.payment_confirm_token = None
            order.save(update_fields=['status', 'payment_confirm_token', 'updated_at'])
            _apply_order_pricing_fields(order, negotiated_offer, ticket_ref, order.quantity)
    except ValueError as e:
        msg = str(e)
        if msg == 'checkout_expired':
            return Response(
                {'error': 'Checkout session expired. Start again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if msg == 'reservation_expired':
            return Response(
                {'error': 'Reservation expired. Start again.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {'error': 'Cannot complete payment for this order.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except PermissionDenied as e:
        return Response(
            {'error': getattr(e, 'detail', str(e))},
            status=status.HTTP_403_FORBIDDEN,
        )

    recipient = (order.user.email if order.user_id else order.guest_email) or ''
    if recipient:
        try:
            from .utils.emails import send_receipt_with_pdf

            send_receipt_with_pdf(recipient, order)
        except Exception:
            logger.exception('confirm_order_payment: receipt email failed')

    order.refresh_from_db()
    return Response(OrderSerializer(order, context={'request': request}).data)


@csrf_required
@api_view(['POST'])
@permission_classes([AllowAny])
def payment_simulation(request):
    """
    Simulate payment processing (for development).
    Accepts payment details and returns success/failure.
    Pre-production: no PAN/Luhn validation here — the mock gateway always succeeds once amount checks pass.
    CRITICAL: Must handle listing_group_id like create_order does
    """
    ticket_id = request.data.get('ticket_id')
    amount = request.data.get('amount')
    
    if not ticket_id or not amount:
        return Response(
            {'error': 'ticket_id and amount are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get listing_group_id if provided (for grouped tickets)
    listing_group_id = request.data.get('listing_group_id')
    
    # Get quantity from request (default to 1 if not provided)
    quantity = int(request.data.get('quantity', 1))
    
    if quantity < 1:
        return Response(
            {'error': 'Quantity must be at least 1'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # CRITICAL: Use transaction.atomic + select_for_update to prevent race conditions
    with transaction.atomic():
        # If listing_group_id is provided, check availability in the group (not just the single ticket)
        if listing_group_id:
            print(f"payment_simulation - Listing Group ID provided: {listing_group_id}, Quantity: {quantity}")
            try:
                from django.db.models import Q
                if request.user.is_authenticated:
                    available_query = Q(
                        listing_group_id=listing_group_id
                    ) & (
                        Q(status='active') |
                        Q(status='reserved', reserved_by=request.user)
                    )
                else:
                    available_query = Q(
                        listing_group_id=listing_group_id,
                        status='active'
                    )
                # Lock rows by evaluating to list (NOT .count() - select_for_update + count causes NotSupportedError)
                locked_tickets = list(Ticket.objects.filter(available_query).select_for_update().order_by('id'))
                available_tickets_count = len(locked_tickets)
                if not locked_tickets:
                    return Response(
                        {'error': 'Ticket group not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                print(f"payment_simulation - Available tickets in group: {available_tickets_count}, Requested: {quantity}")
                if available_tickets_count < quantity:
                    return Response(
                        {'error': f'Invalid quantity. Available in group: {available_tickets_count}, Requested: {quantity}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                ticket = locked_tickets[0]
                print(f"payment_simulation - Using reference ticket {ticket.id} for price calculation")
            except Exception as e:
                print(f"payment_simulation - Error processing group: {str(e)}")
                return Response(
                    {'error': f'Error processing payment: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Single ticket purchase (backward compatibility)
            try:
                ticket = Ticket.objects.select_for_update().get(id=ticket_id)
            except Ticket.DoesNotExist:
                return Response(
                    {'error': 'Ticket not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Re-verify: ticket was just sold to someone else
            if ticket.status not in ['active', 'reserved']:
                return Response(
                    {'error': 'Ticket was just sold. Please refresh and try another listing.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if quantity > (ticket.available_quantity or 1):
                return Response(
                    {'error': f'Invalid quantity. Available: {ticket.available_quantity or 1}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

    # Block purchases for past events
    if _is_event_past(ticket):
        return Response(
            {'error': 'This event has already passed.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    offer_id = request.data.get('offer_id')
    is_negotiated = False
    if offer_id not in (None, '', []):
        try:
            oid = int(offer_id)
        except (TypeError, ValueError):
            return Response({'error': 'Invalid offer_id.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if request.user.is_authenticated:
                offer = Offer.objects.get(id=oid, buyer=request.user, status='accepted')
            else:
                ge = (
                    (request.data.get('guest_email') or request.data.get('email') or '')
                    .strip()
                    .lower()
                )
                offer = Offer.objects.get(id=oid, status='accepted')
                be = (offer.buyer.email or '').strip().lower()
                if not ge or not be or ge != be:
                    return Response(
                        {
                            'error': 'guest_email is required and must match the registered buyer for this offer.',
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            is_negotiated = True
            base_dec, fee_dec, total_dec = buyer_charge_from_base_amount(offer.amount)
            print(
                f"Payment simulation: Negotiated offer {oid}, "
                f"base={base_dec}, expected_total={total_dec}"
            )
        except Offer.DoesNotExist:
            return Response(
                {'error': 'Invalid or ineligible offer for payment simulation.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    
    if not is_negotiated:
        base_dec, fee_dec, total_dec = list_price_checkout_amounts(ticket.asking_price, quantity)
    
    amount_dec = decimal_money(amount)
    if not payment_amounts_match(amount_dec, total_dec):
        return Response(
            {
                'error': (
                    f'Amount does not match {"negotiated offer" if is_negotiated else "ticket"} price. '
                    f'Expected: {total_dec:.2f}, Got: {amount}'
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Simulate payment processing (always succeeds in dev)
    # In production, this would call the actual payment gateway
    return Response({
        'success': True,
        'payment_id': f'PAY_{ticket_id}_{request.data.get("timestamp", "")}',
        'message': 'Payment processed successfully',
        'base_price': float(base_dec),
        'service_fee': float(fee_dec),
        'total_amount': float(total_dec),
        'is_negotiated': is_negotiated
    }, status=status.HTTP_200_OK)


@csrf_required
@api_view(['POST'])
@permission_classes([AllowAny])
def guest_checkout(request):
    """
    Create order for guest (non-authenticated) user after payment
    """
    offer_id = request.data.get('offer_id')
    negotiated_offer = None
    if offer_id not in (None, '', []):
        try:
            oid = int(offer_id)
        except (TypeError, ValueError):
            return Response({'error': 'Invalid offer_id.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            negotiated_offer = Offer.objects.get(id=oid, status='accepted')
            print(f"Guest checkout: Negotiated offer found: ID={oid}, Amount={negotiated_offer.amount}")
        except Offer.DoesNotExist:
            return Response(
                {'error': 'Invalid or ineligible offer for checkout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    serializer = GuestCheckoutSerializer(data=request.data)
    if serializer.is_valid():
        order_data = serializer.validated_data
        ticket_id = order_data.get('ticket_id')
        guest_email_raw = (order_data.get('guest_email') or '').strip()

        if negotiated_offer and not _guest_offer_email_matches(negotiated_offer, guest_email_raw):
            return Response(
                {'error': 'Guest email must match the registered buyer who made this offer.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if negotiated_offer:
            expected_total = expected_negotiated_total_from_offer_base(negotiated_offer.amount)
            received_total = decimal_money(order_data.get('total_amount', 0))
            if not payment_amounts_match(received_total, expected_total):
                return Response(
                    {'error': f'Amount mismatch. Expected {expected_total:.2f}, got {received_total}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if not ticket_id:
            return Response(
                {'error': 'ticket_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        listing_group_id = order_data.get('listing_group_id') or request.data.get('listing_group_id')

        # Get quantity from request (default to 1 if not provided)
        order_quantity = int(order_data.get('quantity', 1))
        
        # Prevent negative inventory: Validate quantity doesn't exceed available
        if order_quantity < 1:
            return Response(
                {'error': 'Quantity must be at least 1'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # CRITICAL: Use transaction.atomic + select_for_update to prevent double-selling (race conditions)
        with transaction.atomic():
            release_abandoned_carts()
            # If listing_group_id is provided, IGNORE the specific ticket_id and find any active tickets in the group
            if listing_group_id:
                # CRITICAL: When listing_group_id is provided, IGNORE the specific ticket_id status
                # Find ANY active tickets from the group, regardless of which ticket_id was sent
                try:
                    # Get a reference ticket to get the price and seller (any ticket from the group will do)
                    reference_ticket = Ticket.objects.filter(
                        listing_group_id=listing_group_id
                    ).first()

                    if not reference_ticket:
                        return Response(
                            {'error': 'Ticket group not found'},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    if _is_event_past(reference_ticket):
                        return Response(
                            {'error': 'This event has already passed.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    print(f"Guest checkout - IGNORING ticket_id {ticket_id}, looking for active tickets in group {listing_group_id}")

                    # Find all available tickets in the same listing group
                    available_tickets_query = Ticket.objects.filter(
                        listing_group_id=listing_group_id,
                        status__in=['active', 'reserved']
                    )
                    available_count = available_tickets_query.count()

                    # Enforce split logic for grouped listings based on split_type
                    split_type_raw = (reference_ticket.split_type or '').strip()
                    split_type_norm = split_type_raw.lower()
                    if split_type_norm in ['כל כמות', 'any']:
                        split_key = 'any'
                    elif split_type_norm in ['זוגות בלבד', 'pairs']:
                        split_key = 'pairs'
                    elif split_type_norm in ['מכור הכל יחד', 'all']:
                        split_key = 'all'
                    else:
                        split_key = 'any'
                    if split_key == 'all' and order_quantity != available_count:
                        return Response(
                            {'error': 'You must buy all tickets together'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    if split_key == 'pairs' and order_quantity % 2 != 0:
                        return Response(
                            {'error': 'Tickets can only be bought in pairs'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    if available_count < order_quantity:
                        return Response(
                            {'error': f'Not enough tickets available in this listing. Available: {available_count}, Requested: {order_quantity}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # CRITICAL: select_for_update() locks rows to prevent double-selling
                    active_tickets = list(available_tickets_query.filter(status='active').select_for_update().order_by('id')[:order_quantity])
                    remaining_needed = order_quantity - len(active_tickets)
                    if remaining_needed > 0:
                        guest_email = order_data.get('guest_email', '').strip()
                        if guest_email:
                            reserved_tickets = list(available_tickets_query.filter(
                                status='reserved',
                                reservation_email=guest_email
                            ).select_for_update().order_by('id')[:remaining_needed])
                        else:
                            reserved_tickets = []
                        available_tickets = active_tickets + reserved_tickets
                    else:
                        available_tickets = active_tickets
                    if len(available_tickets) < order_quantity:
                        return Response(
                            {'error': f'Not enough tickets available. Found {len(available_tickets)}, Requested: {order_quantity}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    for t in available_tickets:
                        if t.status not in ['active', 'reserved']:
                            return Response(
                                {'error': 'This ticket was just sold to someone else.'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    ticket_ids = [t.id for t in available_tickets]
                    ge = (order_data.get('guest_email') or '').strip()
                    try:
                        _reserve_rows_for_pending_checkout(
                            available_tickets, user=None, guest_email=ge
                        )
                    except PermissionDenied as e:
                        return Response(
                            {'error': getattr(e, 'detail', str(e))},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    except ValueError:
                        return Response(
                            {'error': 'Ticket is no longer available.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    ticket = available_tickets[0]
                except Ticket.DoesNotExist:
                    return Response(
                        {'error': 'Ticket group not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                except Exception as e:
                    print(f"Error processing guest group purchase: {str(e)}")
                    return Response(
                        {'error': f'Error processing purchase: {str(e)}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            else:
                # Single ticket purchase (backward compatibility)
                try:
                    ticket = Ticket.objects.select_for_update().get(id=ticket_id)
                except Ticket.DoesNotExist:
                    return Response(
                        {'error': 'Ticket not found'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                _sync_expired_cart_reservation(ticket)
                ticket.refresh_from_db()
                if ticket.status == 'reserved':
                    ge = (order_data.get('guest_email') or '').strip()
                    if ticket.reservation_email and ticket.reservation_email != ge:
                        return Response(
                            {'error': 'This ticket is reserved for another checkout session.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                if _is_event_past(ticket):
                    return Response(
                        {'error': 'This event has already passed.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Enforce split logic for single-ticket listings (legacy path)
                split_type_raw = (ticket.split_type or '').strip()
                split_type_norm = split_type_raw.lower()

                if split_type_norm in ['כל כמות', 'any']:
                    split_key = 'any'
                elif split_type_norm in ['זוגות בלבד', 'pairs']:
                    split_key = 'pairs'
                elif split_type_norm in ['מכור הכל יחד', 'all']:
                    split_key = 'all'
                else:
                    split_key = 'any'

                if split_key == 'all' and order_quantity != (ticket.available_quantity or 1):
                    return Response(
                        {'error': 'You must buy all tickets together'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if split_key == 'pairs' and order_quantity % 2 != 0:
                    return Response(
                        {'error': 'Tickets can only be bought in pairs'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Check if ticket is still available (only for single ticket purchases)
                if ticket.status not in ['active', 'reserved']:
                    return Response(
                        {'error': 'Ticket is no longer available'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if order_quantity > (ticket.available_quantity or 1):
                    return Response(
                        {'error': f'Not enough tickets available. Available: {ticket.available_quantity or 1}, Requested: {order_quantity}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                ge = (order_data.get('guest_email') or '').strip()
                held_qty = 0
                if order_quantity == 1:
                    try:
                        _reserve_rows_for_pending_checkout([ticket], user=None, guest_email=ge)
                    except PermissionDenied as e:
                        return Response(
                            {'error': getattr(e, 'detail', str(e))},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    except ValueError:
                        return Response(
                            {'error': 'Ticket is no longer available.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    ticket_ids = [ticket.id]
                else:
                    ticket.available_quantity -= order_quantity
                    held_qty = order_quantity
                    ticket.reserved_at = timezone.now()
                    ticket.reserved_by = None
                    ticket.reservation_email = ge or None
                    if ticket.available_quantity <= 0:
                        ticket.available_quantity = 0
                        ticket.status = 'reserved'
                    else:
                        ticket.status = 'active'
                    ticket.save()
                    ticket_ids = [ticket.id]

            if negotiated_offer:
                if int(negotiated_offer.quantity or 1) != int(order_quantity):
                    return Response(
                        {'error': 'Order quantity must match the accepted offer.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if listing_group_id:
                    og = negotiated_offer.ticket.listing_group_id
                    if str(og or '') != str(listing_group_id):
                        return Response(
                            {'error': 'Offer does not apply to this listing.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    if int(negotiated_offer.ticket_id) != int(ticket_id):
                        return Response(
                            {'error': 'Offer does not apply to this ticket.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            total_amount = order_data.get('total_amount', ticket.asking_price)
            event_name = order_data.get('event_name', ticket.event_name)

            order = Order.objects.create(
                guest_email=order_data['guest_email'],
                guest_phone=order_data['guest_phone'],
                ticket=ticket,
                total_amount=total_amount,
                quantity=order_quantity,
                event_name=event_name,
                status='pending_payment',
                ticket_ids=ticket_ids,
                pending_offer=negotiated_offer,
                held_ticket=(ticket if (not listing_group_id and order_quantity > 1) else None),
                held_quantity=(held_qty if (not listing_group_id and order_quantity > 1) else 0),
                payment_confirm_token=secrets.token_urlsafe(32),
            )

        order.refresh_from_db()
        return _order_pending_checkout_response(order, request)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_required, name='dispatch')
class TicketViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Ticket model
    """
    queryset = Ticket.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return TicketListSerializer
        return TicketSerializer
    
    def get_queryset(self):
        import logging
        from django.db.models import Q
        logger = logging.getLogger(__name__)
        # Lazy cart abandonment cleanup
        release_abandoned_carts()
        now = timezone.now()
        # Only return tickets for upcoming events (event.date >= now or legacy event_date >= now)
        upcoming_filter = (
            Q(event__date__gte=now) |
            Q(event__isnull=True, event_date__gte=now) |
            Q(event__isnull=True, event_date__isnull=True)
        )
        queryset = (
            Ticket.objects.filter(status='active')
            .filter(upcoming_filter)
            .select_related('event', 'seller')
        )
        
        # Log the count for verification
        count = queryset.count()
        print(f'Active tickets ready: {count}')
        logger.info(f'TicketViewSet.get_queryset: Active tickets ready: {count}')
        
        # For authenticated users, also show their own tickets (for sellers to manage) - same upcoming filter
        if self.request.user.is_authenticated:
            user_tickets = (
                Ticket.objects.filter(seller=self.request.user)
                .filter(upcoming_filter)
                .select_related('event', 'seller')
            )
            queryset = queryset | user_tickets
        
        return queryset.distinct().order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        """
        Override create to handle multiple PDF files - create one Ticket per PDF
        """
        # Only sellers can create tickets
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required to create tickets.")
        if request.user.role != 'seller':
            raise PermissionDenied("Only users with seller role can create tickets.")
        
        # Extract PDF files from request
        pdf_files = []
        pdf_files_count = int(request.data.get('pdf_files_count', 0))
        
        # Collect all PDF files (pdf_file_0, pdf_file_1, etc.)
        for i in range(pdf_files_count):
            pdf_key = f'pdf_file_{i}'
            if pdf_key in request.FILES:
                pdf_files.append(request.FILES[pdf_key])
        
        # If no PDF files found in numbered format, check for single pdf_file (backward compatibility)
        if not pdf_files and 'pdf_file' in request.FILES:
            pdf_files = [request.FILES['pdf_file']]
            pdf_files_count = 1
        
        available_quantity = int(request.data.get('available_quantity', 1))
        relax_pdf = getattr(settings, 'RELAX_PDF_UPLOAD_VALIDATION', False)

        # AUTO-SPLIT MODE: 1 multi-page PDF for N tickets
        is_auto_split_mode = len(pdf_files) == 1 and available_quantity > 1
        if is_auto_split_mode:
            single_pdf = pdf_files[0]
            try:
                reader = _pdf_reader_for_upload(single_pdf, relax_pdf)
                page_count = len(reader.pages)
            except Exception as e:
                if relax_pdf:
                    # Testing: cannot split — store whole file as a single-ticket listing
                    is_auto_split_mode = False
                    available_quantity = 1
                else:
                    return Response(
                        {'error': f'לא ניתן לקרוא את קובץ ה-PDF. ייתכן שהקובץ פגום או מוגן בסיסמה. ({str(e)})'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            if is_auto_split_mode and page_count != available_quantity:
                if relax_pdf:
                    is_auto_split_mode = False
                    available_quantity = 1
                else:
                    return Response(
                        {'error': 'מספר העמודים בקובץ לא תואם למספר הכרטיסים שהצהרת עליהם. אנא העלה קובץ שבו כל עמוד מכיל כרטיס אחד בלבד.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        elif len(pdf_files) != available_quantity:
            return Response(
                {'error': f'Number of PDF files ({len(pdf_files)}) must match quantity ({available_quantity}). Each ticket requires its own unique PDF file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not pdf_files:
            return Response(
                {'error': 'At least one PDF file is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Block uploading tickets for past events
        event_id = request.data.get('event')
        if event_id:
            try:
                evt = Event.objects.get(pk=event_id)
                if evt.date < timezone.now():
                    return Response(
                        {'error': 'This event has already passed. You cannot upload tickets for past events.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Event.DoesNotExist:
                pass  # Serializer will validate event exists
        
        # SECURITY: File validation - size, MIME type, magic bytes, and extension
        MAX_PDF_SIZE = 5 * 1024 * 1024  # 5MB
        for pdf_file in pdf_files:
            # Size limit
            pdf_file.seek(0, 2)
            file_size = pdf_file.tell()
            pdf_file.seek(0)
            if file_size > MAX_PDF_SIZE:
                return Response(
                    {'error': f'קובץ גדול מדי. הגודל המקסימלי הוא 5MB. הקובץ שלך: {file_size // (1024*1024)}MB.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # MIME + %PDF header (no keyword/text scanning — structure only)
            content_type = getattr(pdf_file, 'content_type', '') or ''
            if not _upload_mime_allowed(pdf_file, relax_pdf):
                return Response(
                    {
                        'error': (
                            f'סוג קובץ לא חוקי או חתימת PDF חסרה (נדרש קובץ PDF אמיתי). התקבל: {content_type or "לא ידוע"}'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Extension
            name = getattr(pdf_file, 'name', '') or ''
            if not name.lower().endswith('.pdf'):
                return Response(
                    {'error': f'שם הקובץ חייב להסתיים ב-.pdf. התקבל: {name or "ללא שם"}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate all PDFs are unique (no duplicate filenames)
        pdf_filenames = [f.name for f in pdf_files]
        if len(pdf_filenames) != len(set(pdf_filenames)):
            return Response(
                {'error': 'Each ticket must have a unique PDF file. Duplicate files are not allowed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate seat data when quantity > 1
        # For single tickets (quantity = 1), row/seat are optional
        # For multiple tickets (quantity > 1), row/seat are REQUIRED for each ticket
        seat_data_list = []
        if available_quantity > 1:
            # Multiple tickets: row and seat are REQUIRED
            for i in range(available_quantity):
                row_key = f'row_number_{i}'
                seat_key = f'seat_number_{i}'
                row_number = request.data.get(row_key, '').strip()
                seat_number = request.data.get(seat_key, '').strip()
                
                if not row_number or not seat_number:
                    return Response(
                        {'error': f'כל כרטיס חייב לכלול שורה, כיסא וקובץ PDF ייחודי. חסרים נתונים עבור כרטיס {i + 1}.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                seat_data_list.append({
                    'row_number': row_number,
                    'seat_number': seat_number
                })
            
            # Validate all seats are unique
            seat_combinations = [(s['row_number'], s['seat_number']) for s in seat_data_list]
            if len(seat_combinations) != len(set(seat_combinations)):
                return Response(
                    {'error': 'כל כרטיס חייב להיות עם שורה וכיסא ייחודיים. לא ניתן להשתמש באותו שורה וכיסא פעמיים.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Single ticket: row and seat are optional, but if provided, store them
            row_key = f'row_number_0'
            seat_key = f'seat_number_0'
            row_number = request.data.get(row_key, '').strip()
            seat_number = request.data.get(seat_key, '').strip()
            if row_number and seat_number:
                seat_data_list.append({
                    'row_number': row_number,
                    'seat_number': seat_number
                })
            else:
                # No row/seat provided for single ticket - that's OK
                seat_data_list.append({
                    'row_number': '',
                    'seat_number': ''
                })
        
        # Create base data dict (without pdf_file)
        base_data = {}
        for key, value in request.data.items():
            if not key.startswith('pdf_file') and key != 'pdf_files_count':
                base_data[key] = value

        # Generate listing_group_id for tickets created together
        listing_group_id = str(uuid.uuid4())

        created_tickets = []

        if is_auto_split_mode:
            # AUTO-SPLIT: Split multi-page PDF into one Ticket per page
            single_pdf = pdf_files[0]
            single_pdf.seek(0)  # Reset after validation read
            reader = _pdf_reader_for_upload(single_pdf, relax_pdf)
            base_name = (single_pdf.name or 'ticket').rsplit('.', 1)[0]

            for i in range(available_quantity):
                writer = PdfWriter()
                writer.add_page(reader.pages[i])
                buffer = io.BytesIO()
                writer.write(buffer)
                buffer.seek(0)

                content_file = ContentFile(buffer.getvalue(), name=f'{base_name}_page_{i + 1}.pdf')

                ticket_data = base_data.copy()
                ticket_data['pdf_file'] = content_file
                ticket_data['available_quantity'] = 1
                ticket_data['listing_group_id'] = listing_group_id

                if i < len(seat_data_list):
                    ticket_data['row_number'] = seat_data_list[i]['row_number']
                    ticket_data['seat_number'] = seat_data_list[i]['seat_number']
                else:
                    ticket_data['row_number'] = ''
                    ticket_data['seat_number'] = ''

                serializer = self.get_serializer(data=ticket_data)
                serializer.is_valid(raise_exception=True)
                try:
                    ticket = serializer.save(seller=request.user)
                except Exception as e:
                    _log_cloudinary_or_storage_error(e, 'ticket_create_auto_split')
                    detail = (str(e) or repr(e))[:500]
                    return Response(
                        {
                            'error': 'Failed to store ticket PDF (Cloudinary/storage). See server logs for full traceback.',
                            'detail': detail,
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                if not ticket.listing_group_id:
                    ticket.listing_group_id = listing_group_id
                    ticket.save(update_fields=['listing_group_id'])

                if not _ticket_pdf_persisted(ticket):
                    _rollback_tickets(created_tickets)
                    try:
                        ticket.delete()
                    except Exception:
                        pass
                    return Response(
                        {
                            'error': (
                                'הקובץ לא נשמר בשרת האחסון. ייתכן שהדפדפן לא שלח את הקובץ (multipart). '
                                'PDF did not persist to storage — check the upload request.'
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                print(f'Ticket {ticket.id} saved (auto-split page {i + 1}/{available_quantity}), Row: {ticket_data.get("row_number", "N/A")}, Seat: {ticket_data.get("seat_number", "N/A")}, Listing Group: {listing_group_id}')
                created_tickets.append(ticket)
        else:
            # NORMAL: One PDF file per Ticket
            for i, pdf_file in enumerate(pdf_files):
                ticket_data = base_data.copy()
                ticket_data['pdf_file'] = pdf_file
                ticket_data['available_quantity'] = 1
                ticket_data['listing_group_id'] = listing_group_id

                if i < len(seat_data_list):
                    ticket_data['row_number'] = seat_data_list[i]['row_number']
                    ticket_data['seat_number'] = seat_data_list[i]['seat_number']

                serializer = self.get_serializer(data=ticket_data)
                serializer.is_valid(raise_exception=True)
                try:
                    ticket = serializer.save(seller=request.user)
                except Exception as e:
                    _log_cloudinary_or_storage_error(e, 'ticket_create_multi_pdf')
                    detail = (str(e) or repr(e))[:500]
                    return Response(
                        {
                            'error': 'Failed to store ticket PDF (Cloudinary/storage). See server logs for full traceback.',
                            'detail': detail,
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                if not ticket.listing_group_id:
                    ticket.listing_group_id = listing_group_id
                    ticket.save(update_fields=['listing_group_id'])

                if not _ticket_pdf_persisted(ticket):
                    _rollback_tickets(created_tickets)
                    try:
                        ticket.delete()
                    except Exception:
                        pass
                    return Response(
                        {
                            'error': (
                                'הקובץ לא נשמר בשרת האחסון. ייתכן שהדפדפן לא שלח את הקובץ (multipart). '
                                'PDF did not persist to storage — check the upload request.'
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                print(f'Ticket {ticket.id} saved with PDF: {pdf_file.name}, Row: {ticket_data.get("row_number", "N/A")}, Seat: {ticket_data.get("seat_number", "N/A")}, Listing Group: {ticket.listing_group_id}')
                created_tickets.append(ticket)
        
        # Return the first ticket (or all tickets if needed)
        # For now, return the first one to maintain API compatibility
        response_serializer = self.get_serializer(created_tickets[0])
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    def perform_create(self, serializer):
        # This is now handled in create() method above
        # Keep for backward compatibility but shouldn't be called
        if not self.request.user.is_authenticated:
            raise PermissionDenied("Authentication required to create tickets.")
        if self.request.user.role != 'seller':
            raise PermissionDenied("Only users with seller role can create tickets.")
        serializer.save(seller=self.request.user)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """Ticket detail; scoped to the same queryset as retrieve (no arbitrary ID peek)."""
        ticket = self.get_object()
        serializer = TicketSerializer(ticket, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        """
        Download PDF ticket file.
        IDOR PROTECTION: Only seller OR buyer with paid order can access.
        - Seller: ticket.seller == request.user
        - Buyer: authenticated user with Order (status paid/completed) containing this ticket
        - Guest: guest_email param with matching Order containing this ticket
        """
        ticket = get_object_or_404(Ticket, pk=pk)
        
        # IDOR: Explicit permission check - seller OR paid-order buyer only
        has_access = False
        
        # 1. Seller can always download
        if request.user.is_authenticated and ticket.seller == request.user:
            has_access = True
        
        # 2. Authenticated buyer: must have paid Order containing this ticket
        if request.user.is_authenticated:
            orders = Order.objects.filter(
                user=request.user,
                status__in=['paid', 'completed']
            )
            for order in orders:
                if order.covers_ticket(ticket.pk):
                    has_access = True
                    break
        
        # 3. Guest buyer: must provide email matching paid Order containing this ticket
        guest_email = request.query_params.get('email')
        if guest_email and not has_access:
            orders = Order.objects.filter(
                guest_email=guest_email.strip(),
                status__in=['paid', 'completed']
            )
            for order in orders:
                if order.covers_ticket(ticket.pk):
                    has_access = True
                    break
        
        if not has_access:
            return Response(
                {'error': 'You do not have permission to download this ticket.'},
                status=status.HTTP_403_FORBIDDEN  # Strict 403 - IDOR prevention
            )
        
        if not ticket.pdf_file:
            return Response(
                {'error': 'PDF file not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            import os

            if getattr(settings, 'USE_CLOUDINARY', False):
                content = _download_ticket_pdf_bytes(ticket)
            else:
                ticket.pdf_file.open('rb')
                try:
                    content = ticket.pdf_file.read()
                finally:
                    ticket.pdf_file.close()

            filename = os.path.basename(ticket.pdf_file.name)

            safe_filename = f"ticket_{ticket.id}_{filename}" if filename else f"ticket_{ticket.id}.pdf"
            # ASCII-only filename for Content-Disposition (avoid Latin-1 encoding errors)
            safe_ascii = ''.join(c if ord(c) < 128 and c not in '"\\' else '_' for c in safe_filename) or f'ticket_{ticket.id}.pdf'

            from django.http import HttpResponse
            response = HttpResponse(content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{safe_ascii}"'
            return response
        except PdfFetchError as e:
            logger.exception('download_pdf Cloudinary fetch failed for ticket %s', ticket.pk)
            body = {'error': 'Could not retrieve PDF file.'}
            if settings.DEBUG and e.errors:
                body['details'] = e.errors[-25:]
            return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.exception('download_pdf failed for ticket %s', ticket.pk)
            err_msg = str(e) if settings.DEBUG else 'Could not retrieve PDF file.'
            return Response(
                {'error': err_msg},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reserve(self, request, pk=None):
        """
        Reserve a ticket for 10 minutes when user clicks 'Buy'
        """
        import logging
        from django.utils import timezone
        from datetime import timedelta
        
        logger = logging.getLogger(__name__)
        ticket = get_object_or_404(Ticket, pk=pk)
        
        # Check if ticket is available
        if ticket.status not in ['active']:
            if ticket.status == 'reserved':
                # Calculate time remaining
                if ticket.reserved_at:
                    time_remaining = (ticket.reserved_at + timedelta(minutes=10)) - timezone.now()
                    if time_remaining.total_seconds() > 0:
                        minutes_remaining = int(time_remaining.total_seconds() / 60)
                        return Response(
                            {
                                'error': 'This ticket is currently in someone else\'s cart. It may become available again in a few minutes.',
                                'status': 'reserved',
                                'minutes_remaining': minutes_remaining
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    return Response(
                        {
                            'error': 'This ticket is currently in someone else\'s cart. It may become available again in a few minutes.',
                            'status': 'reserved'
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                return Response(
                    {'error': 'Ticket is not available for reservation', 'status': ticket.status},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if ticket is already reserved by someone else
        if ticket.status == 'reserved' and ticket.reserved_at:
            # Check if reservation has expired (10 minutes)
            if timezone.now() > ticket.reserved_at + timedelta(minutes=10):
                # Reservation expired, release it
                logger.info(f'Releasing expired reservation for ticket {ticket.id} (reserved at {ticket.reserved_at})')
                ticket.status = 'active'
                ticket.reserved_at = None
                ticket.reserved_by = None
                ticket.reservation_email = None
                ticket.save()
            else:
                # Check if it's reserved by the same user/email
                if request.user.is_authenticated:
                    if ticket.reserved_by != request.user:
                        time_remaining = (ticket.reserved_at + timedelta(minutes=10)) - timezone.now()
                        minutes_remaining = int(time_remaining.total_seconds() / 60)
                        return Response(
                            {
                                'error': 'This ticket is currently in someone else\'s cart. It may become available again in a few minutes.',
                                'status': 'reserved',
                                'minutes_remaining': minutes_remaining
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    # Guest reservation - check email if provided
                    guest_email = request.data.get('email')
                    if guest_email and ticket.reservation_email != guest_email:
                        time_remaining = (ticket.reserved_at + timedelta(minutes=10)) - timezone.now()
                        minutes_remaining = int(time_remaining.total_seconds() / 60)
                        return Response(
                            {
                                'error': 'This ticket is currently in someone else\'s cart. It may become available again in a few minutes.',
                                'status': 'reserved',
                                'minutes_remaining': minutes_remaining
                            },
                            status=status.HTTP_400_BAD_REQUEST
                        )
        
        # Reserve the ticket
        ticket.status = 'reserved'
        ticket.reserved_at = timezone.now()
        if request.user.is_authenticated:
            ticket.reserved_by = request.user
            ticket.reservation_email = None
            logger.info(f'Ticket {ticket.id} reserved by user {request.user.id} ({request.user.username}) at {ticket.reserved_at}')
        else:
            ticket.reserved_by = None
            ticket.reservation_email = request.data.get('email', '')
            logger.info(f'Ticket {ticket.id} reserved by guest email {ticket.reservation_email} at {ticket.reserved_at}')
        ticket.save()
        
        return Response({
            'success': True,
            'message': 'Ticket reserved successfully',
            'reserved_at': ticket.reserved_at.isoformat(),
            'expires_at': (ticket.reserved_at + timedelta(minutes=10)).isoformat()
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def release_reservation(self, request, pk=None):
        """
        Release a ticket reservation (when timer expires or modal closes)
        """
        import logging
        logger = logging.getLogger(__name__)
        ticket = get_object_or_404(Ticket, pk=pk)
        
        # Only allow releasing if ticket is reserved
        if ticket.status != 'reserved':
            return Response(
                {'error': 'Ticket is not reserved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has permission to release (must be the one who reserved it)
        if request.user.is_authenticated:
            if ticket.reserved_by != request.user:
                return Response(
                    {'error': 'You do not have permission to release this reservation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            logger.info(f'Ticket {ticket.id} reservation released by user {request.user.id} ({request.user.username})')
        else:
            # Guest reservation - check email
            guest_email = request.data.get('email')
            if guest_email and ticket.reservation_email != guest_email:
                return Response(
                    {'error': 'You do not have permission to release this reservation'},
                    status=status.HTTP_403_FORBIDDEN
                )
            logger.info(f'Ticket {ticket.id} reservation released by guest email {guest_email or ticket.reservation_email}')
        
        # Release the reservation
        ticket.status = 'active'
        ticket.reserved_at = None
        ticket.reserved_by = None
        ticket.reservation_email = None
        ticket.save()
        
        return Response({
            'success': True,
            'message': 'Reservation released successfully'
        }, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """
        Only allow sellers to delete their own tickets
        """
        ticket = self.get_object()
        if ticket.seller != request.user:
            return Response(
                {'error': 'You can only delete your own tickets.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """
        Only allow sellers to update their own tickets
        """
        ticket = self.get_object()
        if ticket.seller != request.user:
            return Response(
                {'error': 'You can only update your own tickets.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)


@method_decorator(csrf_required, name='dispatch')
class EventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Event model
    """
    queryset = Event.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    # Homepage / Sell need the full upcoming marketplace (default PAGE_SIZE=20 hid whole categories).
    pagination_class = None

    def get_serializer_class(self):
        if self.action == 'list':
            return EventListSerializer
        return EventSerializer
    
    def get_queryset(self):
        # Lazy cart abandonment cleanup when browsing events
        release_abandoned_carts()
        # Only show upcoming events (past events are hidden from marketplace feed)
        now = timezone.now()
        queryset = (
            Event.objects.filter(date__gte=now)
            .select_related('artist')
            .annotate(
                _active_tickets_total=Coalesce(
                    Sum('tickets__available_quantity', filter=Q(tickets__status='active')),
                    Value(0),
                )
            )
            .order_by('date', 'name')
        )
        # Marketplace list: never surface events with no listable inventory
        if self.action == 'list':
            queryset = queryset.filter(_active_tickets_total__gt=0)
        
        # Optional: Filter by artist if provided
        artist_id = self.request.query_params.get('artist', None)
        if artist_id:
            queryset = queryset.filter(artist_id=artist_id)
        
        # Optional: Filter by city if provided
        city = self.request.query_params.get('city', None)
        if city:
            queryset = queryset.filter(city__icontains=city)
        
        # Optional: Search by name if provided
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to increment view_count"""
        instance = self.get_object()
        # Increment view count atomically
        Event.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)
        # Refresh instance to get updated view_count
        instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['get'])
    def tickets(self, request, pk=None):
        """
        Get all tickets for a specific event with filtering and sorting
        """
        import logging
        from django.db.models import F
        logger = logging.getLogger(__name__)
        event = get_object_or_404(Event, pk=pk)
        # Lazy cart abandonment cleanup
        release_abandoned_carts()
        # Public marketplace: only listable inventory (active + qty > 0)
        tickets = Ticket.objects.filter(
            event=event,
            status='active',
            available_quantity__gt=0,
        ).select_related('event', 'seller')
        
        # Filtering
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        min_quantity = request.query_params.get('min_quantity')
        
        print(f"Event {pk} - Filter params: min_price={min_price}, max_price={max_price}, min_quantity={min_quantity}")
        print(f"Event {pk} - Tickets before filtering: {tickets.count()}")
        
        if min_price:
            try:
                tickets = tickets.filter(asking_price__gte=float(min_price))
                print(f"Event {pk} - After min_price filter: {tickets.count()}")
            except ValueError:
                pass
        if max_price:
            try:
                tickets = tickets.filter(asking_price__lte=float(max_price))
                print(f"Event {pk} - After max_price filter: {tickets.count()}")
            except ValueError:
                pass
        if min_quantity:
            try:
                min_qty = int(min_quantity)
                print(f"Event {pk} - Applying min_quantity filter: >= {min_qty}")
                tickets_before = tickets.count()
                
                # HARDCODED TEST: Bypass filter for testing
                # Uncomment the next 4 lines to bypass the filter and return ALL tickets
                # This will help determine if the issue is in the SQL query or elsewhere
                # print(f"HARDCODED TEST: Bypassing min_quantity filter, returning ALL tickets")
                # tickets_after = tickets.count()
                # print(f"Event {pk} - After min_quantity filter (BYPASSED): {tickets_before} -> {tickets_after}")
                # return Response(serializer.data, status=status.HTTP_200_OK)  # Early return for testing
                
                # FIX: For grouped tickets, each ticket has available_quantity=1
                # We need to filter by listing_group_id groups that have enough tickets total
                # Count tickets per listing_group_id and only include groups with count >= min_qty
                
                # Debug: Show all listing_group_ids before filtering
                all_group_ids_raw = list(tickets.values_list('listing_group_id', flat=True).distinct())
                print(f"Event {pk} - All unique listing_group_ids (raw): {all_group_ids_raw[:10]}")
                print(f"Event {pk} - Total unique groups: {len(all_group_ids_raw)}")
                
                # Count tickets per group (including NULL and empty)
                group_counts = {}
                for group_id in all_group_ids_raw:
                    if group_id is None:
                        count = tickets.filter(listing_group_id__isnull=True).count()
                    elif group_id == '':
                        count = tickets.filter(listing_group_id='').count()
                    else:
                        count = tickets.filter(listing_group_id=group_id).count()
                    group_counts[group_id] = count
                    print(f"  Group '{group_id}' (type: {type(group_id).__name__}): {count} tickets")
                
                # Get listing_group_ids that have enough tickets
                if min_qty > 1:
                    # Get non-null, non-empty group IDs with enough tickets
                    # CRITICAL: Exclude NULL and empty string when counting groups
                    valid_group_ids = []
                    
                    # Method 1: Get groups with listing_group_id that is not NULL and not empty
                    grouped_tickets = tickets.exclude(listing_group_id__isnull=True).exclude(listing_group_id='')
                    valid_group_ids = list(
                        grouped_tickets
                        .values('listing_group_id')
                        .annotate(count=Count('id'))
                        .filter(count__gte=min_qty)
                        .values_list('listing_group_id', flat=True)
                    )
                    
                    print(f"Event {pk} - Valid group IDs (count >= {min_qty}): {valid_group_ids}")
                    print(f"Event {pk} - Valid group IDs count: {len(valid_group_ids)}")
                    
                    # Also check single tickets (no listing_group_id) with available_quantity >= min_qty
                    single_tickets_with_qty = tickets.filter(
                        Q(listing_group_id__isnull=True) | Q(listing_group_id=''),
                        available_quantity__gte=min_qty
                    )
                    single_tickets_count = single_tickets_with_qty.count()
                    print(f"Event {pk} - Single tickets (no group) with available_quantity >= {min_qty}: {single_tickets_count}")
                    
                    # Filter: either in a valid group OR (no group AND available_quantity >= min_qty)
                    # Handle both grouped tickets (count by listing_group_id) and single tickets (check available_quantity)
                    if valid_group_ids:
                        tickets = tickets.filter(
                            Q(listing_group_id__in=valid_group_ids) | 
                            Q(listing_group_id__isnull=True, available_quantity__gte=min_qty) |
                            Q(listing_group_id='', available_quantity__gte=min_qty)
                        )
                    else:
                        # No valid groups, only single tickets
                        tickets = tickets.filter(
                            Q(listing_group_id__isnull=True, available_quantity__gte=min_qty) |
                            Q(listing_group_id='', available_quantity__gte=min_qty)
                        )
                else:
                    # min_qty is 1, so all tickets pass
                    pass
                
                tickets_after = tickets.count()
                print(f"Event {pk} - After min_quantity filter (>= {min_qty}): {tickets_before} -> {tickets_after}")
                if min_qty > 1:
                    print(f"Event {pk} - Valid group IDs (first 10): {valid_group_ids[:10]}")
                
                # Debug: Show sample tickets after filtering
                sample_tickets = list(tickets[:10])
                print(f"Event {pk} - Sample tickets after filter ({len(sample_tickets)} shown):")
                for t in sample_tickets:
                    print(f"  Ticket {t.id}: listing_group_id='{t.listing_group_id}' (type: {type(t.listing_group_id).__name__}), available_quantity={t.available_quantity}, status={t.status}")
            except ValueError as e:
                print(f"Event {pk} - Error in min_quantity filter: {e}")
                pass
        
        # Sorting
        sort_by = request.query_params.get('sort', 'price_asc')  # Default: price low to high
        if sort_by == 'price_asc':
            tickets = tickets.order_by('asking_price', '-created_at')
        elif sort_by == 'price_desc':
            tickets = tickets.order_by('-asking_price', '-created_at')
        elif sort_by == 'quantity_desc':
            tickets = tickets.order_by('-available_quantity', 'asking_price')
        elif sort_by == 'newest':
            tickets = tickets.order_by('-created_at')
        elif sort_by == 'best_seats':
            # Best seats = lowest price with highest quantity
            tickets = tickets.order_by('asking_price', '-available_quantity')
        else:
            tickets = tickets.order_by('asking_price', '-created_at')
        
        # Log the count for verification
        count = tickets.count()
        print(f'Active tickets found for event {pk}: {count}')
        logger.info(f'EventViewSet.tickets: Active tickets found for event {pk}: {count}')
        
        tickets = tickets.distinct()
        serializer = TicketListSerializer(tickets, many=True, context={'request': request})
        response = Response(serializer.data)
        response['Cache-Control'] = 'no-store, max-age=0'
        return response


@method_decorator(csrf_required, name='dispatch')
class ArtistViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Artist model
    """
    queryset = Artist.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = None

    def get_serializer_class(self):
        if self.action == 'list':
            return ArtistListSerializer
        return ArtistSerializer
    
    def get_queryset(self):
        queryset = Artist.objects.all().order_by('name')
        # List view: one aggregate per artist (avoid N+1 in total_tickets_count)
        if self.action == 'list':
            queryset = (
                queryset.annotate(
                    _artist_tickets_total=Coalesce(
                        Sum(
                            'events__tickets__available_quantity',
                            filter=Q(events__tickets__status='active'),
                        ),
                        Value(0),
                    )
                )
                .filter(_artist_tickets_total__gt=0)
            )
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """
        Get all events for a specific artist, sorted by date (ascending)
        """
        artist = get_object_or_404(Artist, pk=pk)
        now = timezone.now()
        events = (
            Event.objects.filter(artist=artist, date__gte=now)
            .select_related('artist')
            .annotate(
                _active_tickets_total=Coalesce(
                    Sum('tickets__available_quantity', filter=Q(tickets__status='active')),
                    Value(0),
                )
            )
            .filter(_active_tickets_total__gt=0)
            .order_by('date', 'name')
        )
        serializer = EventListSerializer(events, many=True, context={'request': request})
        return Response(serializer.data)


@csrf_required
@api_view(['POST'])
@permission_classes([AllowAny])
def create_ticket_alert(request):
    """
    Create a ticket alert (waitlist) for an event
    """
    serializer = TicketAlertSerializer(data=request.data)
    if serializer.is_valid():
        event_id = request.data.get('event')
        email = request.data.get('email')
        
        if not event_id or not email:
            return Response(
                {'error': 'event and email are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if alert already exists for this event+email combination
        alert, created = TicketAlert.objects.get_or_create(
            event=event,
            email=email,
            defaults={'notified': False}
        )
        
        if not created:
            return Response(
                {'message': 'You are already on the waitlist for this event', 'alert': TicketAlertSerializer(alert).data},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {'message': 'Successfully added to waitlist', 'alert': serializer.data},
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_pending_tickets(request):
    """
    Admin endpoint to get all pending verification tickets
    Only accessible by superusers (admins)
    """
    if not request.user.is_superuser:
        return Response(
            {'error': 'Permission denied. Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    pending_tickets = Ticket.objects.filter(status='pending_verification').order_by('-created_at')
    serializer = TicketSerializer(pending_tickets, many=True, context={'request': request})
    
    return Response({
        'count': pending_tickets.count(),
        'tickets': serializer.data
    }, status=status.HTTP_200_OK)


@csrf_required
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_approve_ticket(request, ticket_id):
    """
    Admin endpoint to approve a pending ticket (change status to 'active')
    Only accessible by superusers (admins)
    """
    if not request.user.is_superuser:
        return Response(
            {'error': 'Permission denied. Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        if ticket.status != 'pending_verification':
            return Response(
                {'error': f'Ticket is not pending verification. Current status: {ticket.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Approve the ticket: change status to 'active'
        ticket.status = 'active'
        ticket.save()
        
        serializer = TicketSerializer(ticket, context={'request': request})
        return Response({
            'message': 'Ticket approved successfully',
            'ticket': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Ticket.DoesNotExist:
        return Response(
            {'error': 'Ticket not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@csrf_required
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_reject_ticket(request, ticket_id):
    """
    Admin endpoint to reject a pending ticket (change status to 'rejected')
    Only accessible by superusers (admins)
    """
    if not request.user.is_superuser:
        return Response(
            {'error': 'Permission denied. Admin access required.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        
        allowed = ('pending_verification', 'active', 'reserved')
        if ticket.status not in allowed:
            return Response(
                {
                    'error': f'Cannot reject ticket in state {ticket.status}. Allowed: {allowed}',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Invalidate negotiation / checkout on this listing
        Offer.objects.filter(
            ticket_id=ticket.id,
            status__in=('pending', 'accepted'),
        ).update(status='rejected')

        ticket.status = 'rejected'
        ticket.reserved_at = None
        ticket.reserved_by = None
        ticket.reservation_email = None
        ticket.save()

        serializer = TicketSerializer(ticket, context={'request': request})
        return Response({
            'message': 'Ticket rejected successfully',
            'ticket': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Ticket.DoesNotExist:
        return Response(
            {'error': 'Ticket not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@method_decorator(csrf_required, name='dispatch')
class OfferViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Offer model - Bid/Ask Negotiation System
    Rate limited: 10 offers/min to prevent inventory lock spam
    """
    serializer_class = OfferSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'offers'
    pagination_class = None  # Full negotiation history for dashboard (no 20-item page cut-off)

    def get_throttles(self):
        if getattr(self, 'action', None) in ('accept', 'reject', 'counter'):
            return [OffersMutationScopedThrottle()]
        return super().get_throttles()

    def _annotate_offer_flags(self, queryset):
        """One Exists subquery — avoids N+1 when serializing purchase_completed."""
        return queryset.annotate(
            _purchase_done=Exists(
                Order.objects.filter(
                    related_offer_id=OuterRef('pk'),
                    status__in=['paid', 'completed'],
                )
            )
        )
    
    def get_queryset(self):
        from django.utils import timezone
        from django.db.models import Q
        
        queryset = Offer.objects.select_related(
            'buyer',
            'ticket',
            'ticket__seller',
            'ticket__event',
            'ticket__event__artist',
            'parent_offer',
            'counter_offer',
        ).all()
        
        # Filter by user role
        user = self.request.user
        
        # Get offers received (for sellers) - offers on tickets they own
        if self.action == 'received':
            queryset = queryset.filter(ticket__seller=user)
        # Get offers sent (for buyers) - offers they made
        elif self.action == 'sent':
            queryset = queryset.filter(buyer=user)
        # Default: show all offers user is involved in
        else:
            queryset = queryset.filter(Q(buyer=user) | Q(ticket__seller=user))
        
        # Auto-expire old pending offers (still return expired rows for history)
        queryset.filter(status='pending', expires_at__lt=timezone.now()).update(status='expired')
        
        queryset = self._annotate_offer_flags(queryset)
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        from django.utils import timezone
        from datetime import timedelta
        from rest_framework.exceptions import ValidationError
        
        ticket = serializer.validated_data['ticket']
        buyer = self.request.user
        
        # CRITICAL SECURITY: Prevent sellers from making offers on their own tickets
        if ticket.seller == buyer:
            raise ValidationError(
                {'ticket': ['You cannot make an offer on your own ticket.']},
                code='invalid'
            )
        
        # INVENTORY LEAK FIX: Cancel any existing pending offers by this buyer for the same listing
        # before creating the new offer. This releases reserved tickets back to inventory.
        listing_group_id = getattr(ticket, 'listing_group_id', None) or ''
        old_pending = Offer.objects.filter(
            buyer=buyer,
            status='pending',
            offer_round_count=0  # Only initial offers (not counter-offers in a chain)
        )
        if listing_group_id:
            old_pending = old_pending.filter(ticket__listing_group_id=listing_group_id)
        else:
            old_pending = old_pending.filter(ticket_id=ticket.id)
        updated = old_pending.update(status='rejected')
        if updated:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f'Offer leak fix: cancelled {updated} pending offer(s) for buyer {buyer.id} on listing {listing_group_id or ticket.id}')
        
        # Check if ticket is active
        if ticket.status != 'active':
            raise PermissionDenied("This ticket is not available for offers.")
        
        # Block offers on past events
        if _is_event_past(ticket):
            raise ValidationError(
                {'ticket': ['This event has already passed.']},
                code='invalid'
            )
        
        # Set expiration to 48 hours from now
        expires_at = timezone.now() + timedelta(hours=48)
        
        offer = serializer.save(
            buyer=buyer,
            expires_at=expires_at,
            status='pending'
        )
        # Notify the other party (seller receives offer from buyer)
        try:
            from .utils.emails import send_offer_notification
            recipient = offer.ticket.seller
            if recipient and recipient.email:
                send_offer_notification(
                    recipient.email,
                    {
                        'event_name': offer.ticket.event_name or (offer.ticket.event.name if offer.ticket.event else 'Unknown'),
                        'amount': offer.amount,
                        'buyer_username': buyer.username,
                    }
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f'Failed to send offer notification: {e}')
    
    def _get_offer_recipient(self, offer):
        """Return the user who can accept/reject this offer (the recipient, not the creator)."""
        # Round 0, 2: buyer made the offer → seller is recipient
        # Round 1: seller countered → buyer is recipient
        round_count = getattr(offer, 'offer_round_count', 0)
        if round_count in (0, 2):
            return offer.ticket.seller
        return offer.buyer

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept an offer - only the RECIPIENT (not creator) can accept."""
        from datetime import timedelta

        with transaction.atomic():
            offer = Offer.objects.select_for_update().select_related(
                'ticket', 'ticket__seller', 'buyer'
            ).filter(
                pk=pk
            ).first()
            if not offer:
                return Response({'error': 'Offer not found.'}, status=status.HTTP_404_NOT_FOUND)

            recipient = self._get_offer_recipient(offer)
            if recipient is None or request.user.pk != recipient.pk:
                raise PermissionDenied("Only the recipient of this offer can accept it.")

            if offer.status != 'pending':
                return Response(
                    {'error': 'This offer is no longer pending.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if timezone.now() > offer.expires_at:
                offer.status = 'expired'
                offer.save(update_fields=['status'])
                return Response(
                    {'error': 'This offer has expired.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ticket = Ticket.objects.select_for_update().get(pk=offer.ticket_id)
            if ticket.listing_group_id:
                group_rows = Ticket.objects.select_for_update().filter(
                    listing_group_id=ticket.listing_group_id,
                    seller_id=ticket.seller_id,
                )
                for t in group_rows:
                    _sync_expired_cart_reservation(t)
            else:
                _sync_expired_cart_reservation(ticket)
            ticket.refresh_from_db()

            if ticket.status in ('sold', 'rejected', 'pending_payout', 'paid_out'):
                return Response(
                    {'error': 'This listing is no longer available for acceptance.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ticket.status == 'pending_verification':
                return Response(
                    {'error': 'This listing is not yet verified.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if _group_reservation_blocks_seller_accept_offer(ticket, offer):
                return Response(
                    {
                        'error': 'This listing is currently in another buyer\'s checkout. Try again shortly.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            needed_qty = int(offer.quantity or 1)
            if ticket.listing_group_id:
                avail = _group_available_units_for_offer_accept(ticket, offer)
                if avail < needed_qty:
                    return Response(
                        {'error': 'Not enough tickets available to accept this offer.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif ticket.available_quantity < needed_qty:
                return Response(
                    {'error': 'Not enough tickets available to accept this offer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            offer.status = 'accepted'
            offer.accepted_at = timezone.now()
            offer.checkout_expires_at = timezone.now() + timedelta(hours=4)
            offer.save()

            group_ticket_ids = [ticket.id]
            if ticket.listing_group_id:
                group_ticket_ids = list(
                    Ticket.objects.filter(
                        listing_group_id=ticket.listing_group_id,
                        seller_id=ticket.seller_id,
                    ).values_list('id', flat=True)
                )
            Offer.objects.filter(
                ticket_id__in=group_ticket_ids,
                status='pending',
            ).exclude(id=offer.id).update(status='rejected')

            # Non-bundled listing: hold stock for the accepted buyer during checkout window
            if not ticket.listing_group_id:
                hold_fields = []
                if ticket.status == 'active':
                    ticket.status = 'reserved'
                    ticket.reserved_by = offer.buyer
                    ticket.reserved_at = timezone.now()
                    hold_fields = ['status', 'reserved_by', 'reserved_at', 'updated_at']
                elif ticket.status == 'reserved':
                    try:
                        same = int(ticket.reserved_by_id or 0) == int(offer.buyer_id or 0)
                    except (TypeError, ValueError):
                        same = False
                    if (
                        not same
                        and not ticket.reserved_by_id
                        and (ticket.reservation_email or '').strip()
                        and getattr(offer, 'buyer', None)
                    ):
                        be = (getattr(offer.buyer, 'email', None) or '').strip().lower()
                        ge = (ticket.reservation_email or '').strip().lower()
                        same = bool(be and ge and be == ge)
                    if same:
                        ticket.reserved_at = timezone.now()
                        hold_fields = ['reserved_at', 'updated_at']
                if hold_fields:
                    ticket.save(update_fields=hold_fields)

        offer.refresh_from_db()
        serializer = self.get_serializer(offer)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an offer - only the RECIPIENT (not creator) can reject."""
        offer = self.get_object()
        
        # Only the recipient can reject (prevents self-rejection abuse)
        recipient = self._get_offer_recipient(offer)
        if recipient is None or request.user.pk != recipient.pk:
            raise PermissionDenied("Only the recipient of this offer can reject it.")
        
        if offer.status != 'pending':
            return Response(
                {'error': 'This offer is no longer pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        offer.status = 'rejected'
        offer.save()
        
        serializer = self.get_serializer(offer)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def counter(self, request, pk=None):
        """Create a counter-offer - enforces round limits and role validation (Ping-Pong rule)."""
        from django.utils import timezone
        from datetime import timedelta
        from django.db import transaction
        from decimal import Decimal

        offer = self.get_object()
        counter_amount = request.data.get('amount')

        if counter_amount is None or counter_amount == '':
            return Response(
                {'error': 'Counter offer amount is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            counter_amount = Decimal(str(counter_amount))
            if counter_amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid counter offer amount.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Expiration check
        if offer.expires_at and timezone.now() > offer.expires_at:
            offer.status = 'expired'
            offer.save(update_fields=['status'])
            return Response(
                {'error': 'This offer has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Status must be pending
        if offer.status != 'pending':
            return Response(
                {'error': 'This offer is no longer pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Role & Round Validation (Ping-Pong Rule)
        round_count = getattr(offer, 'offer_round_count', 0)

        if round_count >= 2:
            return Response(
                {'error': 'Maximum negotiation rounds reached.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if round_count == 0:
            # Only SELLER can counter the initial buyer offer
            if request.user != offer.ticket.seller:
                raise PermissionDenied("Only the seller can counter this offer.")
        elif round_count == 1:
            # Only BUYER can counter the seller's counter
            if request.user != offer.buyer:
                raise PermissionDenied("Only the buyer can counter this offer.")

        # Atomic state mutation
        with transaction.atomic():
            # Mark original as countered
            offer.status = 'countered'
            offer.save(update_fields=['status'])

            # Create new counter-offer (24h strict timer)
            new_round = round_count + 1
            expires_at = timezone.now() + timedelta(hours=24)

            new_offer = Offer.objects.create(
                buyer=offer.buyer,
                ticket=offer.ticket,
                amount=counter_amount,
                quantity=offer.quantity,
                offer_round_count=new_round,
                parent_offer=offer,
                status='pending',
                expires_at=expires_at,
            )

        serializer = self.get_serializer(new_offer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'], url_path='received')
    def received(self, request):
        """Full history: accepted, rejected, countered, expired — seller view."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='sent')
    def sent(self, request):
        """Full history — buyer view."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@method_decorator(csrf_required, name='dispatch')
class EventRequestViewSet(viewsets.GenericViewSet, viewsets.mixins.CreateModelMixin):
    """
    Logged-in sellers request a missing event/artist (Sell flow growth).
    """
    queryset = EventRequest.objects.select_related('user').all()
    serializer_class = EventRequestSerializer
    permission_classes = [IsAuthenticated]


@method_decorator(csrf_required, name='dispatch')
class ContactMessageViewSet(viewsets.GenericViewSet, viewsets.mixins.CreateModelMixin):
    """
    ViewSet for ContactMessage - allows unauthenticated POST requests
    """
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [AllowAny]  # No authentication required
