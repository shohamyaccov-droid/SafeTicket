import logging
from decimal import Decimal
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import User, Order, Ticket, Event, Artist, Offer, ContactMessage, EventRequest
from .admin_pdf_url import get_ticket_pdf_admin_url

_admin_log = logging.getLogger(__name__)


def _admin_pdf_safe_fallback():
    """Non-throwing HTML for admin when PDF URL/preview cannot be built or delivered."""
    return mark_safe('<span style="color:red;">File Error / Missing</span>')


def _admin_missing_media_message():
    try:
        return format_html(
            '<div style="padding:12px;border:1px solid #fecaca;background:#fef2f2;border-radius:8px;'
            'max-width:720px;color:#991b1b;line-height:1.45;">'
            '<strong>File not found or corrupted.</strong> '
            'The stored path may reference a file that no longer exists (for example legacy uploads on '
            'ephemeral disk before Cloudinary), or Cloudinary cannot deliver this asset (401/404).'
            '</div>'
        )
    except Exception as exc:
        _admin_log.warning('_admin_missing_media_message failed: %s', exc, exc_info=True)
        return _admin_pdf_safe_fallback()


def _admin_image_preview_html(fieldfile):
    """Signed Cloudinary URL or local storage; show missing banner if unreachable."""
    try:
        from django.conf import settings
        from users.serializers import resolved_image_url

        if not fieldfile:
            return format_html('<span style="color:#64748b;">אין קובץ</span>')
        if getattr(settings, 'USE_CLOUDINARY', False):
            url = resolved_image_url(None, fieldfile)
            if not url:
                return _admin_missing_media_message()
            return format_html(
                '<img src="{}" style="max-height:220px;border-radius:8px;border:1px solid #e2e8f0;" alt="" />',
                url,
            )
        try:
            if not fieldfile.storage.exists(fieldfile.name):
                return _admin_missing_media_message()
        except Exception:
            return _admin_missing_media_message()
        try:
            src = fieldfile.url
        except Exception:
            return _admin_missing_media_message()
        return format_html(
            '<img src="{}" style="max-height:220px;border-radius:8px;border:1px solid #e2e8f0;" alt="" />',
            src,
        )
    except Exception as exc:
        _admin_log.exception('_admin_image_preview_html failed: %s', exc)
        return _admin_pdf_safe_fallback()


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
        'event_name_display',
        'seller_display',
        'risk_level',
        'verification_status',
        'ticket_type',
        'original_price',
        'status',
        'pdf_staff_link',
        'receipt_staff_link',
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
            'fields': ('ticket_type', 'verification_status', 'pdf_file', 'receipt_file', 'delivery_method')
        }),
        ('Seating Information', {
            'fields': ('section', 'row', 'seat_numbers', 'row_number', 'seat_number', 'seat_row', 'is_obstructed_view', 'is_together')
        }),
        ('Pricing', {
            'fields': ('original_price', 'asking_price'),
            'description': 'For IL events, asking_price must not exceed face value (original_price). Proof of purchase is stored in receipt_file.'
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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        try:
            return qs.select_related('seller', 'event', 'reserved_by')
        except Exception as exc:
            _admin_log.warning('TicketAdmin.get_queryset select_related failed: %s', exc)
            return qs

    def event_name_display(self, obj):
        try:
            name = getattr(obj, 'event_name', None) or ''
            name = str(name).strip()
            return (name[:120] + '…') if len(name) > 120 else (name or '—')
        except Exception as exc:
            _admin_log.warning('TicketAdmin.event_name_display failed pk=%s: %s', getattr(obj, 'pk', None), exc)
            return '—'

    event_name_display.short_description = 'Event name'
    event_name_display.admin_order_field = 'event_name'

    def seller_display(self, obj):
        try:
            if not getattr(obj, 'seller_id', None):
                return '—'
            u = obj.seller
            if u is None:
                return '—'
            return u.get_username() or str(u.pk)
        except Exception as exc:
            _admin_log.warning('TicketAdmin.seller_display failed pk=%s: %s', getattr(obj, 'pk', None), exc)
            return '—'

    seller_display.short_description = 'Seller'
    seller_display.admin_order_field = 'seller__username'

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
        try:
            if not getattr(obj, 'seller_id', None):
                return '—'
            try:
                seller = obj.seller
            except ObjectDoesNotExist:
                return '—'
            if seller is None:
                return '—'
            fresh_cutoff = timezone.now() - timedelta(hours=48)
            op = getattr(obj, 'original_price', None)
            if op is None:
                op = Decimal('0')
            else:
                op = Decimal(str(op))
            price_high = op > Decimal('1000')
            dj = getattr(seller, 'date_joined', None)
            if dj is None:
                seller_new = False
            else:
                seller_new = dj > fresh_cutoff
            if price_high or seller_new:
                return mark_safe(
                    '<span style="color:#b91c1c;font-weight:700;" title="מחיר &gt; 1000 ₪ או מוכר חדש (&lt; 48 שעות)">אדום · High Risk</span>'
                )
            return mark_safe('<span style="color:#15803d;font-weight:600;">ירוק · Normal</span>')
        except Exception as exc:
            _admin_log.warning('TicketAdmin.risk_level failed pk=%s: %s', getattr(obj, 'pk', None), exc)
            return '—'

    risk_level.short_description = 'רמת סיכון / Risk Level'

    def pdf_staff_link(self, obj):
        try:
            pdf = getattr(obj, 'pdf_file', None)
            if not pdf or not str(getattr(pdf, 'name', None) or '').strip():
                return _admin_pdf_safe_fallback()
            url = get_ticket_pdf_admin_url(obj)
            if not url:
                return _admin_pdf_safe_fallback()
            try:
                return format_html(
                    '<a href="{}" target="_blank" rel="noopener noreferrer">PDF</a>',
                    url,
                )
            except Exception as fmt_exc:
                _admin_log.warning(
                    'TicketAdmin.pdf_staff_link format_html failed pk=%s: %s',
                    getattr(obj, 'pk', None),
                    fmt_exc,
                    exc_info=True,
                )
                return _admin_pdf_safe_fallback()
        except Exception:
            _admin_log.exception('TicketAdmin.pdf_staff_link failed pk=%s', getattr(obj, 'pk', None))
            return _admin_pdf_safe_fallback()

    pdf_staff_link.short_description = 'PDF (סטאף)'

    def receipt_staff_link(self, obj):
        try:
            rf = getattr(obj, 'receipt_file', None)
            if not rf or not str(getattr(rf, 'name', None) or '').strip():
                return mark_safe('<span style="color:#64748b;">—</span>')
            try:
                url = rf.url
            except Exception:
                return _admin_pdf_safe_fallback()
            return format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer">קבלה</a>',
                url,
            )
        except Exception:
            _admin_log.exception('TicketAdmin.receipt_staff_link failed pk=%s', getattr(obj, 'pk', None))
            return _admin_pdf_safe_fallback()

    receipt_staff_link.short_description = 'הוכחת קנייה'

    def pdf_file_display(self, obj):
        try:
            pdf = getattr(obj, 'pdf_file', None)
            if not pdf or not str(getattr(pdf, 'name', None) or '').strip():
                return _admin_pdf_safe_fallback()
            url = get_ticket_pdf_admin_url(obj)
            if not url:
                return _admin_pdf_safe_fallback()
            try:
                return format_html(
                    '<a class="button" style="padding:8px 12px;display:inline-block;margin-top:4px;" '
                    'href="{}" target="_blank" rel="noopener noreferrer">פתיחה / הורדת PDF (קישור חתום לסטאף)</a>',
                    url,
                )
            except Exception as fmt_exc:
                _admin_log.warning(
                    'TicketAdmin.pdf_file_display format_html failed pk=%s: %s',
                    getattr(obj, 'pk', None),
                    fmt_exc,
                    exc_info=True,
                )
                return _admin_pdf_safe_fallback()
        except Exception:
            _admin_log.exception('TicketAdmin.pdf_file_display failed pk=%s', getattr(obj, 'pk', None))
            return _admin_pdf_safe_fallback()

    pdf_file_display.short_description = 'קובץ PDF (גישת מנהל)'

    def pdf_inline_preview(self, obj):
        try:
            pdf = getattr(obj, 'pdf_file', None)
            if not pdf or not str(getattr(pdf, 'name', None) or '').strip():
                return _admin_pdf_safe_fallback()
            url = get_ticket_pdf_admin_url(obj)
            if not url:
                return _admin_pdf_safe_fallback()
            try:
                return format_html(
                    '<a href="{}" target="_blank" rel="noopener noreferrer" '
                    'style="display:inline-block;padding:14px 26px;background:linear-gradient(135deg,#0284c7 0%,#0369a1 100%);'
                    'color:#fff!important;font-weight:700;text-decoration:none;border-radius:10px;'
                    'box-shadow:0 3px 10px rgba(3,105,161,0.35);font-size:16px;line-height:1.35;'
                    'border:1px solid #0369a1;">פתח PDF מאובטח בחלון חדש</a>'
                    '<p style="margin-top:12px;color:#475569;font-size:13px;max-width:560px;line-height:1.5;">'
                    'דפדפנים מודרניים חוסמים לעיתים תצוגת PDF בתוך העמוד; פתיחה בלשונית חדשה היא הדרך התקינה לצפייה בסטאף.</p>',
                    url,
                )
            except Exception as fmt_exc:
                _admin_log.warning(
                    'TicketAdmin.pdf_inline_preview format_html failed pk=%s: %s',
                    getattr(obj, 'pk', None),
                    fmt_exc,
                    exc_info=True,
                )
                return _admin_pdf_safe_fallback()
        except Exception:
            _admin_log.exception('TicketAdmin.pdf_inline_preview failed pk=%s', getattr(obj, 'pk', None))
            return _admin_pdf_safe_fallback()

    pdf_inline_preview.short_description = 'PDF (פתיחה בלשונית חדשה)'

    @admin.action(description='Approve & Activate Selected Tickets (אישור והפעלת כרטיסים)')
    def approve_and_activate_selected(self, request, queryset):
        updated = queryset.update(verification_status='מאומת', status='active')
        self.message_user(
            request,
            f'אושרו והופעלו {updated} כרטיסים · Approved and activated {updated} ticket(s).',
        )
    
    def reservation_info(self, obj):
        """Display reservation information in admin list"""
        try:
            if getattr(obj, 'status', None) == 'reserved' and obj.reserved_at:
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
                        minutes,
                    )
                return mark_safe('<span style="color: red;">EXPIRED</span>')
            return '-'
        except Exception as exc:
            _admin_log.warning('TicketAdmin.reservation_info failed pk=%s: %s', getattr(obj, 'pk', None), exc)
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
    readonly_fields = ['created_at', 'updated_at', 'image_delivery_preview', 'cover_image_delivery_preview']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'genre', 'description')
        }),
        ('Media & Images', {
            'fields': ('image', 'cover_image', 'image_delivery_preview', 'cover_image_delivery_preview')
        }),
        ('Social Links', {
            'fields': ('youtube_link', 'spotify_link')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Country', ordering='country')
    def country_display(self, obj):
        return obj.get_country_display() if obj else '—'

    def image_delivery_preview(self, obj):
        return _admin_image_preview_html(getattr(obj, 'image', None))

    image_delivery_preview.short_description = 'Image preview (delivery check)'

    def cover_image_delivery_preview(self, obj):
        return _admin_image_preview_html(getattr(obj, 'cover_image', None))

    cover_image_delivery_preview.short_description = 'Cover preview (delivery check)'


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'artist', 'category', 'home_team', 'away_team', 'status', 'date',
        'venue', 'city', 'country_display', 'created_at',
    ]
    list_filter = ['artist', 'category', 'status', 'venue', 'city', 'country', 'age_restriction', 'date', 'created_at']
    search_fields = ['name', 'venue', 'city', 'artist__name', 'home_team', 'away_team', 'tournament']
    readonly_fields = ['created_at', 'updated_at', 'view_count', 'image_delivery_preview']
    fieldsets = (
        ('Basic Information', {
            'fields': ('artist', 'name', 'category', 'status')
        }),
        ('Location & Timing', {
            'fields': ('venue', 'city', 'country', 'date', 'ends_at', 'doors_open')
        }),
        ('Event Details', {
            'fields': ('age_restriction', 'image', 'image_delivery_preview', 'view_count')
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

    @admin.display(description='Country', ordering='country')
    def country_display(self, obj):
        return obj.get_country_display() if obj else '—'

    def image_delivery_preview(self, obj):
        return _admin_image_preview_html(getattr(obj, 'image', None))

    image_delivery_preview.short_description = 'Image preview (delivery check)'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'guest_email', 'status', 'total_amount', 'currency', 'event_name', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'guest_email', 'event_name']
    readonly_fields = ['created_at', 'updated_at', 'payment_confirm_token']


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ['id', 'buyer', 'ticket', 'amount', 'currency', 'status', 'expires_at', 'accepted_at', 'created_at']
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
