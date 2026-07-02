from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.secure_ticket_storage import ticket_pdf_upload_to, ticket_receipt_upload_to


class User(AbstractUser):
    """
    Custom User model with roles (Buyer/Seller) and additional fields
    """
    ROLE_CHOICES = [
        ('buyer', 'Buyer'),
        ('seller', 'Seller'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='buyer')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    payout_details = models.TextField(
        blank=True,
        default='',
        help_text='Legacy JSON blob from seller onboarding (see structured bank fields below)',
    )
    account_holder_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Legal name on the seller bank account (for manual payouts)',
    )
    bank_name = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='Bank name or Israeli bank code',
    )
    branch_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text='Bank branch number',
    )
    account_number = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text='Bank account number for seller payouts',
    )
    accepted_escrow_terms = models.BooleanField(default=False)
    escrow_terms_accepted_at = models.DateTimeField(null=True, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    is_verified_seller = models.BooleanField(default=False, help_text="Verified seller badge (for trust indicators)")
    is_email_verified = models.BooleanField(default=True, help_text="Email verified via OTP (False when OTP enforcement is enabled)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    class Meta:
        db_table = 'users'


class Artist(models.Model):
    """
    Artist model for grouping events by artist/performer
    """
    CATEGORY_CHOICES = [
        ('music', 'Music'),
        ('standup', 'Standup'),
        ('sports', 'Sports'),
        ('theater', 'Theater'),
    ]

    name = models.CharField(max_length=255, help_text="Artist name")
    image = models.ImageField(upload_to='artists/images/', blank=True, null=True, help_text="Artist image/photo")
    description = models.TextField(blank=True, null=True, help_text="Artist description")
    genre = models.CharField(max_length=100, blank=True, null=True, help_text="Genre (e.g., Pop, Rock, Sports)")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='music',
        help_text='Homepage category for marketplace discovery rows',
    )
    is_international = models.BooleanField(
        default=False,
        help_text='Hide from local-market homepage discovery when enabled',
    )
    cover_image = models.ImageField(upload_to='artist_covers/', blank=True, null=True, help_text="Artist cover/banner image")
    youtube_link = models.URLField(blank=True, null=True, help_text="YouTube channel or video link")
    spotify_link = models.URLField(blank=True, null=True, help_text="Spotify artist page link")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]


class Venue(models.Model):
    """Structured venue record for seating maps and relational sections."""

    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name}, {self.city}'

    class Meta:
        ordering = ['name', 'city']
        constraints = [
            models.UniqueConstraint(fields=['name', 'city'], name='users_venue_unique_name_city'),
        ]


class VenueSection(models.Model):
    """A seating / gate / block label belonging to one Venue."""

    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.venue})'

    class Meta:
        ordering = ['venue', 'name']
        constraints = [
            models.UniqueConstraint(fields=['venue', 'name'], name='users_venuesection_unique_venue_name'),
        ]


def _ticket_pdf_storage():
    """
    Ticket PDFs must upload as resource_type=raw on Cloudinary (authenticated delivery).
    Images (Artist/Event/User) use STORAGES['default'] → MediaCloudinaryStorage.
    Local/dev uses STORAGES['ticket_pdfs'] → FileSystemStorage (see settings.STORAGES).
    """
    from django.core.files.storage import storages

    return storages['ticket_pdfs']


def _ticket_receipt_storage():
    """Receipt files use the same authenticated raw storage backend as ticket PDFs."""
    from django.core.files.storage import storages

    return storages['ticket_receipts']


