from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db.models import Sum, Q
from .models import (
    User,
    Order,
    Ticket,
    Event,
    Artist,
    TicketAlert,
    Offer,
    ContactMessage,
    EventRequest,
    Venue,
    VenueSection,
)
from .currency import (
    iso4217_for_country,
    currency_symbol,
    money_amount_for_api,
    iso4217_for_ticket_listing,
    quantize_money_decimal,
)


def build_profile_orders_serialization_context(request, orders_queryset):
    """
    Select-related orders + one batched ticket fetch for ProfileOrderSerializer
    (avoids N+1 in get_tickets / get_status_timeline).
    """
    orders = list(
        orders_queryset.select_related(
            'ticket',
            'ticket__event',
            'ticket__event__artist',
            'ticket__event__venue_place',
            'ticket__venue_section',
            'related_offer',
        )
    )
    ticket_ids = set()
    for o in orders:
        if o.ticket_id:
            ticket_ids.add(o.ticket_id)
        for tid in (o.ticket_ids or []):
            try:
                ticket_ids.add(int(tid))
            except (TypeError, ValueError):
                pass
    profile_tickets_by_id = {}
    if ticket_ids:
        profile_tickets_by_id = {
            t.id: t
            for t in Ticket.objects.filter(id__in=ticket_ids).select_related(
                'event', 'event__artist', 'event__venue_place', 'venue_section'
            )
        }
    return {
        'request': request,
        'profile_tickets_by_id': profile_tickets_by_id,
    }, orders


def build_listing_primary_order_map(listings):
    """
    Map ticket id → latest paid Order for sold listings (ProfileListingSerializer).
    Single forward scan of recent orders instead of one query per listing.
    """
    sold_ids = {
        t.id
        for t in listings
        if getattr(t, 'status', None) in ('sold', 'pending_payout', 'paid_out')
    }
    if not sold_ids:
        return {}
    orders = (
        Order.objects.filter(status__in=['paid', 'completed'])
        .order_by('created_at')
        .select_related('ticket')[:3000]
    )
    ticket_to_order = {}
    for o in orders:
        touched = []
        if o.ticket_id:
            touched.append(o.ticket_id)
        for x in (o.ticket_ids or []):
            try:
                touched.append(int(x))
            except (TypeError, ValueError):
                pass
        for tid in touched:
            if tid in sold_ids:
                ticket_to_order[tid] = o
    return ticket_to_order


def round_shekel_price(value):
    """Whole shekels for ticket face value (matches Ticket.save rounding)."""
    from decimal import Decimal, ROUND_HALF_UP
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def price_as_int_for_json(value):
    """Whole shekels as int in API JSON (222, not 221.99)."""
    if value is None:
        return None
    from decimal import Decimal
    return int(Decimal(str(value)).quantize(Decimal('1')))


def user_can_access_ticket_pdf(user, ticket) -> bool:
    """Same rules as TicketViewSet.download_pdf: seller, staff, or buyer with paid order."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_staff', False) and user.is_staff:
        return True
    if ticket.seller_id == user.id:
        return True
    qs = Order.objects.filter(user=user, status__in=['paid', 'completed']).only('ticket_id', 'ticket_ids')
    for o in qs.iterator():
        if o.covers_ticket(ticket.id):
            return True
    return False


def user_can_access_ticket_receipt(user, ticket) -> bool:
    """Proof of purchase: seller, superuser, or staff (not public / not buyers)."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'is_staff', False):
        return True
    if ticket.seller_id == user.id:
        return True
    return False


def cloudinary_unsigned_https_image_url(fieldfile):
    """
    Unsigned https:// delivery URL from FieldFile.name (public_id).
    Signed URLs can be wrong for some uploads; storage-backed FieldFile.url is preferred in resolved_image_url.
    """
    from django.conf import settings

    if not fieldfile or not getattr(settings, 'USE_CLOUDINARY', False):
        return None
    name = (getattr(fieldfile, 'name', None) or '').strip()
    if not name:
        return None
    try:
        import cloudinary.utils
    except ImportError:
        return None

    public_id = name.replace('\\', '/')
    for opts in (
        {'resource_type': 'image', 'secure': True},
        {'resource_type': 'image', 'type': 'upload', 'secure': True},
    ):
        try:
            url, _ = cloudinary.utils.cloudinary_url(public_id, **opts)
            if url and str(url).startswith('https://'):
                return str(url)
        except Exception:
            continue
    return None


def resolved_image_url(request, fieldfile):
    """
    Prefer the storage layer URL (django-cloudinary-storage knows folder/version/delivery).
    Fallback: unsigned Cloudinary URL from public_id. Avoid signed URLs — they often 401/404 for some assets.
    """
    if not fieldfile:
        return None
    from django.conf import settings

    raw = None
    try:
        raw = fieldfile.url
    except (ValueError, AttributeError):
        raw = None
    if raw:
        s = str(raw).strip()
        if s.startswith('https://') or s.startswith('http://'):
            return s
        if s.startswith('//'):
            return f'https:{s}'
        if request and s.startswith('/'):
            try:
                return request.build_absolute_uri(s)
            except Exception:
                pass
    if getattr(settings, 'USE_CLOUDINARY', False):
        u = cloudinary_unsigned_https_image_url(fieldfile)
        if u:
            return u
    if raw and request and not str(raw).startswith('http'):
        try:
            return request.build_absolute_uri(str(raw).strip())
        except Exception:
            pass
    return None


def absolute_file_url(request, fieldfile):
    """Same resolution as resolved_image_url (single code path for catalog media)."""
    return resolved_image_url(request, fieldfile)


