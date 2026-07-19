import logging
from decimal import Decimal
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    AffiliatePartner,
    AnalyticsEvent,
    Artist,
    ContactMessage,
    Coupon,
    CouponRedemption,
    Event,
    EventRequest,
    GlobalFeeSettings,
    Offer,
    Order,
    SellerPayout,
    Ticket,
    User,
    Venue,
    VenueSection,
)
from .admin_pdf_url import get_ticket_pdf_admin_url, get_ticket_receipt_admin_url

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
        (
            'Seller payout (bank transfer)',
            {
                'fields': (
                    'account_holder_name',
                    'bank_name',
                    'branch_number',
                    'account_number',
                    'payout_details',
                ),
                'classes': ('collapse',),
            },
        ),
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
    search_fields = ['event_name', 'seller__username', 'venue', 'section_legacy', 'custom_section_text', 'row']
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
            'fields': (
                'venue_section',
                'custom_section_text',
                'section_legacy',
                'row',
                'seat_numbers',
                'row_number',
                'seat_number',
                'seat_row',
                'is_obstructed_view',
                'is_together',
            )
        }),
        ('Pricing', {
            'fields': ('original_price', 'asking_price'),
            'description': 'For IL events, asking_price must not exceed face value (original_price). Receipt files are optional.'
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
            return qs.select_related('seller', 'event', 'event__venue_place', 'venue_section', 'reserved_by')
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
            try:
                url = get_ticket_pdf_admin_url(obj)
            except Exception as url_exc:
                _admin_log.warning(
                    'TicketAdmin.pdf_staff_link URL helper failed pk=%s: %s',
                    getattr(obj, 'pk', None),
                    url_exc,
                )
                return _admin_pdf_safe_fallback()
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
                )
                return _admin_pdf_safe_fallback()
        except Exception as exc:
            _admin_log.warning(
                'TicketAdmin.pdf_staff_link failed pk=%s: %s',
                getattr(obj, 'pk', None),
                exc,
            )
            return _admin_pdf_safe_fallback()

    pdf_staff_link.short_description = 'PDF (סטאף)'

    def receipt_staff_link(self, obj):
        try:
            rf = getattr(obj, 'receipt_file', None)
            if not rf or not str(getattr(rf, 'name', None) or '').strip():
                return mark_safe('<span style="color:#64748b;">—</span>')
            url = get_ticket_receipt_admin_url(obj)
            if not url:
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
    list_display = ['name', 'category', 'genre', 'is_international', 'created_at']
    list_filter = ['category', 'is_international', 'genre', 'created_at']
    search_fields = ['name', 'description', 'genre']
    readonly_fields = ['created_at', 'updated_at', 'image_delivery_preview', 'cover_image_delivery_preview']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'is_international', 'genre', 'description')
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


