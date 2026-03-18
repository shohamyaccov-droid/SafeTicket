from django.contrib.auth.models import AbstractUser
from django.db import models


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
    name = models.CharField(max_length=255, help_text="Artist name")
    image = models.ImageField(upload_to='artists/images/', blank=True, null=True, help_text="Artist image/photo")
    description = models.TextField(blank=True, null=True, help_text="Artist description")
    genre = models.CharField(max_length=100, blank=True, null=True, help_text="Genre (e.g., Pop, Rock, Sports)")
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


class Event(models.Model):
    """
    Centralized Event model for grouping tickets
    """
    VENUE_CHOICES = [
        ('מנורה מבטחים', 'מנורה מבטחים'),
        ('בלומפילד', 'בלומפילד'),
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
        default='מנורה מבטחים',
        help_text="Venue name"
    )
    city = models.CharField(max_length=100, help_text="City where event takes place")
    image = models.ImageField(upload_to='events/images/', blank=True, null=True, help_text="Event image/photo")
    view_count = models.IntegerField(default=0, help_text="Number of times this event page has been viewed (for popularity tracking)")
    
    # Event categorization and status
    CATEGORY_CHOICES = [
        ('concert', 'הופעות'),
        ('sport', 'משחקי ספורט'),
        ('theater', 'הצגות תיאטרון'),
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
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        # For sports events with teams, show team matchup
        if self.category == 'sport' or self.category == 'ספורט':
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
        ('pending_verification', 'Pending Verification'),
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
    
    # Detailed seating information
    section = models.CharField(max_length=100, blank=True, null=True, help_text="Section/Block/Gate (e.g., Gate 11)")
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
    
    def save(self, *args, **kwargs):
        # Enforce Israeli law: asking_price must always equal original_price
        # Ensure prices are properly rounded to 2 decimal places
        from decimal import Decimal, ROUND_HALF_UP
        if self.original_price is not None:
            # Convert to Decimal and round to 2 decimal places to prevent floating point errors
            if isinstance(self.original_price, (int, float, str)):
                self.original_price = Decimal(str(self.original_price)).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )
            # Set asking_price to exactly match original_price (no deductions)
            self.asking_price = self.original_price
        super().save(*args, **kwargs)
    
    # PDF file
    pdf_file = models.FileField(upload_to='tickets/pdfs/', help_text="Upload the PDF ticket file (can contain multiple tickets)")
    
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
        ('העברה באפליקציה', 'העברה באפליקציה'),
        ('כרטיס נייר פיזי', 'כרטיס נייר פיזי'),
    ]
    ticket_type = models.CharField(
        max_length=50,
        choices=TICKET_TYPE_CHOICES,
        default='כרטיס אלקטרוני / PDF',
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_verification')
    
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
        event_name = self.event.name if self.event else (self.event_name or 'Unknown Event')
        return f"{event_name} - {self.seller.username} (₪{self.asking_price})"
    
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
    quantity = models.IntegerField(default=1, help_text="Number of tickets purchased in this order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Event name (can be derived from ticket, but kept for guest orders)
    event_name = models.CharField(max_length=255, blank=True)
    
    # Multi-ticket support: list of ticket IDs for download (when quantity > 1)
    ticket_ids = models.JSONField(default=list, blank=True, help_text='List of ticket IDs in this order')
    
    def __str__(self):
        if self.user:
            return f"Order {self.id} - {self.user.username}"
        else:
            return f"Order {self.id} - Guest ({self.guest_email})"
    
    class Meta:
        ordering = ['-created_at']


class TicketAlert(models.Model):
    """
    Waitlist/Alert model for users to get notified when tickets become available for an event
    """
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='alerts',
        help_text="The event to be notified about"
    )
    email = models.EmailField(help_text="Email address to notify when tickets become available")
    created_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False, help_text="Whether this alert has been sent")
    notified_at = models.DateTimeField(null=True, blank=True, help_text="When the notification was sent")
    
    class Meta:
        ordering = ['-created_at']
        unique_together = [['event', 'email']]  # Prevent duplicate alerts for same event+email
        indexes = [
            models.Index(fields=['event', 'notified']),
        ]
    
    def __str__(self):
        return f"Alert for {self.event.name} - {self.email}"


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
        help_text="When the checkout window expires (4 hours after acceptance)"
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
    
    def __str__(self):
        return f"Offer #{self.id}: {self.buyer.username} → {self.ticket.seller.username} - ₪{self.amount} ({self.status})"
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['ticket', 'status']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['checkout_expires_at']),
        ]


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