def artist_effective_image_field(artist):
    """
    Single source of truth for artist visuals: cover (banner) first, then profile image.
    Lets Shoham upload once on the artist and reuse everywhere.
    """
    if not artist:
        return None
    if getattr(artist, 'cover_image', None):
        return artist.cover_image
    if getattr(artist, 'image', None):
        return artist.image
    return None


def event_effective_image_field(event):
    """
    Event card/detail image: event-specific upload wins; else artist cover, then artist image.
    """
    if not event:
        return None
    if getattr(event, 'image', None):
        return event.image
    return artist_effective_image_field(getattr(event, 'artist', None))


def artist_image_file_candidates(artist):
    """
    Cover (banner) first, then profile image — same order as artist_effective_image_field,
    but returned as separate candidates so we can skip a broken cover and still use profile.
    """
    if not artist:
        return []
    out = []
    for attr in ('cover_image', 'image'):
        ff = getattr(artist, attr, None)
        if ff and getattr(ff, 'name', None):
            out.append(ff)
    return out


def first_resolved_image_url_for_artist(request, artist):
    for ff in artist_image_file_candidates(artist):
        u = resolved_image_url(request, ff)
        if u:
            return u
    return None


def first_resolved_image_url_for_event(request, event):
    if not event:
        return None
    if getattr(event, 'image', None) and getattr(event.image, 'name', None):
        u = resolved_image_url(request, event.image)
        if u:
            return u
    return first_resolved_image_url_for_artist(request, getattr(event, 'artist', None))


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password2', 'first_name', 'last_name', 'role', 'phone_number')
        extra_kwargs = {
            'email': {'required': True},
            'phone_number': {'required': False},
            'first_name': {'required': False},
            'last_name': {'required': False},
        }
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2')
        phone_number = validated_data.get('phone_number')
        if phone_number == '':
            phone_number = None
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', 'buyer'),
            phone_number=phone_number,
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    is_verified_seller = serializers.BooleanField(read_only=True)
    is_email_verified = serializers.BooleanField(read_only=True)
    profile_image = serializers.SerializerMethodField()

    def get_profile_image(self, obj):
        try:
            field = getattr(obj, 'profile_image', None)
            if not field:
                return None
            return resolved_image_url(self.context.get('request'), field)
        except Exception:
            return None

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'role', 'phone_number', 'payout_details',
            'accepted_escrow_terms', 'profile_image', 'is_verified_seller', 'is_email_verified',
            'is_superuser', 'is_staff', 'date_joined',
        )
        read_only_fields = (
            'id', 'date_joined', 'is_verified_seller', 'is_email_verified', 'is_superuser', 'is_staff',
            'accepted_escrow_terms',
        )


class UpgradeToSellerSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=30, required=True)
    payout_details = serializers.CharField(required=True, min_length=4, max_length=4000)
    accepted_escrow_terms = serializers.BooleanField(required=True)

    def validate_phone_number(self, value):
        s = (value or '').strip()
        if len(s) < 8:
            raise serializers.ValidationError('נא להזין מספר טלפון תקין.')
        return s

    def validate_accepted_escrow_terms(self, value):
        if not value:
            raise serializers.ValidationError('יש לאשר את תנאי הנאמנות.')
        return value


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # JWT payload must be JSON-serializable (no lazy proxies / odd types).
        token['role'] = str(getattr(user, 'role', '') or '')
        token['username'] = str(getattr(user, 'username', '') or '')
        return token



class OrderSerializer(serializers.ModelSerializer):
    ticket_info = serializers.SerializerMethodField()
    tickets = serializers.SerializerMethodField()
    quantity = serializers.IntegerField(default=1, min_value=1, max_value=10)
    
    class Meta:
        model = Order
        fields = (
            'id', 'user', 'ticket', 'ticket_info', 'tickets', 'ticket_ids', 'guest_email', 'guest_phone', 'status',
            'total_amount', 'currency', 'quantity', 'event_name', 'created_at',
            'related_offer', 'final_negotiated_price', 'buyer_service_fee', 'seller_service_fee',
            'total_paid_by_buyer', 'net_seller_revenue',
            'payout_status', 'payout_eligible_date',
        )
        read_only_fields = (
            'id', 'created_at', 'status', 'ticket_info', 'tickets', 'ticket_ids', 'currency',
            'related_offer', 'final_negotiated_price', 'buyer_service_fee', 'seller_service_fee',
            'total_paid_by_buyer', 'net_seller_revenue',
            'payout_status', 'payout_eligible_date',
        )
    
    def create(self, validated_data):
        ticket = validated_data.get('ticket')
        validated_data['currency'] = iso4217_for_ticket_listing(ticket) if ticket else 'ILS'
        return super().create(validated_data)
    
    def get_tickets(self, obj):
        """Return array of tickets with id and pdf_file_url for multi-ticket downloads"""
        cache = self.context.get('profile_tickets_by_id') or {}
        ids = list(getattr(obj, 'ticket_ids', None) or [])
        if not ids and obj.ticket_id:
            ids = [obj.ticket_id]
        elif not ids and obj.ticket:
            ids = [obj.ticket.id]
        tickets = []
        request = self.context.get('request')
        for tid in ids:
            t = cache.get(tid)
            if t is None:
                try:
                    t = Ticket.objects.select_related('event', 'event__artist').get(id=tid)
                except Ticket.DoesNotExist:
                    continue
            url = None
            if t.pdf_file:
                if request:
                    url = request.build_absolute_uri(f'/api/users/tickets/{t.id}/download_pdf/')
                else:
                    url = f'/api/users/tickets/{t.id}/download_pdf/'
            tickets.append({'id': t.id, 'pdf_file_url': url})
        return tickets
    
    def get_ticket_info(self, obj):
        if obj.ticket:
            ev = obj.ticket.event
            return {
                'id': obj.ticket.id,
                'event_name': ev.name if ev else (obj.ticket.event_name or ''),
                'venue': ev.venue_display_name() if ev else (obj.ticket.venue or ''),
                'asking_price': str(obj.ticket.asking_price),
            }
        return None
    
    def validate(self, attrs):
        # Ensure either user or guest fields are provided
        if not attrs.get('user') and not (attrs.get('guest_email') or attrs.get('guest_phone')):
            raise serializers.ValidationError(
                "Either a registered user or guest contact information (email/phone) is required."
            )
        return attrs