class Event(models.Model):
    """
    Centralized Event model for grouping tickets
    """
    VENUE_CHOICES = [
        ('היכל מנורה מבטחים', 'היכל מנורה מבטחים'),
        ('אצטדיון בלומפילד', 'אצטדיון בלומפילד'),
        ('אצטדיון בלומפילד (הופעות)', 'אצטדיון בלומפילד (הופעות)'),
        ('פיס ארנה ירושלים', 'פיס ארנה ירושלים'),
        ('סמי עופר', 'סמי עופר'),
        ('בארבי תל אביב', 'בארבי תל אביב'),
        ('אחר', 'אחר'),
    ]
    
    artist = models.ForeignKey(
        'Artist',
        on_delete=models.CASCADE,
        related_name='events',
        null=True,
        blank=True,
        help_text="The artist/performer for this event"
    )
    name = models.CharField(max_length=255, help_text="Event name")
    date = models.DateTimeField(help_text="Event date and time")
    venue = models.CharField(
        max_length=255,
        choices=VENUE_CHOICES,
        default='היכל מנורה מבטחים',
        help_text="Venue name"
    )
    venue_place = models.ForeignKey(
        'Venue',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        help_text='Optional structured venue (seating sections); leave empty for legacy/text-only events.',
    )
    city = models.CharField(max_length=100, help_text="City where event takes place")
    image = models.ImageField(upload_to='events/images/', blank=True, null=True, help_text="Event image/photo")
    view_count = models.IntegerField(default=0, help_text="Number of times this event page has been viewed (for popularity tracking)")
    
    # Event categorization and status
    CATEGORY_CHOICES = [
        ('concert', 'הופעות'),
        ('sport', 'ספורט'),
        ('theater', 'תיאטרון'),
        ('festival', 'פסטיבלים'),
        ('standup', 'סטנדאפ'),
    ]
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='concert',
        help_text="Event category"
    )
    
    STATUS_CHOICES = [
        ('פעיל', 'פעיל'),
        ('בוטל', 'בוטל'),
        ('נדחה', 'נדחה'),
        ('סולד אאוט', 'סולד אאוט'),
    ]
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='פעיל',
        help_text="Event status"
    )
    
    # Event timing details
    doors_open = models.TimeField(blank=True, null=True, help_text="Time when doors open")
    
    # Age restrictions
    AGE_RESTRICTION_CHOICES = [
        ('ללא הגבלה', 'ללא הגבלה'),
        ('18+', '18+'),
        ('21+', '21+'),
    ]
    age_restriction = models.CharField(
        max_length=50,
        choices=AGE_RESTRICTION_CHOICES,
        default='ללא הגבלה',
        help_text="Age restriction for the event"
    )
    
    # Sports-specific fields
    home_team = models.CharField(max_length=255, blank=True, null=True, help_text="Home team name (for sports events)")
    away_team = models.CharField(max_length=255, blank=True, null=True, help_text="Away team name (for sports events)")
    tournament = models.CharField(max_length=255, blank=True, null=True, help_text="Tournament/League name (e.g., Champions League, Premier League)")
    
    # Geo / regulatory jurisdiction — stored as ISO 3166-1 alpha-2; admin shows full names.
    COUNTRY_CHOICES = [
        ('IL', 'Israel'),
        ('US', 'United States'),
        ('GB', 'United Kingdom'),
        ('ES', 'Spain'),
        ('FR', 'France'),
        ('DE', 'Germany'),
        ('IT', 'Italy'),
        ('GR', 'Greece'),
        ('CY', 'Cyprus'),
        ('AE', 'United Arab Emirates'),
    ]
    country = models.CharField(
        max_length=2,
        choices=COUNTRY_CHOICES,
        default='IL',
        help_text='Event location country (anti-scalping rules use this field, not city).',
    )
    ends_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the show ends (optional). Escrow payout uses ends_at + 36h when set; else date + 36h.',
    )

    high_demand = models.BooleanField(
        default=False,
        help_text='Show high-demand urgency badge on discovery (e.g. official launch headliners).',
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def venue_display_name(self):
        """Buyer-facing venue: prefer linked Venue.name (full hall) over the choice field (e.g. אחר)."""
        vp = getattr(self, 'venue_place', None)
        if vp is not None:
            name = (vp.name or '').strip()
            if name:
                return name
        return (self.venue or '').strip()
    
    def __str__(self):
        # For sports events with teams, show team matchup
        if self.category == 'sport':
            if self.home_team and self.away_team:
                tournament_str = f" - {self.tournament}" if self.tournament else ""
                return f"{self.home_team} vs {self.away_team}{tournament_str}"
        # Standard format for all other events
        return f"{self.name} - {self.venue}, {self.city}"
    
    class Meta:
        ordering = ['-date', 'name']
        indexes = [
            models.Index(fields=['-date', 'name']),
            models.Index(fields=['city']),
        ]


class Ticket(models.Model):
    """
    Ticket listing model for sellers to list their tickets
    """
    STATUS_CHOICES = [
        ('pending_approval', 'Pending Approval'),
        ('active', 'Active'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
        ('pending_payout', 'Pending Payout'),
        ('paid_out', 'Paid Out'),
        ('rejected', 'Rejected'),
    ]
    
    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tickets'
    )
    
    # Link to Event model
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='tickets',
        null=True,
        blank=True,
        help_text="The event this ticket is for"
    )
    
    # Legacy fields - kept for backward compatibility during migration
    event_name = models.CharField(max_length=255, blank=True, null=True, help_text="Legacy field - use event.name instead")
    event_date = models.DateTimeField(blank=True, null=True, help_text="Legacy field - use event.date instead")
    venue = models.CharField(max_length=255, blank=True, null=True, help_text="Legacy field - use event.venue instead")
    seat_row = models.CharField(max_length=100, blank=True, null=True, help_text="Optional seat/row information (legacy field)")
    
    # Detailed seating information — section_legacy holds migrated/free-text history; prefer venue_section / custom_section_text.
    section_legacy = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Legacy section label (e.g. Gate 11); kept for migrated rows and display fallback.',
    )
    venue_section = models.ForeignKey(
        'VenueSection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        help_text='Structured section when the event venue defines sections',
    )
    custom_section_text = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='User-entered section when no structured sections exist',
    )
    row = models.CharField(max_length=50, blank=True, null=True, help_text="Row number (e.g., Row 12)")
    seat_numbers = models.CharField(max_length=200, blank=True, null=True, help_text="Seat numbers (e.g., 12-15). Not shown to buyers before purchase.")
    
    # Individual seat data for each ticket
    row_number = models.CharField(max_length=50, blank=True, null=True, help_text="Specific row number for this individual ticket")
    seat_number = models.CharField(max_length=50, blank=True, null=True, help_text="Specific seat number for this individual ticket")
    
    # Listing grouping - tickets created together share the same listing_group_id
    listing_group_id = models.CharField(max_length=100, blank=True, null=True, help_text="UUID to group tickets from the same listing session")
    
    # Pricing - Israeli Consumer Protection Law: resale price must equal face value
    original_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Face value of the ticket (final price)")
    asking_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price (always equals original_price per Israeli law)")
    
    def get_section_display(self):
        """Buyer-facing section label (structured name, custom text, or legacy)."""
        vid = getattr(self, 'venue_section_id', None)
        if vid:
            vs = getattr(self, 'venue_section', None)
            if vs is not None:
                return (vs.name or '').strip()
            try:
                vs = VenueSection.objects.filter(pk=vid).values_list('name', flat=True).first()
                return (vs or '').strip()
            except Exception:
                pass
        txt = (self.custom_section_text or '').strip()
        if txt:
            return txt
        return (self.section_legacy or '').strip()

    def save(self, *args, **kwargs):
        # Quantize per listing currency (ILS: whole units; global: 0.01).
        from decimal import Decimal
        from .currency import quantize_money_decimal, iso4217_for_country
        country = 'IL'
        if self.event_id:
            try:
                ev = getattr(self, 'event', None)
                if ev is not None and getattr(ev, 'pk', None) == self.event_id:
                    country = (getattr(ev, 'country', None) or 'IL').strip().upper()
                else:
                    country = (
                        Event.objects.filter(pk=self.event_id).values_list('country', flat=True).first() or 'IL'
                    )
                    country = (country or 'IL').upper()
            except Exception:
                country = 'IL'
        cur = iso4217_for_country(country)
        if self.original_price is not None:
            if isinstance(self.original_price, (int, float, str, Decimal)):
                self.original_price = quantize_money_decimal(self.original_price, cur)
        if self.asking_price is not None:
            if isinstance(self.asking_price, (int, float, str, Decimal)):
                self.asking_price = quantize_money_decimal(self.asking_price, cur)
        # Jurisdiction from linked Event.venue country only (not artist).
        country = 'IL'
        if self.event_id:
            try:
                ev = getattr(self, 'event', None)
                if ev is not None and getattr(ev, 'pk', None) == self.event_id and getattr(ev, 'country', None):
                    country = (ev.country or 'IL').upper()
                else:
                    country = (
                        Event.objects.filter(pk=self.event_id).values_list('country', flat=True).first() or 'IL'
                    )
                    country = (country or 'IL').upper()
            except Exception:
                country = 'IL'
        if self.venue_section_id:
            vs = getattr(self, 'venue_section', None)
            if vs is None:
                vs = VenueSection.objects.filter(pk=self.venue_section_id).first()
            if vs is not None:
                self.section_legacy = (vs.name or '')[:100]
        elif (self.custom_section_text or '').strip():
            self.section_legacy = (self.custom_section_text or '')[:100]
        if self.asking_price is None and self.original_price is not None:
            self.asking_price = self.original_price
        # IL anti-scalping: never persist asking above face (serializer should already enforce).
        elif country == 'IL' and self.original_price is not None and self.asking_price is not None:
            if self.asking_price > self.original_price:
                self.asking_price = self.original_price
        super().save(*args, **kwargs)
    
    # PDF file (raw storage on Cloudinary — see _ticket_pdf_storage / settings.STORAGES)
    pdf_file = models.FileField(
        upload_to=ticket_pdf_upload_to,
        storage=_ticket_pdf_storage(),
        help_text="Upload the PDF ticket file (can contain multiple tickets)",
    )
    
    receipt_file = models.FileField(
        upload_to=ticket_receipt_upload_to,
        storage=_ticket_receipt_storage(),
        blank=True,
        null=True,
        help_text='Optional proof of purchase / receipt file',
    )
    
    # Seating information
    is_together = models.BooleanField(default=True, help_text="Are the seats together (next to each other)?")
    available_quantity = models.IntegerField(default=1, help_text="Number of tickets available for sale (1-10)")
    
    # Delivery method
    DELIVERY_CHOICES = [
        ('instant', 'Instant Download'),
        ('mobile', 'Mobile Transfer'),
        ('physical', 'Physical'),
    ]
    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default='instant',
        help_text="How the ticket will be delivered to buyer"
    )
    
    # Ticket type and verification
    TICKET_TYPE_CHOICES = [
        ('כרטיס אלקטרוני / PDF', 'כרטיס אלקטרוני / PDF'),
        ('כרטיס אלקטרוני (PDF או תמונה)', 'כרטיס אלקטרוני (PDF או תמונה)'),
        ('העברה באפליקציה', 'העברה באפליקציה'),
        ('כרטיס נייר פיזי', 'כרטיס נייר פיזי'),
    ]
    ticket_type = models.CharField(
        max_length=50,
        choices=TICKET_TYPE_CHOICES,
        default='כרטיס אלקטרוני (PDF או תמונה)',
        help_text="Type of ticket"
    )
    
    VERIFICATION_STATUS_CHOICES = [
        ('ממתין לאישור', 'ממתין לאישור'),
        ('מאומת', 'מאומת'),
        ('נדחה', 'נדחה'),
    ]
    verification_status = models.CharField(
        max_length=50,
        choices=VERIFICATION_STATUS_CHOICES,
        default='ממתין לאישור',
        help_text="Ticket verification status (admin approval required)"
    )
    
    # View quality and split options
    is_obstructed_view = models.BooleanField(
        default=False,
        help_text="Does this ticket have an obstructed view? (Important for buyer trust)"
    )
    
    SPLIT_TYPE_CHOICES = [
        ('כל כמות', 'כל כמות'),
        ('זוגות בלבד', 'זוגות בלבד'),
        ('מכור הכל יחד', 'מכור הכל יחד'),
    ]
    split_type = models.CharField(
        max_length=50,
        choices=SPLIT_TYPE_CHOICES,
        default='כל כמות',
        help_text="How tickets can be split/sold"
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_approval')
    
    # Reservation fields
    reserved_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when ticket was reserved")
    reserved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reserved_tickets',
        help_text="User who reserved this ticket (null for guest reservations)"
    )
    reservation_email = models.EmailField(null=True, blank=True, help_text="Email of guest who reserved (if not logged in)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        try:
            ev = getattr(self, 'event', None)
            event_name = ev.name if ev else (self.event_name or 'Unknown Event')
            seller = getattr(self, 'seller', None)
            if seller is None:
                seller_name = '?'
            elif hasattr(seller, 'get_username'):
                seller_name = seller.get_username() or str(seller.pk)
            else:
                seller_name = str(getattr(seller, 'username', '')) or str(seller.pk)
            return f'{event_name} - {seller_name} (₪{self.asking_price})'
        except Exception:
            return f'Ticket #{getattr(self, "pk", "") or "—"}'
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['seller', 'status']),
        ]