class VenueSectionInline(admin.TabularInline):
    model = VenueSection
    extra = 1


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'created_at']
    search_fields = ['name', 'city']
    inlines = [VenueSectionInline]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'artist', 'category', 'high_demand', 'home_team', 'away_team', 'status', 'date',
        'venue', 'city', 'country_display', 'created_at',
    ]
    list_filter = ['artist', 'category', 'high_demand', 'status', 'venue', 'city', 'country', 'age_restriction', 'date', 'created_at']
    search_fields = ['name', 'slug', 'venue', 'city', 'artist__name', 'home_team', 'away_team', 'tournament']
    readonly_fields = ['created_at', 'updated_at', 'view_count', 'image_delivery_preview', 'slug']
    fieldsets = (
        ('Basic Information', {
            'fields': ('artist', 'name', 'slug', 'category', 'status', 'high_demand')
        }),
        ('Location & Timing', {
            'fields': ('venue', 'venue_place', 'city', 'country', 'date', 'ends_at', 'doors_open')
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
    list_display = [
        'id',
        'user',
        'guest_email',
        'status',
        'total_amount',
        'coupon_code_snapshot',
        'affiliate_commission',
        'currency',
        'event_name',
        'created_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'guest_email', 'event_name', 'coupon_code_snapshot']
    readonly_fields = ['created_at', 'updated_at', 'payment_confirm_token']


@admin.register(AffiliatePartner)
class AffiliatePartnerAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'email', 'is_active', 'commission_rate', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'email']


@admin.register(GlobalFeeSettings)
class GlobalFeeSettingsAdmin(admin.ModelAdmin):
    """
    Singleton Platform Settings: one row editable in Admin — drives live checkout fees.
    (service_fee_percentage ≡ base_buyer_fee_percent)
    """

    list_display = [
        'base_buyer_fee_percent',
        'base_seller_fee_percent',
        'buyer_coupon_discount_percent',
        'affiliate_commission_percent',
        'updated_at',
    ]
    readonly_fields = ['updated_at']
    fieldsets = (
        (
            'Platform service fee',
            {
                'fields': (
                    'base_buyer_fee_percent',
                    'base_seller_fee_percent',
                ),
                'description': (
                    'base_buyer_fee_percent is the platform service/operation fee shown at checkout '
                    '(e.g. 12.00 = 12%). Change it here — no code deploy required. '
                    'With a coupon: buyer pays (base buyer − coupon discount); affiliate gets '
                    'affiliate commission (0% for platform coupons); platform keeps the remainder.'
                ),
            },
        ),
        (
            'Coupon split',
            {
                'fields': (
                    'buyer_coupon_discount_percent',
                    'affiliate_commission_percent',
                ),
            },
        ),
        ('Meta', {'fields': ('updated_at',)}),
    )

    def has_add_permission(self, request):
        return not GlobalFeeSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = GlobalFeeSettings.load()
        return redirect(reverse('admin:users_globalfeesettings_change', args=[obj.pk]))


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'coupon_type',
        'affiliate',
        'is_active',
        'redemption_count',
        'max_redemptions_total',
        'discount_amount',
        'buyer_discount_rate',
        'affiliate_commission_rate',
        'platform_net_rate',
    ]
    list_filter = ['is_active', 'coupon_type', 'affiliate']
    search_fields = ['code', 'affiliate__name']


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'coupon',
        'buyer_key',
        'status',
        'discount_amount',
        'affiliate_commission',
        'platform_net_fee',
        'order',
        'created_at',
    ]
    list_filter = ['status', 'coupon']
    search_fields = ['buyer_key', 'guest_email', 'coupon__code']
    readonly_fields = ['created_at', 'updated_at', 'redeemed_at', 'released_at']


@admin.register(SellerPayout)
class SellerPayoutAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'seller',
        'order',
        'total_paid',
        'platform_fee',
        'net_payout',
        'payout_status',
        'seller_bank_summary',
        'transferred_at',
        'created_at',
    ]
    list_filter = [
        'payout_status',
        ('seller', admin.RelatedOnlyFieldListFilter),
        'created_at',
        'transferred_at',
    ]
    search_fields = [
        'seller__username',
        'seller__email',
        'order__id',
        'order__event_name',
        'seller__account_holder_name',
        'seller__account_number',
    ]
    readonly_fields = [
        'created_at',
        'seller_bank_details_panel',
        'seller_pending_total_panel',
        'order',
        'seller',
        'total_paid',
        'platform_fee',
        'net_payout',
    ]
    list_select_related = ['seller', 'order']
    ordering = ['-created_at']
    actions = ['mark_transferred', 'mark_cancelled']
    fieldsets = (
        (
            'Seller payout',
            {
                'fields': (
                    'order',
                    'seller',
                    'payout_status',
                    'total_paid',
                    'platform_fee',
                    'net_payout',
                    'transferred_at',
                    'created_at',
                    'seller_pending_total_panel',
                ),
            },
        ),
        (
            'Seller bank details (for manual transfer)',
            {
                'fields': ('seller_bank_details_panel',),
            },
        ),
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        pending_qs = SellerPayout.objects.filter(payout_status=SellerPayout.PayoutStatus.PENDING)
        all_qs = SellerPayout.objects.exclude(payout_status=SellerPayout.PayoutStatus.CANCELLED)
        owed = pending_qs.aggregate(s=Sum('net_payout'))['s'] or Decimal('0')
        revenue = all_qs.aggregate(s=Sum('platform_fee'))['s'] or Decimal('0')
        extra_context['ledger_total_owed'] = Decimal(owed).quantize(Decimal('0.01'))
        extra_context['ledger_platform_revenue'] = Decimal(revenue).quantize(Decimal('0.01'))
        extra_context['ledger_pending_count'] = pending_qs.count()
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            if hasattr(response, 'context_data') and response.context_data is not None:
                response.context_data.update(extra_context)
            self.message_user(
                request,
                (
                    f'Ledger summary — Total owed to sellers: ₪{extra_context["ledger_total_owed"]} '
                    f'({extra_context["ledger_pending_count"]} pending) · '
                    f'Platform revenue (5% fees): ₪{extra_context["ledger_platform_revenue"]}'
                ),
                level=messages.INFO,
            )
        except (TypeError, ValueError, KeyError, AttributeError):
            pass
        try:
            seller_id = request.GET.get('seller__id__exact')
            if seller_id and hasattr(response, 'context_data') and response.context_data:
                pending_total = SellerPayout.total_pending_for_seller_id(int(seller_id))
                count = SellerPayout.objects.filter(
                    seller_id=int(seller_id),
                    payout_status=SellerPayout.PayoutStatus.PENDING,
                ).count()
                self.message_user(
                    request,
                    f'Pending owed to this seller: ₪{pending_total} ({count} payout(s) awaiting transfer).',
                    level=messages.INFO,
                )
        except (TypeError, ValueError, KeyError):
            pass
        return response

    @admin.action(description='Mark selected payouts as transferred')
    def mark_transferred(self, request, queryset):
        from django.core.exceptions import ValidationError

        from wallets.services import mark_seller_payout_paid

        updated = 0
        failed = 0
        for payout in queryset.select_related('seller', 'order'):
            try:
                mark_seller_payout_paid(payout)
                updated += 1
            except ValidationError:
                failed += 1
        if updated:
            self.message_user(request, f'Marked {updated} payout(s) as transferred.', level=messages.SUCCESS)
        if failed:
            self.message_user(request, f'{failed} payout(s) could not be transferred.', level=messages.WARNING)

    @admin.action(description='Mark selected payouts as cancelled')
    def mark_cancelled(self, request, queryset):
        updated = queryset.update(payout_status=SellerPayout.PayoutStatus.CANCELLED)
        self.message_user(request, f'Marked {updated} payout(s) as cancelled.', level=messages.WARNING)

    @admin.display(description='Bank (seller)')
    def seller_bank_summary(self, obj):
        if not obj or not obj.seller_id:
            return '—'
        s = obj.seller
        bank = (s.bank_name or '').strip() or '—'
        acct = (s.account_number or '').strip()
        tail = f'…{acct[-4:]}' if len(acct) >= 4 else (acct or '—')
        return f'{bank} / {tail}'

    @admin.display(description='Seller pending total')
    def seller_pending_total_panel(self, obj):
        if not obj or not obj.seller_id:
            return format_html('<span style="color:#64748b;">No seller linked</span>')
        total = SellerPayout.total_pending_for_seller(obj.seller)
        count = SellerPayout.pending_for_seller(obj.seller).count()
        return format_html(
            '<p style="margin:0;font-size:1.05rem;"><strong>Total pending owed to this seller:</strong> '
            '₪{} <span style="color:#64748b;">({} pending payout(s))</span></p>',
            total,
            count,
        )

    @admin.display(description='Seller bank details')
    def seller_bank_details_panel(self, obj):
        if not obj or not obj.seller_id:
            return format_html('<span style="color:#64748b;">No seller linked</span>')
        s = obj.seller
        rows = [
            ('Account holder', (s.account_holder_name or '').strip() or '—'),
            ('Bank', (s.bank_name or '').strip() or '—'),
            ('Branch', (s.branch_number or '').strip() or '—'),
            ('Account number', (s.account_number or '').strip() or '—'),
            ('Email', (s.email or '').strip() or '—'),
            ('Phone', (s.phone_number or '').strip() or '—'),
        ]
        lines = ''.join(
            f'<tr><th style="text-align:right;padding:6px 12px 6px 0;color:#475569;">{label}</th>'
            f'<td style="padding:6px 0;font-weight:600;">{value}</td></tr>'
            for label, value in rows
        )
        return format_html(
            '<table style="border-collapse:collapse;direction:rtl;">{}</table>',
            mark_safe(lines),
        )


# Backward-compatible admin alias
PayoutAdmin = SellerPayoutAdmin


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


# ── Analytics Admin ────────────────────────────────────────────────────────────

@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    """
    Admin for AnalyticsEvent.
    The main list gives a raw event log; the custom /dashboard/ sub-page shows
    today's traffic summary (unique visitors, top pages, funnel drop-off).
    """
    list_display = ['timestamp', 'event_type', 'path', 'session_id', 'user']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['path', 'session_id']
    readonly_fields = [
        'timestamp', 'session_id', 'path', 'event_type', 'event_data', 'ip_hash', 'user',
    ]
    ordering = ['-timestamp']

    def get_urls(self):
        from django.urls import path as dj_path
        urls = super().get_urls()
        custom = [
            dj_path(
                'reset-test-data/',
                self.admin_site.admin_view(self.reset_test_data_view),
                name='analyticsevent_reset_test_data',
            ),
            dj_path(
                'dashboard/',
                self.admin_site.admin_view(self.analytics_dashboard_view),
                name='analyticsevent_dashboard',
            ),
        ]
        return custom + urls

    # Link shown at the top of the change list to jump to the dashboard
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['dashboard_url'] = '../dashboard/'
        return super().changelist_view(request, extra_context=extra_context)

    def analytics_dashboard_view(self, request):
        from django.db.models import Count, Q
        from django.shortcuts import render

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_qs = AnalyticsEvent.objects.filter(timestamp__gte=today_start)

        # 1. Unique visitors today (distinct session IDs)
        unique_visitors = today_qs.values('session_id').distinct().count()

        # 2. Top event pages (/event/<id>, legacy /events/<id>) by page_view count
        top_pages = list(
            today_qs
            .filter(event_type='page_view')
            .filter(Q(path__startswith='/event/') | Q(path__startswith='/events/'))
            .values('path')
            .annotate(views=Count('id'))
            .order_by('-views')[:10]
        )

        # 3. Checkout funnel
        checkout_starts = today_qs.filter(event_type='checkout_start').count()
        checkout_completes = today_qs.filter(event_type='checkout_complete').count()
        drop_off = checkout_starts - checkout_completes

        # 4. All-time totals (quick sanity figures)
        total_events = AnalyticsEvent.objects.count()

        context = {
            **self.admin_site.each_context(request),
            'title': 'Analytics Dashboard — Today',
            'unique_visitors': unique_visitors,
            'top_pages': top_pages,
            'checkout_starts': checkout_starts,
            'checkout_completes': checkout_completes,
            'drop_off': drop_off,
            'total_events': total_events,
            'today_label': today_start.strftime('%Y-%m-%d'),
            'show_reset_test_data_button': request.user.is_superuser,
        }
        return render(request, 'admin/analytics_dashboard.html', context)

    def reset_test_data_view(self, request):
        """
        Superuser-only: same behaviour as ``manage.py reset_test_data --execute``.
        GET shows a confirmation page; POST runs the wipe and redirects to the dashboard.
        """
        from users.reset_test_data_core import get_reset_test_data_preview, run_reset_test_data

        if not request.user.is_superuser:
            self.message_user(
                request,
                'Only Django superusers can reset test data.',
                level=messages.ERROR,
            )
            return redirect('admin:index')

        if request.method == 'POST':
            result = run_reset_test_data()
            messages.success(
                request,
                (
                    'Test data reset completed. Deleted %(offers)d offer(s) and %(orders)d order(s); '
                    'reset %(tickets)d ticket row(s) to active; restored quantity on %(qty)d active listing(s). '
                    'Platform sales stats should now read zero.'
                )
                % {
                    'offers': result['offers_deleted'],
                    'orders': result['orders_deleted'],
                    'tickets': result['tickets_reset'],
                    'qty': result['qty_restored'],
                },
            )
            return redirect(reverse('admin:analyticsevent_dashboard'))

        preview = get_reset_test_data_preview()
        context = {
            **self.admin_site.each_context(request),
            'title': 'Confirm reset test data',
            'preview': preview,
            'opts': self.model._meta,
            'has_permission': True,
        }
        return render(request, 'admin/reset_test_data_confirm.html', context)