class ArtistSerializer(serializers.ModelSerializer):
    """Serializer for Artist model"""
    image_url = serializers.SerializerMethodField()
    total_tickets_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Artist
        fields = (
            'id', 'name', 'image', 'image_url', 'description',
            'total_tickets_count', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'total_tickets_count')
    
    def get_image_url(self, obj):
        return first_resolved_image_url_for_artist(self.context.get('request'), obj)
    
    def get_total_tickets_count(self, obj):
        ann = getattr(obj, '_artist_tickets_total', None)
        if ann is not None:
            return int(ann) if ann else 0
        total = Ticket.objects.filter(
            event__artist=obj,
            status='active'
        ).aggregate(total=Sum('available_quantity'))['total']
        return total or 0


class ArtistListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Artist list view"""
    image_url = serializers.SerializerMethodField()
    total_tickets_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Artist
        fields = (
            'id', 'name', 'image_url', 'total_tickets_count'
        )
        read_only_fields = fields
    
    def get_image_url(self, obj):
        return first_resolved_image_url_for_artist(self.context.get('request'), obj)
    
    def get_total_tickets_count(self, obj):
        ann = getattr(obj, '_artist_tickets_total', None)
        if ann is not None:
            return int(ann) if ann else 0
        total = Ticket.objects.filter(
            event__artist=obj,
            status='active'
        ).aggregate(total=Sum('available_quantity'))['total']
        return total or 0


class ArtistCardSerializer(serializers.ModelSerializer):
    """Minimal artist nest for event lists (avoids per-row ticket aggregate queries)."""

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Artist
        fields = ('id', 'name', 'image_url')
        read_only_fields = fields

    def get_image_url(self, obj):
        return first_resolved_image_url_for_artist(self.context.get('request'), obj)


class VenueSectionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = VenueSection
        fields = ('id', 'name')
        read_only_fields = fields


class VenueDetailSerializer(serializers.ModelSerializer):
    sections = VenueSectionBriefSerializer(many=True, read_only=True)

    class Meta:
        model = Venue
        fields = ('id', 'name', 'city', 'sections')
        read_only_fields = fields


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model"""
    image_url = serializers.SerializerMethodField()
    tickets_count = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()
    artist = ArtistSerializer(read_only=True)
    artist_id = serializers.PrimaryKeyRelatedField(queryset=Artist.objects.all(), source='artist', write_only=True, required=False, allow_null=True)
    venue_detail = VenueDetailSerializer(source='venue_place', read_only=True)

    class Meta:
        model = Event
        fields = (
            'id', 'artist', 'artist_id', 'name', 'date', 'ends_at', 'venue', 'venue_detail', 'city', 'country',
            'currency', 'currency_symbol',
            'image', 'image_url',
            'tickets_count', 'view_count', 'category', 'home_team', 'away_team', 'tournament',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'created_at', 'updated_at', 'tickets_count', 'view_count', 'currency', 'currency_symbol',
            'venue_detail',
        )
    
    def get_currency(self, obj):
        return iso4217_for_country(getattr(obj, 'country', None))
    
    def get_currency_symbol(self, obj):
        return currency_symbol(iso4217_for_country(getattr(obj, 'country', None)))
    
    def get_image_url(self, obj):
        return first_resolved_image_url_for_event(self.context.get('request'), obj)
    
    def get_tickets_count(self, obj):
        ann = getattr(obj, '_active_tickets_total', None)
        if ann is not None:
            return int(ann) if ann else 0
        total = obj.tickets.filter(status='active').aggregate(total=Sum('available_quantity'))['total']
        return total or 0


class EventListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Event list view"""
    image_url = serializers.SerializerMethodField()
    tickets_count = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()
    artist_name = serializers.CharField(source='artist.name', read_only=True)
    artist_detail = ArtistCardSerializer(source='artist', read_only=True)
    venue_detail = VenueDetailSerializer(source='venue_place', read_only=True)

    class Meta:
        model = Event
        fields = (
            'id', 'artist', 'artist_detail', 'artist_name', 'name', 'date', 'venue', 'venue_detail', 'city', 'country',
            'currency', 'currency_symbol',
            'image_url',
            'tickets_count',
            'category', 'home_team', 'away_team', 'tournament'
        )
        read_only_fields = fields
    
    def get_currency(self, obj):
        return iso4217_for_country(getattr(obj, 'country', None))
    
    def get_currency_symbol(self, obj):
        return currency_symbol(iso4217_for_country(getattr(obj, 'country', None)))
    
    def get_image_url(self, obj):
        return first_resolved_image_url_for_event(self.context.get('request'), obj)
    
    def get_tickets_count(self, obj):
        ann = getattr(obj, '_active_tickets_total', None)
        if ann is not None:
            return int(ann) if ann else 0
        total = obj.tickets.filter(status='active').aggregate(total=Sum('available_quantity'))['total']
        return total or 0


class GuestCheckoutSerializer(serializers.Serializer):
    guest_email = serializers.EmailField(required=True)
    guest_phone = serializers.CharField(max_length=20, required=True)
    ticket_id = serializers.IntegerField(required=True)  # Used to find the ticket
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    quantity = serializers.IntegerField(required=True, min_value=1, max_value=10)
    event_name = serializers.CharField(max_length=255, required=False)
    listing_group_id = serializers.CharField(required=False, allow_blank=True, max_length=120)


class TicketSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='seller.username', read_only=True)
    seller_is_verified = serializers.BooleanField(source='seller.is_verified_seller', read_only=True)
    pdf_file_url = serializers.SerializerMethodField()
    receipt_file_url = serializers.SerializerMethodField()
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    listing_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        write_only=True,
        help_text='Listing / buyer price; for IL must be <= original_price (face value)',
    )
    asking_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        help_text='Buyer-facing price (equals face for IL cap; may differ abroad)',
    )
    delivery_method = serializers.ChoiceField(choices=Ticket.DELIVERY_CHOICES, default='instant', required=False)
    # Event data
    event = EventSerializer(read_only=True)
    event_id = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all(), source='event', write_only=True, required=True)
    # Legacy fields for backward compatibility
    event_name = serializers.SerializerMethodField()
    event_date = serializers.SerializerMethodField()
    venue = serializers.SerializerMethodField()
    
    section = serializers.SerializerMethodField()
    venue_section = serializers.PrimaryKeyRelatedField(
        queryset=VenueSection.objects.select_related('venue'),
        required=False,
        allow_null=True,
    )
    custom_section_text = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    row = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    seat_numbers = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    row_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    seat_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    is_together = serializers.BooleanField(required=False, default=True)
    available_quantity = serializers.IntegerField(required=False, default=1, min_value=1, max_value=10)
    
    # Master Architecture fields
    ticket_type = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default='כרטיס אלקטרוני (PDF או תמונה)'
    )
    split_type = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='כל כמות')
    is_obstructed_view = serializers.BooleanField(required=False, default=False)
    verification_status = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='ממתין לאישור', read_only=True)
    has_pdf_file = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = (
            'id', 'seller', 'seller_username', 'seller_is_verified', 'event', 'event_id',
            'event_name', 'event_date', 'venue', 'seat_row', 'section', 'venue_section', 'custom_section_text',
            'row', 'seat_numbers',
            'row_number', 'seat_number', 'listing_group_id',
            'original_price', 'listing_price', 'asking_price', 'currency', 'delivery_method',
            'is_together', 'available_quantity', 'pdf_file', 'pdf_file_url', 'receipt_file', 'receipt_file_url',
            'has_pdf_file', 'status',
            'ticket_type', 'split_type', 'is_obstructed_view', 'verification_status',
            'reserved_at', 'reserved_by', 'reservation_email', 'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'seller', 'status', 'created_at', 'updated_at', 'asking_price', 'currency',
            'reserved_at', 'reserved_by', 'reservation_email', 'event_name', 'event_date', 'venue',
            'section',
        )
        extra_kwargs = {
            'pdf_file': {'write_only': True, 'required': True, 'allow_empty_file': False},
            'receipt_file': {'write_only': True, 'required': False, 'allow_empty_file': False},
        }
    
    def get_event_name(self, obj):
        return obj.event.name if obj.event else (obj.event_name or '')
    
    def get_event_date(self, obj):
        return obj.event.date if obj.event else (obj.event_date or None)
    
    def get_venue(self, obj):
        if obj.event:
            return obj.event.venue_display_name()
        return (obj.venue or '').strip()

    def get_section(self, obj):
        return obj.get_section_display()
    
    def get_has_pdf_file(self, obj):
        return bool(obj.pdf_file)
    
    def get_currency(self, obj):
        return iso4217_for_ticket_listing(obj)
    
    def get_pdf_file_url(self, obj):
        """
        Never expose raw Cloudinary/S3 URLs on the public API. Authorized users get the
        authenticated download endpoint (same authorization as download_pdf).
        """
        if not obj.pdf_file:
            return None
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        if not user_can_access_ticket_pdf(user, obj):
            return None
        if request:
            return request.build_absolute_uri(f'/api/users/tickets/{obj.id}/download_pdf/')
        return f'/api/users/tickets/{obj.id}/download_pdf/'

    def get_receipt_file_url(self, obj):
        if not obj.receipt_file:
            return None
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None
        if not user_can_access_ticket_receipt(user, obj):
            return None
        if request:
            return request.build_absolute_uri(f'/api/users/tickets/{obj.id}/download_receipt/')
        return f'/api/users/tickets/{obj.id}/download_receipt/'
    
    def validate_pdf_file(self, value):
        if not value:
            raise serializers.ValidationError('קובץ כרטיס נדרש (PDF או תמונה) / A ticket file is required.')
        if getattr(value, 'size', None) is not None and int(value.size) < 1:
            raise serializers.ValidationError('קובץ כרטיס ריק / Ticket file is empty.')
        return value

    def validate_receipt_file(self, value):
        if not value:
            return value
        if getattr(value, 'size', None) is not None and int(value.size) < 1:
            raise serializers.ValidationError('קובץ הוכחת קנייה ריק.')
        if getattr(value, 'size', None) is not None and int(value.size) > 15 * 1024 * 1024:
            raise serializers.ValidationError('קובץ הוכחת קנייה גדול מדי (מקס׳ 15MB).')
        return value

    def validate(self, attrs):
        attrs.pop('asking_price', None)
        listing_price = attrs.pop('listing_price', None)

        original_price = attrs.get('original_price')
        if original_price is None:
            raise serializers.ValidationError({
                'original_price': 'Original price (face value) is required.'
            })

        from decimal import Decimal

        # Geo-pricing / receipt rules: Event.venue country ONLY (not artist nationality).
        event = attrs.get('event')
        country = 'IL'
        if event is not None:
            country = (getattr(event, 'country', None) or 'IL').strip().upper()
        if not country:
            country = 'IL'
        cur = iso4217_for_country(country)

        if isinstance(original_price, (int, float, str, Decimal)):
            attrs['original_price'] = quantize_money_decimal(original_price, cur)
        original_price = attrs['original_price']

        if listing_price is not None:
            listing_price = quantize_money_decimal(listing_price, cur)
        else:
            listing_price = original_price

        request = self.context.get('request')
        legal_raw = None
        if request is not None:
            legal_raw = request.data.get('il_legal_declaration')
        legal_ok = legal_raw in (True, 'true', 'True', '1', 'on', 'yes')

        if country == 'IL':
            receipt = attrs.get('receipt_file')
            if not receipt:
                raise serializers.ValidationError({
                    'receipt_file': 'העלאת הוכחת קנייה / קבלה נדרשת לאירועים בישראל.'
                })
            if not legal_ok:
                raise serializers.ValidationError({
                    'il_legal_declaration': 'יש לאשר את תנאי ההצהרה (כולל קבלה ומחיר חוקי).'
                })
            if listing_price > original_price:
                raise serializers.ValidationError({
                    'listing_price': 'מחיר המכירה אינו יכול לעלות על מחיר הפנים (חוק ישראל).',
                    'original_price': 'מחיר הפנים חייב להיות גבוה או שווה למחיר המכירה.',
                })
            attrs['asking_price'] = listing_price
        else:
            attrs['asking_price'] = listing_price

        event_date = attrs.get('event_date')
        if event_date and isinstance(event_date, str):
            from datetime import datetime
            from zoneinfo import ZoneInfo

            try:
                if 'T' in event_date:
                    parts = event_date.split('T')
                    if len(parts) == 2 and '+' not in event_date and 'Z' not in event_date:
                        naive_dt = datetime.fromisoformat(event_date)
                        israel_tz = ZoneInfo('Asia/Jerusalem')
                        attrs['event_date'] = naive_dt.replace(tzinfo=israel_tz)
            except (ValueError, AttributeError, ImportError):
                try:
                    import pytz
                    if 'T' in event_date and '+' not in event_date and 'Z' not in event_date:
                        naive_dt = datetime.fromisoformat(event_date)
                        israel_tz = pytz.timezone('Asia/Jerusalem')
                        attrs['event_date'] = israel_tz.localize(naive_dt)
                except (ImportError, ValueError, AttributeError):
                    pass

        event = attrs.get('event')
        initial = getattr(self, 'initial_data', None)
        raw_section = initial.get('section') if isinstance(initial, dict) else None

        if raw_section not in (None, ''):
            rs = str(raw_section).strip()
            if rs and attrs.get('venue_section') is None:
                if rs.isdigit() and event and getattr(event, 'venue_place_id', None):
                    try:
                        attrs['venue_section'] = VenueSection.objects.get(
                            pk=int(rs), venue_id=event.venue_place_id,
                        )
                    except VenueSection.DoesNotExist:
                        if not (attrs.get('custom_section_text') or '').strip():
                            attrs['custom_section_text'] = rs
                elif not (attrs.get('custom_section_text') or '').strip():
                    attrs['custom_section_text'] = rs

        vs = attrs.get('venue_section')
        if vs is not None and event is not None:
            vplace = getattr(event, 'venue_place_id', None)
            if not vplace or vs.venue_id != event.venue_place_id:
                raise serializers.ValidationError({
                    'venue_section': 'This section does not belong to the selected event venue.'
                })

        return attrs
    
    def create(self, validated_data):
        # Status queue uses Event.country only (venue jurisdiction).
        event = validated_data.get('event')
        country = 'IL'
        if event is not None:
            country = (getattr(event, 'country', None) or 'IL').strip().upper()
        if not country:
            country = 'IL'
        if country == 'IL':
            validated_data['status'] = 'pending_approval'
            validated_data['verification_status'] = 'ממתין לאישור'
        else:
            validated_data['status'] = 'active'
            validated_data['verification_status'] = 'מאומת'
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        validated_data.pop('listing_price', None)
        if 'original_price' in validated_data and 'asking_price' not in validated_data:
            oe = instance.event
            country = (getattr(oe, 'country', None) or 'IL').strip().upper() if oe else 'IL'
            if country == 'IL':
                validated_data['asking_price'] = validated_data['original_price']
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        cur = iso4217_for_ticket_listing(instance)
        for k in ('original_price', 'asking_price'):
            if k in ret and ret[k] is not None:
                ret[k] = money_amount_for_api(getattr(instance, k), cur)
        return ret


class TicketListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing tickets (hides PDF)"""
    seller = serializers.PrimaryKeyRelatedField(read_only=True)  # Add seller ID for security checks
    seller_username = serializers.CharField(source='seller.username', read_only=True)
    seller_is_verified = serializers.BooleanField(source='seller.is_verified_seller', read_only=True)
    original_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    asking_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    delivery_method = serializers.ChoiceField(choices=Ticket.DELIVERY_CHOICES, read_only=True)
    split_type = serializers.CharField(required=False, allow_blank=True, allow_null=True, read_only=True)
    has_pdf_file = serializers.SerializerMethodField()
    is_reserved_slot = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    # Event data
    event_name = serializers.SerializerMethodField()
    event_date = serializers.SerializerMethodField()
    venue = serializers.SerializerMethodField()
    event_venue = serializers.SerializerMethodField()
    event_city = serializers.SerializerMethodField()
    event_country = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = (
            'id', 'seller', 'seller_username', 'seller_is_verified', 'event', 'event_name', 'event_date', 
            'venue', 'event_venue', 'event_city', 'event_country', 'seat_row', 'section', 'row', 'seat_numbers',
            'row_number', 'seat_number', 'listing_group_id',
            'original_price', 'asking_price', 'currency', 'delivery_method',
            'is_together', 'available_quantity', 'split_type', 'status', 'has_pdf_file',
            'is_reserved_slot', 'created_at'
        )
        read_only_fields = fields

    def get_currency(self, obj):
        return iso4217_for_ticket_listing(obj)

    def get_is_reserved_slot(self, obj):
        return obj.status == 'reserved'
    
    def get_event_name(self, obj):
        return obj.event.name if obj.event else (obj.event_name or '')
    
    def get_event_date(self, obj):
        return obj.event.date if obj.event else (obj.event_date or None)
    
    def get_venue(self, obj):
        if obj.event:
            return obj.event.venue_display_name()
        return (obj.venue or '').strip()

    def get_event_venue(self, obj):
        return self.get_venue(obj)

    def get_event_city(self, obj):
        return (obj.event.city or '').strip() if obj.event else ''

    def get_event_country(self, obj):
        return (obj.event.country or '').strip() if obj.event else ''

    def get_section(self, obj):
        return obj.get_section_display()
    
    def get_has_pdf_file(self, obj):
        return bool(obj.pdf_file)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        cur = iso4217_for_ticket_listing(instance)
        for k in ('original_price', 'asking_price'):
            if k in ret and ret[k] is not None:
                ret[k] = money_amount_for_api(getattr(instance, k), cur)
        return ret