class Order(models.Model):
    """
    Order model supporting both registered users and guest checkout
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('pending_payment', 'Pending payment'),
        ('paid', 'Paid'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Optional user field for registered users
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='orders'
    )
    
    # Link to ticket
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )
    
    # Guest checkout fields
    guest_email = models.EmailField(blank=True, null=True)
    guest_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Order details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        default='ILS',
        help_text='ISO 4217; matches Event.country at listing time',
    )
    quantity = models.IntegerField(default=1, help_text="Number of tickets purchased in this order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Event name (can be derived from ticket, but kept for guest orders)
    event_name = models.CharField(max_length=255, blank=True)
    
    # Multi-ticket support: list of ticket IDs for download (when quantity > 1)
    ticket_ids = models.JSONField(default=list, blank=True, help_text='List of ticket IDs in this order')

    # Price integrity (negotiated vs list; buyer total; seller net)
    related_offer = models.ForeignKey(
        'Offer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        help_text='Accepted offer this order fulfilled, if any',
    )
    final_negotiated_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Seller bundle price: offer amount if negotiated, else asking × quantity',
    )
    buyer_service_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='15% buyer-side service fee (added on top of final_negotiated_price)',
    )
    seller_service_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='0% seller-side platform fee — sellers keep 100% of their asking price',
    )
    total_paid_by_buyer = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Total charged to buyer (mirrors total_amount when set)',
    )
    net_seller_revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Amount seller receives after seller_service_fee (currently 0%) on final_negotiated_price',
    )

    # Escrow / seller payout (funds held until after event + 36h)
    PAYOUT_STATUS_CHOICES = [
        ('locked', 'Locked'),
        ('eligible', 'Eligible'),
        ('paid', 'Paid'),
    ]
    payout_status = models.CharField(
        max_length=20,
        choices=PAYOUT_STATUS_CHOICES,
        default='locked',
        help_text='Escrow lifecycle: locked -> eligible (after event+36h) -> paid',
    )
    payout_eligible_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When seller payout becomes eligible (36 hours after event)',
    )

    # Single-row multi-qty: inventory held on the ticket row until payment confirms or order expires
    held_ticket = models.ForeignKey(
        'Ticket',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_payment_holds',
        help_text='Ticket row with decremented available_quantity while order is pending_payment',
    )
    held_quantity = models.PositiveIntegerField(
        default=0,
        help_text='Quantity subtracted from held_ticket.available_quantity for this pending order',
    )
    pending_offer = models.ForeignKey(
        'Offer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_orders',
        help_text='Negotiated offer associated with this checkout before payment confirms',
    )
    # One-time secret returned with the pending order so the client can call confirm-payment
    # without a global webhook secret (cleared when the order becomes paid).
    payment_confirm_token = models.CharField(max_length=64, blank=True, null=True)

    payme_transaction_id = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        help_text='Payme gateway transaction / sale id',
    )
    payme_status = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text='Last known Payme payment status (webhook / API)',
    )

    def covers_ticket(self, ticket_id):
        """True if this order includes the given ticket (FK or JSON list; int/str safe)."""
        if ticket_id is None:
            return False
        if self.ticket_id is not None:
            try:
                if int(self.ticket_id) == int(ticket_id):
                    return True
            except (TypeError, ValueError):
                if str(self.ticket_id) == str(ticket_id):
                    return True
        for x in (self.ticket_ids or []):
            try:
                if int(x) == int(ticket_id):
                    return True
            except (TypeError, ValueError):
                if str(x) == str(ticket_id):
                    return True
        return False
    
    def __str__(self):
        if self.user:
            return f"Order {self.id} - {self.user.username}"
        else:
            return f"Order {self.id} - Guest ({self.guest_email})"
    
    class Meta:
        ordering = ['-created_at']


class SellerPayout(models.Model):
    """
    Financial ledger: one row per paid order — platform fee vs seller net payout.
    """

    class PayoutStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        TRANSFERRED = 'transferred', 'Transferred'
        CANCELLED = 'cancelled', 'Cancelled'

    PLATFORM_FEE_RATE = Decimal('0.15')

    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name='seller_payout',
    )
    seller = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='seller_payouts',
    )
    total_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Total amount the buyer paid via PayMe',
    )
    platform_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='TradeTix platform fee (buyer Security Fee plus any seller-side fee)',
    )
    net_payout = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Amount owed to the seller after seller-side fees',
    )
    payout_status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    transferred_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the net payout was transferred to the seller',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payout_status', '-created_at']),
            models.Index(fields=['seller', 'payout_status']),
        ]
        verbose_name = 'Seller payout'
        verbose_name_plural = 'Seller payouts'

    def __str__(self):
        return (
            f'SellerPayout #{self.pk} order={self.order_id} seller={self.seller_id} '
            f'{self.payout_status} net={self.net_payout}'
        )

    @classmethod
    def compute_amounts(cls, total_paid: Decimal) -> tuple[Decimal, Decimal, Decimal]:
        """Legacy fallback: return (total_paid, platform_fee, net_payout) from gross amount."""
        total = Decimal(total_paid).quantize(Decimal('0.01'))
        fee = (total * cls.PLATFORM_FEE_RATE).quantize(Decimal('0.01'))
        net = (total - fee).quantize(Decimal('0.01'))
        return total, fee, net

    @classmethod
    def total_pending_for_seller(cls, seller) -> Decimal:
        """Sum of net_payout still owed to this seller (pending status only)."""
        from django.db.models import Sum

        total = (
            cls.objects.filter(seller=seller, payout_status=cls.PayoutStatus.PENDING)
            .aggregate(sum=Sum('net_payout'))
            .get('sum')
        )
        return Decimal(total or 0).quantize(Decimal('0.01'))

    @classmethod
    def total_pending_for_seller_id(cls, seller_id: int) -> Decimal:
        from django.db.models import Sum

        total = (
            cls.objects.filter(seller_id=seller_id, payout_status=cls.PayoutStatus.PENDING)
            .aggregate(sum=Sum('net_payout'))
            .get('sum')
        )
        return Decimal(total or 0).quantize(Decimal('0.01'))

    @classmethod
    def pending_for_seller(cls, seller):
        """All pending payout rows for a seller (for admin / reporting)."""
        return cls.objects.filter(seller=seller, payout_status=cls.PayoutStatus.PENDING)

    def save(self, *args, **kwargs):
        if self.total_paid is not None and (self.platform_fee is None or self.net_payout is None):
            _, fee, net = self.compute_amounts(self.total_paid)
            self.platform_fee = fee
            self.net_payout = net
        if self.payout_status == self.PayoutStatus.TRANSFERRED and not self.transferred_at:
            self.transferred_at = timezone.now()
        super().save(*args, **kwargs)

    def clean(self):
        if self.net_payout is not None and self.net_payout < 0:
            raise ValidationError({'net_payout': 'Net payout cannot be negative.'})


# Backward-compatible alias (deprecated — use SellerPayout)
Payout = SellerPayout


class TicketAlert(models.Model):
    """
    Waitlist/Alert: notify when tickets become available for an event or any future show by an artist.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ticket_alerts',
        null=True,
        blank=True,
        help_text='Registered user (optional — guests use email only)',
    )
    artist = models.ForeignKey(
        'Artist',
        on_delete=models.CASCADE,
        related_name='ticket_alerts',
        null=True,
        blank=True,
        help_text='Subscribe to all future shows for this artist',
    )
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='alerts',
        null=True,
        blank=True,
        help_text='Subscribe to a specific event',
    )
    email = models.EmailField(help_text="Email address to notify when tickets become available")
    phone = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='Optional phone for SMS / WhatsApp follow-up',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False, help_text="Whether this alert has been sent")
    notified_at = models.DateTimeField(null=True, blank=True, help_text="When the notification was sent")

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'email'],
                condition=models.Q(event__isnull=False),
                name='unique_ticket_alert_event_email',
            ),
            models.UniqueConstraint(
                fields=['artist', 'email'],
                condition=models.Q(artist__isnull=False, event__isnull=True),
                name='unique_ticket_alert_artist_email',
            ),
        ]
        indexes = [
            models.Index(fields=['event', 'notified']),
            models.Index(fields=['artist', 'notified']),
        ]

    def clean(self):
        if not self.event_id and not self.artist_id:
            raise ValidationError('TicketAlert requires event or artist.')
        if self.event_id and self.artist_id:
            raise ValidationError('TicketAlert cannot target both event and artist.')

    def __str__(self):
        if self.event_id:
            return f"Alert for {self.event.name} - {self.email}"
        if self.artist_id:
            return f"Alert for artist {self.artist.name} - {self.email}"
        return f"Alert - {self.email}"


