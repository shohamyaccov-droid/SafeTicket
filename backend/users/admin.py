from decimal import Decimal

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from datetime import timedelta
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import User, Order, Ticket, Event, Artist, Offer, ContactMessage, EventRequest
from .admin_pdf_url import get_ticket_pdf_admin_url


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'phone_number', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    
    # Properly handle fieldsets for Django 6.0 compatibility
    fieldsets = list(BaseUserAdmin.fieldsets) + [
        ('Additional Info', {'fields': ('role', 'phone_number', 'profile_image')}),
    ]
    
    # Properly handle add_fieldsets for Django 6.0 compatibility  
    add_fieldsets = list(BaseUserAdmin.add_fieldsets) + [
        ('Additional Info', {'fields': ('role', 'phone_number', 'profile_image')}),
    ]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'event_name',
        'seller',
        'risk_level',
        'verification_status',
        'ticket_type',
        'original_price',
        'status',
        'pdf_staff_link',
        'reservation_info',
        'created_at',
    ]
    list_filter = ['verification_status', 'ticket_type', 'status', 'split_type', 'is_obstructed_view', 'created_at', 'event_date']
    search_fields = ['event_name', 'seller__username', 'venue', 'section', 'row']
    readonly_fields = ['created_at', 'updated_at', 'asking_price']
    actions = [
        'approve_and_activate_selected',
        'force_release_expired_reservations',
        'force_release_all_reserved',
    ]
    fieldsets = (
        ('Event & Seller Information', {
            'fields': ('event', 'seller', 'event_name', 'event_date', 'venue')
        }),
        ('Ticket Details', {
            'fields': ('ticket_type', 'verification_status', 'pdf_file', 'delivery_method')
        }),
        ('Seating Information', {
            'fields': ('section', 'row', 'seat_numbers', 'row_number', 'seat_number', 'seat_row', 'is_obstructed_view', 'is_together')
        }),
        ('Pricing', {
            'fields': ('original_price', 'asking_price'),
            'description': 'Asking price is automatically set to match original_price per Israeli Consumer Protection Law.'
        }),
        ('Quantity & Split Options', {
            'fields': ('available_quantity', 'split_type')
        }),
        ('Status & Reservations', {
            'fields': ('status', 'reserved_at', 'reserved_by', 'reservation_email')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.pk:
            ro += [
                'seller',
                'event',
                'original_price',
                'pdf_file_display',
                'pdf_inline_preview',
            ]
        return ro

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.fieldsets
        out = []
        for title, options in self.fieldsets:
            row = []
            for name in options.get('fields', ()):
                if name == 'pdf_file':
                    row.extend(['pdf_file_display', 'pdf_inline_preview'])
                else:
                    row.append(name)
            out.append((title, {**options, 'fields': tuple(row)}))
        return tuple(out)

    def risk_level(self, obj):
        if not obj.seller_id:
            return format_html('<span style="color:#64748b;">—</span>')
        try:
            seller = obj.seller
        except ObjectDoesNotExist:
            return format_html('<span style="color:#64748b;">—</span>')
        fresh_cutoff = timezone.now() - timedelta(hours=48)
        price_high = (obj.original_price or Decimal('0')) > Decimal('1000')
        seller_new = seller.date_joined > fresh_cutoff
        if price_high or seller_new:
            return format_html(
                '<span style="color:#b91c1c;font-weight:700;" title="מחיר &gt; 1000 ₪ או מוכר חדש (&lt; 48 שעות)">אדום · High Risk</span>'
            )
        return format_html('<span style="color:#15803d;font-weight:600;">ירוק · Normal</span>')

    risk_level.short_description = 'רמת סיכון / Risk Level'

    def pdf_staff_link(self, obj):
        try:
            url = get_ticket_pdf_admin_url(obj)
        except Exception:
            return '—'
        if not url:
            return '—'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">PDF</a>',
            url,
        )

    pdf_staff_link.short_description = 'PDF (סטאף)'

    def pdf_file_display(self, obj):
        try:
            url = get_ticket_pdf_admin_url(obj)
        except Exception:
            return format_html('<span style="color:#64748b;">אין קובץ</span>')
        if not url:
            return format_html('<span style="color:#64748b;">אין קובץ</span>')
        return format_html(
            '<a class="button" style="padding:8px 12px;display:inline-block;margin-top:4px;" '
            'href="{}" target="_blank" rel="noopener noreferrer">פתיחה / הורדת PDF (קישור חתום לסטאף)</a>',
            url,
        )

    pdf_file_display.short_description = 'קובץ PDF (גישת מנהל)'

    def pdf_inline_preview(self, obj):
        try:
            url = get_ticket_pdf_admin_url(obj)
        except Exception:
            return '—'
        if not url:
            return '—'
        return format_html(
            '<iframe src="{}" title="PDF preview" '
            'style="width:100%%;max-width:720px;height:480px;border:1px solid #cbd5e1;'
            'border-radius:6px;background:#f1f5f9;"></iframe>'
            '<p style="color:#64748b;font-size:12px;margin-top:8px;max-width:720px;">'
            'אם המסך ריק, פתחו את הקישור למעלה — חלק מהדפדפנים חוסמים תצוגת PDF בתוך מסגרת.</p>',
            url,
        )

    pdf_inline_preview.short_description = 'תצוגה מקדימה'

    @admin.action(description='Approve & Activate Selected Tickets (אישור והפעלת כרטיסים)')
    def approve_and_activate_selected(self, request, queryset):
        updated = queryset.update(verification_status='מאומת', status='active')
        self.message_user(
            request,
            f'אושרו והופעלו {updated} כרטיסים · Approved and activated {updated} ticket(s).',
        )
    
    def reservation_info(self, obj):
        """Display reservation information in admin list"""
        if obj.status == 'reserved' and obj.reserved_at:
            time_remaining = (obj.reserved_at + timedelta(minutes=10)) - timezone.now()
            if time_remaining.total_seconds() > 0:
                minutes = int(time_remaining.total_seconds() / 60)
                try:
                    rb = obj.reserved_by
                    reserved_by = rb.username if rb else (obj.reservation_email or 'Guest')
                except ObjectDoesNotExist:
                    reserved_by = obj.reservation_email or 'Guest'
                return format_html(
                    '<span style="color: orange;">Reserved by {}<br/>{} min remaining</span>',
                    reserved_by,
                    minutes
                )
            else:
                return mark_safe('<span style="color: red;">EXPIRED</span>')
        return '-'
    reservation_info.short_description = 'Reservation Info'
    
    @admin.action(description='Force Release Expired Reservations')
    def force_release_expired_reservations(self, request, queryset):
        """
        Admin action to force release all expired reservations immediately
        """
        import logging
        logger = logging.getLogger(__name__)
        
        expired_reservations = Ticket.objects.filter(
            status='reserved',
            reserved_at__lt=timezone.now() - timedelta(minutes=10)
        )
        
        count = expired_reservations.count()
        
        if count > 0:
            ticket_ids = list(expired_reservations.values_list('id', flat=True))
            logger.info(f'Admin {request.user.username} force-released {count} expired reservation(s) for tickets: {ticket_ids}')
            
            expired_reservations.update(
                status='active',
                reserved_at=None,
                reserved_by=None,
                reservation_email=None
            )
            
            self.message_user(request, f'Successfully released {count} expired reservation(s).')
        else:
            self.message_user(request, 'No expired reservations found.')
    
    @admin.action(description='Force Release ALL Reserved Tickets')
    def force_release_all_reserved(self, request, queryset):
        """
        Admin action to force release ALL reserved tickets (regardless of expiry)
        Use this as a one-time fix to clear stuck reservations
        """
        import logging
        logger = logging.getLogger(__name__)
        
        all_reserved = Ticket.objects.filter(status='reserved')
        count = all_reserved.count()
        
        if count > 0:
            ticket_ids = list(all_reserved.values_list('id', flat=True))
            logger.info(f'Admin {request.user.username} force-released ALL {count} reserved ticket(s): {ticket_ids}')
            
            all_reserved.update(
                status='active',
                reserved_at=None,
                reserved_by=None,
                reservation_email=None
            )
            
            self.message_user(request, f'Successfully released ALL {count} reserved ticket(s).')
        else:
            self.message_user(request, 'No reserved tickets found.')
    
    force_release_expired_reservations.short_description = 'Force Release Expired Reservations'
    force_release_all_reserved.short_description = 'Force Release ALL Reserved Tickets'


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ['name', 'genre', 'created_at']
    list_filter = ['genre', 'created_at']
    search_fields = ['name', 'description', 'genre']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'genre', 'description')
        }),
        ('Media & Images', {
            'fields': ('image', 'cover_image')
        }),
        ('Social Links', {
            'fields': ('youtube_link', 'spotify_link')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'artist', 'category', 'home_team', 'away_team', 'status', 'date', 'venue', 'city', 'created_at']
    list_filter = ['artist', 'category', 'status', 'venue', 'city', 'age_restriction', 'date', 'created_at']
    search_fields = ['name', 'venue', 'city', 'artist__name', 'home_team', 'away_team', 'tournament']
    readonly_fields = ['created_at', 'updated_at', 'view_count']
    fieldsets = (
        ('Basic Information', {
            'fields': ('artist', 'name', 'category', 'status')
        }),
        ('Location & Timing', {
            'fields': ('venue', 'city', 'date', 'doors_open')
        }),
        ('Event Details', {
            'fields': ('age_restriction', 'image', 'view_count')
        }),
        ('Sports Data', {
            'fields': ('home_team', 'away_team', 'tournament'),
            'classes': ('collapse',),
            'description': 'Optional fields for sports events only'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'guest_email', 'status', 'total_amount', 'event_name', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'guest_email', 'event_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ['id', 'buyer', 'ticket', 'amount', 'status', 'expires_at', 'accepted_at', 'created_at']
    list_filter = ['status', 'created_at', 'expires_at']
    search_fields = ['buyer__username', 'ticket__event_name', 'ticket__seller__username']
    readonly_fields = ['created_at', 'updated_at', 'expires_at', 'accepted_at', 'checkout_expires_at']
    fieldsets = (
        ('Offer Information', {
            'fields': ('buyer', 'ticket', 'amount', 'status')
        }),
        ('Timing', {
            'fields': ('expires_at', 'accepted_at', 'checkout_expires_at')
        }),
        ('Counter Offer', {
            'fields': ('counter_offer',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EventRequest)
class EventRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'event_hint', 'category', 'submitted_email', 'created_at', 'is_handled']
    list_filter = ['is_handled', 'category', 'created_at']
    search_fields = ['event_hint', 'details', 'user__username', 'submitted_email']
    readonly_fields = ['user', 'submitted_email', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'created_at', 'is_resolved']
    list_filter = ['is_resolved', 'created_at']
    search_fields = ['name', 'email', 'order_number', 'message']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'email', 'order_number')
        }),
        ('Message', {
            'fields': ('message',)
        }),
        ('Status', {
            'fields': ('is_resolved',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