class ProfileOrderSerializer(serializers.ModelSerializer):
    """Enhanced serializer for orders in dashboard view - includes ticket details, event image, and receipt"""
    ticket_details = serializers.SerializerMethodField()
    pdf_download_url = serializers.SerializerMethodField()
    tickets = serializers.SerializerMethodField()
    receipt_url = serializers.SerializerMethodField()
    event_image_url = serializers.SerializerMethodField()
    status_timeline = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = (
            'id', 'ticket', 'ticket_details', 'tickets', 'status', 'total_amount', 'currency', 'quantity',
            'event_name', 'created_at', 'pdf_download_url', 'receipt_url',
            'event_image_url', 'status_timeline',
            'related_offer', 'final_negotiated_price', 'buyer_service_fee', 'seller_service_fee',
            'total_paid_by_buyer', 'net_seller_revenue',
            'payout_status', 'payout_eligible_date',
        )
        read_only_fields = fields

    def get_tickets(self, obj):
        """Return array of tickets with id and pdf_file_url for multi-ticket downloads"""
        cache = self.context.get('profile_tickets_by_id') or {}
        ids = list(getattr(obj, 'ticket_ids', None) or [])
        if not ids and obj.ticket_id:
            ids = [obj.ticket_id]
        elif not ids and obj.ticket:
            ids = [obj.ticket.id]
        tickets = []
        request = self.context.get('request')
        for tid in ids:
            t = cache.get(tid)
            if t is None:
                try:
                    t = Ticket.objects.select_related('event', 'event__artist').get(id=tid)
                except Ticket.DoesNotExist:
                    continue
            url = None
            if t.pdf_file:
                if request:
                    url = request.build_absolute_uri(f'/api/users/tickets/{t.id}/download_pdf/')
                else:
                    url = f'/api/users/tickets/{t.id}/download_pdf/'
            tickets.append({'id': t.id, 'pdf_file_url': url})
        return tickets
    
    def get_ticket_details(self, obj):
        if obj.ticket:
            ev = obj.ticket.event
            vlabel = ev.venue_display_name() if ev else (obj.ticket.venue or '')
            td = {
                'id': obj.ticket.id,
                'event_name': ev.name if ev else (obj.ticket.event_name or 'Unknown Event'),
                'event_date': ev.date if ev else obj.ticket.event_date,
                'venue': vlabel,
                'event_venue': vlabel,
                'city': ev.city if ev else '',
                'country': ev.country if ev else '',
                'seat_row': getattr(obj.ticket, 'seat_row', None),
                'section': obj.ticket.get_section_display() if obj.ticket else '',
                'row': getattr(obj.ticket, 'row', None) or '',
                'seat_numbers': getattr(obj.ticket, 'seat_numbers', None) or '',
                'original_listing_price': str(obj.ticket.asking_price),
                'asking_price': str(obj.ticket.asking_price),
            }
            if obj.final_negotiated_price is not None:
                td['final_negotiated_price'] = str(obj.final_negotiated_price)
            return td
        return {
            'event_name': obj.event_name,
        }
    
    def get_pdf_download_url(self, obj):
        if obj.ticket and obj.ticket.pdf_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(f'/api/users/tickets/{obj.ticket.id}/download_pdf/')
            return f'/api/users/tickets/{obj.ticket.id}/download_pdf/'
        return None
    
    def get_receipt_url(self, obj):
        """Generate receipt URL for the order"""
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(f'/api/users/orders/{obj.id}/receipt/')
        return f'/api/users/orders/{obj.id}/receipt/'
    
    def get_event_image_url(self, obj):
        """Event card image: event upload, or artist cover/image (fixes artists like Omar Adam with no per-event image)."""
        if not obj.ticket:
            return None
        ev = obj.ticket.event
        if not ev:
            return None
        return first_resolved_image_url_for_event(self.context.get('request'), ev)
    
    def get_status_timeline(self, obj):
        """Return status timeline for order progress. When paid+has PDFs, show ready for download."""
        cache = self.context.get('profile_tickets_by_id') or {}
        ids = list(getattr(obj, 'ticket_ids', None) or [])
        if not ids and obj.ticket_id:
            ids = [obj.ticket_id]
        has_pdf = False
        for tid in ids:
            t = cache.get(tid)
            if t is None and obj.ticket_id == tid and obj.ticket:
                t = obj.ticket
            if t and t.pdf_file:
                has_pdf = True
                break
        if not has_pdf and obj.ticket and obj.ticket.pdf_file:
            has_pdf = True
        # If paid/completed AND has PDFs (instant delivery), show step 3 (ready for download)
        ready_for_download = obj.status in ['paid', 'completed'] and has_pdf
        current_step = 3 if ready_for_download else (2 if obj.status == 'paid' else (1 if obj.status == 'pending' else 0))
        labels = {1: 'הזמנה אושרה', 2: 'מעבד', 3: 'מוכן להורדה'}
        return {
            'current_step': current_step,
            'current_label': labels.get(current_step, obj.status),
            'steps': [
                {'step': 1, 'label': 'הזמנה אושרה', 'completed': obj.status in ['paid', 'completed']},
                {'step': 2, 'label': 'מעבד', 'completed': ready_for_download},
                {'step': 3, 'label': 'מוכן להורדה', 'completed': ready_for_download},
            ]
        }