class Offer(models.Model):
    """
    Bid/Ask Negotiation System - Offers from buyers to sellers
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('countered', 'Countered'),
        ('expired', 'Expired'),
    ]
    
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='offers_sent',
        help_text="The buyer making the offer"
    )
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='offers',
        help_text="The ticket being offered on"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="The offer amount (bid price)"
    )
    currency = models.CharField(
        max_length=3,
        default='ILS',
        help_text='ISO 4217; locked to listing/event — no mixed-currency negotiation',
    )
    offer_round_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="0=initial buyer offer, 1=seller counter, 2=buyer counter (max)"
    )
    parent_offer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='counter_offers',
        help_text="The previous offer in this negotiation chain"
    )
    quantity = models.IntegerField(
        default=1,
        help_text="Number of tickets in this offer"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the offer"
    )
    expires_at = models.DateTimeField(
        help_text="When the offer expires (48 hours from creation)"
    )
    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the offer was accepted"
    )
    checkout_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the checkout window expires (24 hours after acceptance)"
    )
    counter_offer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='original_offer',
        help_text="If this is a counter-offer, link to the original offer"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        from .currency import quantize_money_decimal
        if self.amount is not None:
            cur = getattr(self, 'currency', None) or 'ILS'
            self.amount = quantize_money_decimal(self.amount, cur)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Offer #{self.id}: {self.buyer.username} → {self.ticket.seller.username} - {self.amount} {self.currency} ({self.status})"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['ticket', 'status']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['checkout_expires_at']),
        ]


class EventRequest(models.Model):
    """
    Seller request to add a missing event/artist to the catalog (growth / ops queue).

    Must stay defined here: users.admin, serializers, and views import EventRequest from this module.
    Migration: users.0030_eventrequest.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='event_requests',
    )
    submitted_email = models.EmailField(blank=True, help_text='Email at time of submission')
    event_hint = models.CharField(
        max_length=400,
        blank=True,
        help_text='Artist, teams, or event name',
    )
    details = models.TextField(help_text='Date, venue, category, or other context')
    category = models.CharField(max_length=50, blank=True, help_text='Sell flow category (e.g. concert, sport)')
    created_at = models.DateTimeField(auto_now_add=True)
    is_handled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        hint = (self.event_hint or '')[:60]
        return f'Event request #{self.id} — {self.user.username}: {hint}'


