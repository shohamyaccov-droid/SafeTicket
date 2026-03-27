from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token


def csrf_required(view):
    """Override DRF's csrf_exempt so CSRF is enforced for cookie-based auth."""
    view.csrf_exempt = False
    return view
from rest_framework import generics, status, viewsets
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
import math
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.db.models import F, Q, Count
from django.db import transaction
from django.core.files.base import ContentFile
import io
import logging
import uuid
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)


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
    EventSerializer,
    EventListSerializer,
    ArtistSerializer,
    ArtistListSerializer,
    TicketAlertSerializer,
    OfferSerializer,
    ContactMessageSerializer
)
from .models import Order, Ticket, Event, Artist, TicketAlert, Offer, ContactMessage
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

User = get_user_model()

# Cart abandonment timeout (minutes)
RESERVATION_TIMEOUT_MINUTES = 10


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
            headers={'User-Agent': 'SafeTicket-PDF/1.0'},
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
    Strict: application/pdf only (+ magic bytes).
    Relaxed (testing): also allow common browser fallbacks for real PDFs (octet-stream, empty).
    """
    ct = (getattr(uploaded_file, 'content_type', '') or '').strip().lower()
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
    return released


@method_decorator(csrf_required, name='dispatch')
class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint. Returns JWT tokens immediately for instant login.
    OTP verification flow is dormant and can be re-enabled when needed.
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    
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
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)
        from .authentication import set_jwt_cookies
        set_jwt_cookies(response, token_data.access_token, token_data)
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
        'user': UserSerializer(user).data,
        'access': str(token_data.access_token),
        'refresh': str(token_data),
        'message': 'Email verified successfully.',
    }, status=status.HTTP_200_OK)


@method_decorator(csrf_required, name='dispatch')
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom login endpoint. Sets JWT tokens as HttpOnly cookies (XSS-safe).
    Returns user data in JSON body; tokens are NOT in body.
    """
    serializer_class = CustomTokenObtainPairSerializer
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            from .authentication import set_jwt_cookies
            access = response.data.get('access')
            refresh = response.data.get('refresh')
            if access and refresh:
                set_jwt_cookies(response, access, refresh)
                # Remove tokens from body - they are in HttpOnly cookies
                del response.data['access']
                del response.data['refresh']
            # Ensure user data in response
            username = request.data.get('username')
            try:
                user = User.objects.get(username=username)
                user_serializer = UserSerializer(user)
                response.data['user'] = user_serializer.data
            except User.DoesNotExist:
                pass
        return response


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
        response = Response({'detail': 'Token refreshed.'}, status=status.HTTP_200_OK)
        set_jwt_cookies(response, access, new_refresh or refresh)
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
            orders = Order.objects.filter(user=user, status__in=['paid', 'completed']).order_by('-created_at')
            orders_serializer = ProfileOrderSerializer(orders, many=True, context={'request': request})
            orders_data = orders_serializer.data if orders_serializer.data else []
        except Exception as e:
            # If serialization fails, return empty list
            orders_data = []
        
        # Get user's ticket listings (only if seller) - ensure we always return a list
        listings_data = []
        if user.role == 'seller':
            try:
                listings = Ticket.objects.filter(seller=user).order_by('-created_at')
                listings_serializer = ProfileListingSerializer(listings, many=True, context={'request': request})
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_activity(request):
    """
    Comprehensive dashboard endpoint returning purchases and listings separately
    Returns: {'purchases': [...], 'listings': {'active': [...], 'sold': [...]}}
    """
    try:
        user = request.user
        
        # Get purchases (orders)
        purchases = Order.objects.filter(
            user=user,
            status__in=['paid', 'completed']
        ).order_by('-created_at')
        purchases_serializer = ProfileOrderSerializer(purchases, many=True, context={'request': request})
        
        # Get listings - show ALL tickets where seller=user (regardless of role)
        # Fix: Previously only showed when user.role=='seller'; tickets could exist but not display
        # if role was mis-set. Now we always fetch by seller=user so dashboard matches Event page.
        active_listings = []
        sold_listings = []
        
        all_listings = Ticket.objects.filter(seller=user).order_by('-created_at')
        listings_serializer = ProfileListingSerializer(all_listings, many=True, context={'request': request})
        
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
        order = Order.objects.filter(user=request.user, id=order_id).first()
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
        order = Order.objects.filter(
            guest_email__iexact=guest_email,
            id=order_id,
            status__in=['paid', 'completed']
        ).first()
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
        'quantity': order.quantity,
        'event_name': order.event_name or (order.ticket.event.name if order.ticket and order.ticket.event else 'Unknown Event'),
        'ticket_details': {
            'section': order.ticket.section if order.ticket else None,
            'row': order.ticket.row if order.ticket else None,
            'venue': order.ticket.event.venue if order.ticket and order.ticket.event else (order.ticket.venue if order.ticket else None),
        } if order.ticket else {},
    }
    
    return Response(receipt_data, status=status.HTTP_200_OK)


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
    
    # CRITICAL: Check if this is a negotiated price from an accepted offer
    offer_id = request.data.get('offer_id')
    negotiated_offer = None
    if offer_id:
        try:
            negotiated_offer = Offer.objects.get(
                id=offer_id,
                buyer=request.user,
                status='accepted'
            )
            print(f"Negotiated offer found: ID={offer_id}, Amount={negotiated_offer.amount}, Quantity={negotiated_offer.quantity}")
            # Override total_amount validation by using the offer's amount + service fee
            # The frontend already calculated the correct total (offer.amount + 10% fee)
            # So we trust the total_amount sent, but we verify it matches the offer
            offer_base_amount = float(negotiated_offer.amount)
            expected_service_fee = offer_base_amount * 0.10
            expected_total = offer_base_amount + expected_service_fee
            received_total = float(request.data.get('total_amount', 0))
            
            # Allow tolerance of 2.00 ILS for JS float vs Python Decimal rounding differences
            AMOUNT_TOLERANCE = 2.00
            if abs(received_total - expected_total) > AMOUNT_TOLERANCE:
                return Response(
                    {'error': f'Amount mismatch. Expected approx {expected_total:.2f}, got {received_total}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Offer.DoesNotExist:
            print(f"WARNING: Offer ID {offer_id} not found or not accepted for user {request.user.id}")
            # Continue without offer validation (backward compatibility)
        except Exception as e:
            print(f"ERROR checking offer: {str(e)}")
            # Continue without offer validation
    
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
                            sent_total = float(request.data.get('total_amount', 0))
                            unit_base = float(reference_ticket.asking_price)
                            expected_unit = math.ceil(unit_base * 1.10)
                            expected_total = expected_unit * order_quantity
                            if sent_total != expected_total:
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
                    # Mark specific tickets as sold
                    ticket_ids = []
                    for t in available_tickets:
                        t.status = 'sold'
                        t.available_quantity = 0
                        t.reserved_at = None
                        t.reserved_by = None
                        t.reservation_email = None
                        t.save()
                        ticket_ids.append(t.id)
                        print(f"Marked ticket {t.id} (Row {t.row_number}, Seat {t.seat_number}) as sold")

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
                            sent_total = float(request.data.get('total_amount', 0))
                            unit_base = float(ticket.asking_price)
                            expected_unit = math.ceil(unit_base * 1.10)
                            expected_total = expected_unit * order_quantity
                            if sent_total != expected_total:
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
                ticket.available_quantity -= order_quantity
                ticket.reserved_at = None
                ticket.reserved_by = None
                ticket.reservation_email = None
                if ticket.available_quantity <= 0:
                    ticket.status = 'sold'
                    ticket.available_quantity = 0
                else:
                    ticket.status = 'active'
                ticket.save()
                ticket_ids = [ticket.id]

            # Create order with 'paid' status (payment already processed)
            order = serializer.save(status='paid', quantity=order_quantity)
            order.ticket_ids = ticket_ids
            order.save(update_fields=['ticket_ids'])

        # Send receipt with PDF attachments (outside transaction so email failure doesn't rollback)
        if request.user.email:
            try:
                from .utils.emails import send_receipt_with_pdf
                send_receipt_with_pdf(request.user.email, order)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(f'Failed to send receipt email: {e}')

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_required
@api_view(['POST'])
@permission_classes([AllowAny])
def payment_simulation(request):
    """
    Simulate payment processing (for development)
    Accepts payment details and returns success/failure
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

    # CRITICAL: Check if this is a negotiated price from an accepted offer
    offer_id = request.data.get('offer_id')
    is_negotiated = False
    if offer_id:
        try:
            # For authenticated users, verify the offer belongs to them
            if request.user.is_authenticated:
                offer = Offer.objects.get(id=offer_id, buyer=request.user, status='accepted')
            else:
                # For guests, just check if offer exists and is accepted
                offer = Offer.objects.get(id=offer_id, status='accepted')
            
            is_negotiated = True
            # Use offer amount as base price (it's already the total for the quantity)
            base_price = float(offer.amount)
            service_fee = base_price * 0.10
            expected_amount = base_price + service_fee
            print(f"Payment simulation: Negotiated price from offer {offer_id}, base={base_price}, expected={expected_amount}")
        except Offer.DoesNotExist:
            print(f"Payment simulation: Offer {offer_id} not found, using ticket price")
            is_negotiated = False
    
    if not is_negotiated:
        # Calculate expected amount with 10% service fee
        # Base price = ticket price * quantity
        base_price = float(ticket.asking_price) * quantity
        service_fee = base_price * 0.10  # 10% service fee
        expected_amount = base_price + service_fee
    
    # Allow tolerance of 2.00 ILS for JS float vs Python Decimal rounding differences
    AMOUNT_TOLERANCE = 2.00
    if abs(float(amount) - expected_amount) > AMOUNT_TOLERANCE:
        return Response(
            {'error': f'Amount does not match {"negotiated offer" if is_negotiated else "ticket"} price. Expected: {expected_amount:.2f} (Base: {base_price:.2f} + Service Fee: {service_fee:.2f}), Got: {amount}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Calculate service fee for response
    service_fee = base_price * 0.10
    total_amount = base_price + service_fee
    
    # Simulate payment processing (always succeeds in dev)
    # In production, this would call the actual payment gateway
    return Response({
        'success': True,
        'payment_id': f'PAY_{ticket_id}_{request.data.get("timestamp", "")}',
        'message': 'Payment processed successfully',
        'base_price': base_price,
        'service_fee': service_fee,
        'total_amount': total_amount,
        'is_negotiated': is_negotiated
    }, status=status.HTTP_200_OK)


@csrf_required
@api_view(['POST'])
@permission_classes([AllowAny])
def guest_checkout(request):
    """
    Create order for guest (non-authenticated) user after payment
    """
    # CRITICAL: Check if this is a negotiated price from an accepted offer
    offer_id = request.data.get('offer_id')
    negotiated_offer = None
    if offer_id:
        try:
            # For guests, verify offer exists and is accepted
            # Note: We can't verify buyer for guests, but we can check offer status
            negotiated_offer = Offer.objects.get(id=offer_id, status='accepted')
            print(f"Guest checkout: Negotiated offer found: ID={offer_id}, Amount={negotiated_offer.amount}")
        except Offer.DoesNotExist:
            print(f"Guest checkout: Offer ID {offer_id} not found or not accepted")
    
    serializer = GuestCheckoutSerializer(data=request.data)
    if serializer.is_valid():
        order_data = serializer.validated_data
        ticket_id = order_data.get('ticket_id')
        
        # Validate total_amount for negotiated offers with 2.00 ILS tolerance
        if negotiated_offer:
            offer_base = float(negotiated_offer.amount)
            expected_total = offer_base + (offer_base * 0.10)
            received_total = float(order_data.get('total_amount', 0))
            if abs(received_total - expected_total) > 2.00:
                return Response(
                    {'error': f'Amount mismatch. Expected approx {expected_total:.2f}, got {received_total}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if not ticket_id:
            return Response(
                {'error': 'ticket_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get listing_group_id if provided (for grouped tickets)
        listing_group_id = order_data.get('listing_group_id')
        
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
                    ticket_ids = []
                    for t in available_tickets:
                        t.status = 'sold'
                        t.available_quantity = 0
                        t.reserved_at = None
                        t.reserved_by = None
                        t.reservation_email = None
                        t.save()
                        ticket_ids.append(t.id)
                        print(f"Guest checkout - Marked ticket {t.id} (Row {t.row_number}, Seat {t.seat_number}) as sold")
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

                # Partial Inventory Update: Decrement available_quantity instead of marking as sold
                ticket.available_quantity -= order_quantity
                ticket.reserved_at = None
                ticket.reserved_by = None
                ticket.reservation_email = None
                if ticket.available_quantity <= 0:
                    ticket.status = 'sold'
                    ticket.available_quantity = 0
                else:
                    ticket.status = 'active'
                ticket.save()
                ticket_ids = [ticket.id]

            # Use ticket's asking price and event name
            total_amount = order_data.get('total_amount', ticket.asking_price)
            event_name = order_data.get('event_name', ticket.event_name)

            # Create order with 'paid' status (payment already processed)
            order = Order.objects.create(
                guest_email=order_data['guest_email'],
                guest_phone=order_data['guest_phone'],
                ticket=ticket,
                total_amount=total_amount,
                quantity=order_quantity,
                event_name=event_name,
                status='paid',
                ticket_ids=ticket_ids
            )

        # Send receipt with PDF attachments to guest
        if order.guest_email:
            try:
                from .utils.emails import send_receipt_with_pdf
                send_receipt_with_pdf(order.guest_email, order)
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(f'Failed to send receipt email: {e}')

        order_serializer = OrderSerializer(order)
        return Response(order_serializer.data, status=status.HTTP_201_CREATED)
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
        """
        Get detailed ticket information including PDF URL
        Only available to authenticated users
        """
        ticket = get_object_or_404(Ticket, pk=pk)
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
            .order_by('date', 'name')
        )
        
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
        # Get all active tickets for this event
        tickets = Ticket.objects.filter(event=event, status='active').select_related('event', 'seller')
        
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
        return Response(serializer.data)


@method_decorator(csrf_required, name='dispatch')
class ArtistViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Artist model
    """
    queryset = Artist.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ArtistListSerializer
        return ArtistSerializer
    
    def get_queryset(self):
        # Show all artists, ordered by name
        queryset = Artist.objects.all().order_by('name')
        
        # Optional: Search by name if provided
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
        
        # Get events for this artist, sorted by date (ascending)
        events = Event.objects.filter(artist=artist).order_by('date', 'name')
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
        
        if ticket.status != 'pending_verification':
            return Response(
                {'error': f'Ticket is not pending verification. Current status: {ticket.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reject the ticket: change status to 'rejected'
        ticket.status = 'rejected'
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
    
    def get_queryset(self):
        from django.utils import timezone
        from django.db.models import Q
        
        queryset = Offer.objects.select_related('buyer', 'ticket', 'ticket__seller', 'ticket__event').all()
        
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
        
        # Auto-expire old offers
        expired_offers = queryset.filter(
            status='pending',
            expires_at__lt=timezone.now()
        )
        expired_offers.update(status='expired')
        
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
        from django.utils import timezone
        from datetime import timedelta
        
        offer = self.get_object()
        
        # Only the recipient can accept (prevents self-acceptance)
        recipient = self._get_offer_recipient(offer)
        if recipient != request.user:
            raise PermissionDenied("Only the recipient of this offer can accept it.")
        
        # Check if offer is still valid
        if offer.status != 'pending':
            return Response(
                {'error': 'This offer is no longer pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if timezone.now() > offer.expires_at:
            offer.status = 'expired'
            offer.save()
            return Response(
                {'error': 'This offer has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Accept the offer
        offer.status = 'accepted'
        offer.accepted_at = timezone.now()
        offer.checkout_expires_at = timezone.now() + timedelta(hours=4)
        offer.save()
        
        # Reject all other pending offers on the same ticket
        Offer.objects.filter(
            ticket=offer.ticket,
            status='pending'
        ).exclude(id=offer.id).update(status='rejected')
        
        serializer = self.get_serializer(offer)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an offer - only the RECIPIENT (not creator) can reject."""
        offer = self.get_object()
        
        # Only the recipient can reject (prevents self-rejection abuse)
        recipient = self._get_offer_recipient(offer)
        if recipient != request.user:
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
        """Get offers received by the seller (offers on tickets they own)"""
        from django.utils import timezone
        
        # Explicitly filter by ticket__seller (the seller receives offers on their tickets)
        queryset = Offer.objects.select_related('buyer', 'ticket', 'ticket__seller', 'ticket__event').filter(
            ticket__seller=request.user
        ).exclude(status='expired').order_by('-created_at')
        
        # Auto-expire old offers
        expired_offers = queryset.filter(expires_at__lt=timezone.now(), status='pending')
        expired_offers.update(status='expired')
        queryset = queryset.exclude(status='expired')
        
        # Disable pagination for this action - return all results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='sent')
    def sent(self, request):
        """Get offers sent by the buyer (offers where current user is the buyer)"""
        from django.utils import timezone

        queryset = Offer.objects.select_related('buyer', 'ticket', 'ticket__seller', 'ticket__event').filter(
            buyer=request.user
        ).exclude(status='expired').order_by('-created_at')

        # Auto-expire old offers
        expired_offers = queryset.filter(expires_at__lt=timezone.now(), status='pending')
        expired_offers.update(status='expired')
        queryset = queryset.exclude(status='expired')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@method_decorator(csrf_required, name='dispatch')
class ContactMessageViewSet(viewsets.GenericViewSet, viewsets.mixins.CreateModelMixin):
    """
    ViewSet for ContactMessage - allows unauthenticated POST requests
    """
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer
    permission_classes = [AllowAny]  # No authentication required