class ProfileListingSerializer(serializers.ModelSerializer):
    """Serializer for user's ticket listings in profile view"""
    asking_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    event_image_url = serializers.SerializerMethodField()
    event_name_display = serializers.SerializerMethodField()
    event_date_display = serializers.SerializerMethodField()
    venue_display = serializers.SerializerMethodField()
    event_city = serializers.SerializerMethodField()
    event_country = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()
    expected_payout = serializers.SerializerMethodField()
    order_count = serializers.SerializerMethodField()
    escrow_payout_status = serializers.SerializerMethodField()
    escrow_payout_eligible_date = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = (
            'id', 'event_name', 'event_date', 'venue', 'seat_row', 
            'section', 'row', 'seat_numbers',
            'original_price', 'asking_price', 'is_together', 'available_quantity', 'status', 'created_at',
            'event_image_url', 'event_name_display', 'event_date_display', 'venue_display',
            'event_city', 'event_country',
            'expected_payout', 'order_count',
            'escrow_payout_status', 'escrow_payout_eligible_date', 'currency',
        )
        read_only_fields = fields

    def _primary_order_for_sold_ticket(self, obj):
        if obj.status not in ['sold', 'pending_payout', 'paid_out']:
            return None
        cache_map = self.context.get('listing_primary_order_map')
        if isinstance(cache_map, dict) and obj.id in cache_map:
            return cache_map[obj.id]
        order = (
            Order.objects.filter(status__in=['paid', 'completed'])
            .filter(Q(ticket_id=obj.id) | Q(ticket_ids__contains=[obj.id]))
            .order_by('-created_at')
            .first()
        )
        if order is None:
            for o in Order.objects.filter(status__in=['paid', 'completed']).order_by('-created_at')[:200]:
                if o.covers_ticket(obj.id):
                    order = o
                    break
        return order
    
    def get_event_image_url(self, obj):
        if obj.event and obj.event.image:
            return absolute_file_url(self.context.get('request'), obj.event.image)
        return None
    
    def get_event_name_display(self, obj):
        return obj.event.name if obj.event else (obj.event_name or 'Unknown Event')
    
    def get_event_date_display(self, obj):
        return obj.event.date if obj.event else obj.event_date
    
    def get_venue_display(self, obj):
        if obj.event:
            return obj.event.venue_display_name()
        return (obj.venue or '').strip()

    def get_event_city(self, obj):
        return (obj.event.city or '').strip() if obj.event else ''

    def get_event_country(self, obj):
        return (obj.event.country or '').strip() if obj.event else ''

    def get_section(self, obj):
        return obj.get_section_display()
    
    def get_expected_payout(self, obj):
        """Sold listing: seller net from order row when present, else listing asking_price."""
        if obj.status not in ['sold', 'pending_payout', 'paid_out']:
            return None
        order = self._primary_order_for_sold_ticket(obj)
        if order and order.net_seller_revenue is not None:
            return float(order.net_seller_revenue)
        return float(obj.asking_price)

    def get_escrow_payout_status(self, obj):
        order = self._primary_order_for_sold_ticket(obj)
        if not order:
            return None
        return order.payout_status

    def get_escrow_payout_eligible_date(self, obj):
        order = self._primary_order_for_sold_ticket(obj)
        if not order or not order.payout_eligible_date:
            return None
        return order.payout_eligible_date.isoformat()

    def get_order_count(self, obj):
        """Get number of orders for this ticket"""
        return len(list(obj.orders.all()))

    def get_currency(self, obj):
        if obj.status in ('sold', 'pending_payout', 'paid_out'):
            order = self._primary_order_for_sold_ticket(obj)
            if order and getattr(order, 'currency', None):
                return str(order.currency).strip().upper()
        return iso4217_for_ticket_listing(obj)