class ContactMessage(models.Model):
    """
    Customer service contact messages from users
    """
    name = models.CharField(max_length=255, help_text="Contact name")
    email = models.EmailField(help_text="Contact email")
    order_number = models.CharField(max_length=100, blank=True, null=True, help_text="Optional order number reference")
    message = models.TextField(help_text="Message content")
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False, help_text="Whether this message has been resolved")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_resolved', '-created_at']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"Contact from {self.name} ({self.email}) - {self.created_at.strftime('%Y-%m-%d')}"


class AnalyticsEvent(models.Model):
    """
    Lightweight funnel / traffic event store. No external dependencies.
    One row per user action; designed to stay small — purge rows older than 90 days periodically.
    """
    EVENT_TYPE_CHOICES = [
        ('page_view', 'Page View'),
        ('checkout_start', 'Checkout Start'),
        ('checkout_complete', 'Purchase Complete'),
        ('offer_submitted', 'Offer Submitted'),
        ('ticket_viewed', 'Ticket Viewed'),
    ]

    session_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text='Anonymous browser session UUID (localStorage); no PII.',
    )
    path = models.CharField(max_length=500, help_text='URL path, e.g. /events/12')
    event_type = models.CharField(
        max_length=30,
        choices=EVENT_TYPE_CHOICES,
        db_index=True,
    )
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Optional extra context (event_id, ticket_id, etc.).',
    )
    ip_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text='First 32 chars of SHA-256(client IP) — allows unique-visitor counts without storing raw PII.',
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='analytics_events',
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'event_type']),
            models.Index(fields=['session_id', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.event_type} {self.path} @ {self.timestamp:%Y-%m-%d %H:%M}'