class TicketAlertSerializer(serializers.ModelSerializer):
    """Serializer for TicketAlert model"""
    event_name = serializers.CharField(source='event.name', read_only=True)
    
    class Meta:
        model = TicketAlert
        fields = ('id', 'event', 'event_name', 'email', 'created_at', 'notified', 'notified_at')
        read_only_fields = ('id', 'created_at', 'notified', 'notified_at')


class OfferSerializer(serializers.ModelSerializer):
    """Serializer for Offer model"""
    buyer_username = serializers.CharField(source='buyer.username', read_only=True)
    ticket_details = TicketListSerializer(source='ticket', read_only=True)
    is_expired = serializers.SerializerMethodField()
    is_checkout_expired = serializers.SerializerMethodField()
    time_remaining = serializers.SerializerMethodField()
    checkout_time_remaining = serializers.SerializerMethodField()
    purchase_completed = serializers.SerializerMethodField()
    ticket_listing_status = serializers.CharField(source='ticket.status', read_only=True)
    
    class Meta:
        model = Offer
        fields = (
            'id', 'buyer', 'buyer_username', 'ticket', 'ticket_details',
            'amount', 'currency', 'quantity', 'status', 'expires_at', 'accepted_at', 'checkout_expires_at',
            'offer_round_count', 'parent_offer', 'counter_offer',
            'is_expired', 'is_checkout_expired',
            'time_remaining', 'checkout_time_remaining',
            'purchase_completed', 'ticket_listing_status',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'buyer', 'currency', 'expires_at', 'accepted_at', 'checkout_expires_at', 'created_at', 'updated_at')
    
    def get_purchase_completed(self, obj):
        v = getattr(obj, '_purchase_done', None)
        if v is not None:
            return bool(v)
        return Order.objects.filter(
            related_offer_id=obj.id,
            status__in=['paid', 'completed'],
        ).exists()
    
    def get_is_expired(self, obj):
        from django.utils import timezone
        if obj.status == 'expired':
            return True
        if obj.status == 'accepted':
            # Pending-offer expires_at must not mark accepted offers "expired" while checkout is open
            if obj.checkout_expires_at:
                return timezone.now() > obj.checkout_expires_at
            return False
        if obj.expires_at:
            return timezone.now() > obj.expires_at
        return False
    
    def get_is_checkout_expired(self, obj):
        from django.utils import timezone
        if obj.status == 'accepted' and obj.checkout_expires_at:
            return timezone.now() > obj.checkout_expires_at
        return False
    
    def get_time_remaining(self, obj):
        from django.utils import timezone
        if obj.expires_at:
            remaining = obj.expires_at - timezone.now()
            return max(0, int(remaining.total_seconds()))
        return None
    
    def get_checkout_time_remaining(self, obj):
        from django.utils import timezone
        if obj.status == 'accepted' and obj.checkout_expires_at:
            remaining = obj.checkout_expires_at - timezone.now()
            return max(0, int(remaining.total_seconds()))
        return None

    def validate(self, attrs):
        ticket = attrs.get('ticket')
        if ticket is None and getattr(self, 'instance', None) is not None:
            ticket = self.instance.ticket

        if 'amount' in attrs and attrs['amount'] is not None:
            from decimal import Decimal

            try:
                amt = Decimal(str(attrs['amount']))
            except Exception:
                raise serializers.ValidationError({'amount': 'Invalid offer amount.'})
            if amt <= 0:
                raise serializers.ValidationError({'amount': 'Offer amount must be greater than zero.'})

            if ticket is not None:
                cur = iso4217_for_ticket_listing(ticket)
                attrs['amount'] = quantize_money_decimal(amt, cur)
                if attrs['amount'] <= 0:
                    raise serializers.ValidationError({'amount': 'Offer amount must be greater than zero.'})
        return attrs

    def create(self, validated_data):
        ticket = validated_data['ticket']
        validated_data['currency'] = iso4217_for_ticket_listing(ticket)
        return super().create(validated_data)

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        cur = instance.currency or iso4217_for_ticket_listing(instance.ticket)
        if 'amount' in ret and ret['amount'] is not None:
            ret['amount'] = money_amount_for_api(instance.amount, cur)
        ret['currency'] = cur
        return ret


class EventRequestSerializer(serializers.ModelSerializer):
    """Authenticated seller submits a missing-event request from the Sell flow."""

    class Meta:
        model = EventRequest
        fields = ('id', 'event_hint', 'details', 'category', 'created_at')
        read_only_fields = ('id', 'created_at')

    def validate_details(self, value):
        text = (value or '').strip()
        if len(text) < 8:
            raise serializers.ValidationError('נא לתת לפחות משפט אחד עם פרטי האירוע.')
        return text

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        return EventRequest.objects.create(
            user=user,
            submitted_email=(getattr(user, 'email', None) or '').strip(),
            **validated_data,
        )


class ContactMessageSerializer(serializers.ModelSerializer):
    """Serializer for ContactMessage model"""
    
    class Meta:
        model = ContactMessage
        fields = ('id', 'name', 'email', 'order_number', 'message', 'created_at', 'is_resolved')
        read_only_fields = ('id', 'created_at', 'is_resolved')
