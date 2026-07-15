"""
Programmatic SEO helpers for Event pages (Schema.org Event + AggregateOffer).

Architecture note (decoupled React SPA + Django API):
- Pure client-side Helmet is NOT enough for reliable indexing: Googlebot can render JS
  (delayed), but social crawlers and many AI bots do not. JSON-LD / meta must appear
  in the *initial* HTML when possible.
- This module builds title/description/canonical/JSON-LD once on the server.
- Consumers: EventSerializer, Django spa_index_view injection, frontend seo-server.mjs
  (serves injected HTML for /event/* on the public static host).
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.db.models import Max, Min, Sum
from django.utils import timezone
from django.utils.text import slugify


def frontend_origin() -> str:
    origin = getattr(settings, 'FRONTEND_ORIGIN', None) or 'https://safeticket-web.onrender.com'
    return str(origin).rstrip('/')


def api_public_origin() -> str:
    origin = getattr(settings, 'API_PUBLIC_ORIGIN', None) or ''
    if not origin:
        origin = getattr(settings, 'FRONTEND_ORIGIN', '') or 'https://safeticket-api.onrender.com'
    return str(origin).rstrip('/')


def event_path(slug_or_id: str) -> str:
    return f'/event/{slug_or_id}'


def event_canonical_url(event) -> str:
    key = (getattr(event, 'slug', None) or '').strip() or str(event.pk)
    return f'{frontend_origin()}{event_path(key)}'


def _strip_html(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text or '')).strip()


def build_event_slug_base(event) -> str:
    """URL slug base: artist/city (preferred) or event name; Unicode-safe for Hebrew SEO."""
    artist_name = ''
    if getattr(event, 'artist_id', None) and getattr(event, 'artist', None):
        artist_name = (event.artist.name or '').strip()
    city = (event.city or '').strip()
    name = (event.name or '').strip()
    if artist_name and city:
        raw = f'{artist_name}-{city}'
    elif artist_name:
        raw = artist_name
    else:
        raw = name or city or 'event'
    base = slugify(raw, allow_unicode=True)
    if not base:
        base = f'event-{event.pk or "new"}'
    if event.date:
        try:
            local = timezone.localtime(event.date) if timezone.is_aware(event.date) else event.date
            base = slugify(f'{base}-{local.strftime("%Y-%m-%d")}', allow_unicode=True)
        except Exception:
            pass
    return (base or f'event-{event.pk or "new"}')[:180]


def ensure_unique_event_slug(event, base: Optional[str] = None) -> str:
    from users.models import Event

    candidate = (base or build_event_slug_base(event)).strip('-')[:180] or f'event-{event.pk or "x"}'
    qs = Event.objects.all()
    if event.pk:
        qs = qs.exclude(pk=event.pk)
    if not qs.filter(slug=candidate).exists():
        return candidate
    suffix = event.pk or Event.objects.order_by('-pk').values_list('pk', flat=True).first() or 1
    unique = f'{candidate}-{suffix}'[:200]
    n = 2
    while qs.filter(slug=unique).exists():
        unique = f'{candidate}-{suffix}-{n}'[:200]
        n += 1
    return unique


def iso_datetime(dt) -> Optional[str]:
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).isoformat()


def _active_ticket_price_stats(event) -> dict[str, Any]:
    from users.models import Ticket

    agg = Ticket.objects.filter(
        event=event,
        status='active',
        available_quantity__gt=0,
    ).aggregate(
        low=Min('asking_price'),
        high=Max('asking_price'),
        count=Sum('available_quantity'),
    )
    return {
        'low': agg.get('low'),
        'high': agg.get('high'),
        'count': int(agg.get('count') or 0),
    }


def build_seo_title(event) -> str:
    name = (event.name or '').strip() or 'אירוע'
    venue = ''
    try:
        venue = (event.venue_display_name() or '').strip()
    except Exception:
        venue = (event.venue or '').strip()
    city = (event.city or '').strip()
    place = venue or city
    if place:
        return _strip_html(f'{name} ב-{place} - כרטיסים | TradeTix')[:70]
    return _strip_html(f'{name} - כרטיסים | TradeTix')[:70]


def build_seo_description(event, *, low_price: Any = None, currency: str = 'ILS') -> str:
    name = (event.name or '').strip() or 'אירוע'
    try:
        venue = (event.venue_display_name() or '').strip()
    except Exception:
        venue = (event.venue or '').strip()
    city = (event.city or '').strip()
    place = ', '.join(p for p in (venue, city) if p)
    price_bit = ''
    if low_price is not None:
        try:
            price_bit = f' החל מ-{Decimal(str(low_price)):.0f} {currency}.'
        except Exception:
            price_bit = ''
    if place:
        return _strip_html(
            f'קנו או מכרו כרטיסים ל-{name} ב-{place} ב-TradeTix.{price_bit} '
            f'תשלום מאובטח והגנה מלאה על הכסף.'
        )[:160]
    return _strip_html(
        f'קנו או מכרו כרטיסים ל-{name} ב-TradeTix.{price_bit} תשלום מאובטח והגנה מלאה על הכסף.'
    )[:160]


def event_status_schema(event) -> str:
    status = (getattr(event, 'status', None) or '').strip()
    mapping = {
        'בוטל': 'https://schema.org/EventCancelled',
        'נדחה': 'https://schema.org/EventPostponed',
        'סולד אאוט': 'https://schema.org/EventScheduled',
        'פעיל': 'https://schema.org/EventScheduled',
    }
    return mapping.get(status, 'https://schema.org/EventScheduled')


def build_event_json_ld(event, *, request=None) -> dict[str, Any]:
    """
    Google Event rich-result compatible JSON-LD with nested AggregateOffer when tickets exist.
    Required: name, startDate, location.
    """
    from users.currency import iso4217_for_country
    from users.serializers import first_resolved_image_url_for_event

    currency = iso4217_for_country(getattr(event, 'country', None)) or 'ILS'
    stats = _active_ticket_price_stats(event)
    low, high, offer_count = stats['low'], stats['high'], stats['count']
    canonical = event_canonical_url(event)
    image_url = first_resolved_image_url_for_event(request, event) if request is not None else None
    if not image_url:
        image_url = f'{frontend_origin()}/og-share.svg'

    venue_name = ''
    try:
        venue_name = event.venue_display_name()
    except Exception:
        venue_name = event.venue or ''
    city = (event.city or '').strip()
    country = (getattr(event, 'country', None) or 'IL').upper()

    location: dict[str, Any] = {
        '@type': 'Place',
        'name': venue_name or city or 'Israel',
        'address': {
            '@type': 'PostalAddress',
            'addressLocality': city or venue_name or '',
            'addressCountry': country,
        },
    }
    if venue_name:
        location['address']['streetAddress'] = venue_name

    availability = (
        'https://schema.org/SoldOut'
        if offer_count <= 0 or (getattr(event, 'status', '') == 'סולד אאוט')
        else 'https://schema.org/InStock'
    )

    offers: dict[str, Any]
    if low is not None and offer_count > 0:
        offers = {
            '@type': 'AggregateOffer',
            'url': canonical,
            'priceCurrency': currency,
            'lowPrice': str(Decimal(str(low)).quantize(Decimal('0.01'))),
            'highPrice': str(Decimal(str(high if high is not None else low)).quantize(Decimal('0.01'))),
            'offerCount': str(offer_count),
            'availability': availability,
            'validFrom': iso_datetime(getattr(event, 'created_at', None) or timezone.now()),
        }
    else:
        offers = {
            '@type': 'Offer',
            'url': canonical,
            'price': '0',
            'priceCurrency': currency,
            'availability': availability,
            'validFrom': iso_datetime(timezone.now()),
        }

    data: dict[str, Any] = {
        '@context': 'https://schema.org',
        '@type': 'Event',
        'name': (event.name or '').strip() or 'Event',
        'startDate': iso_datetime(event.date),
        'eventAttendanceMode': 'https://schema.org/OfflineEventAttendanceMode',
        'eventStatus': event_status_schema(event),
        'location': location,
        'image': [image_url] if image_url else [],
        'description': build_seo_description(event, low_price=low, currency=currency),
        'offers': offers,
        'organizer': {
            '@type': 'Organization',
            'name': 'TradeTix',
            'url': frontend_origin(),
        },
        'url': canonical,
    }
    if getattr(event, 'ends_at', None):
        data['endDate'] = iso_datetime(event.ends_at)
    if getattr(event, 'artist_id', None) and getattr(event, 'artist', None) and event.artist.name:
        data['performer'] = {
            '@type': 'PerformingGroup',
            'name': event.artist.name,
        }
    return data


def build_event_seo_payload(event, *, request=None) -> dict[str, Any]:
    from users.currency import iso4217_for_country

    currency = iso4217_for_country(getattr(event, 'country', None)) or 'ILS'
    stats = _active_ticket_price_stats(event)
    slug = (getattr(event, 'slug', None) or '').strip() or str(event.pk)
    title = build_seo_title(event)
    description = build_seo_description(event, low_price=stats['low'], currency=currency)
    canonical = event_canonical_url(event)
    json_ld = build_event_json_ld(event, request=request)
    image = None
    try:
        from users.serializers import first_resolved_image_url_for_event

        image = first_resolved_image_url_for_event(request, event) if request is not None else None
    except Exception:
        image = None
    if not image:
        image = f'{frontend_origin()}/og-share.svg'

    return {
        'slug': slug,
        'seo_title': title,
        'seo_description': description,
        'canonical_url': canonical,
        'canonical_path': event_path(slug),
        'og_image': image,
        'json_ld': json_ld,
        'lowest_price': str(stats['low']) if stats['low'] is not None else None,
        'highest_price': str(stats['high']) if stats['high'] is not None else None,
        'available_ticket_count': stats['count'],
        'currency': currency,
    }


def inject_seo_into_html(html: str, seo: dict[str, Any]) -> str:
    """
    Replace/augment <title>, description, canonical, Open Graph, and inject JSON-LD
    into an SPA index.html for crawler-visible first paint.
    """
    import json

    title = _strip_html(str(seo.get('seo_title') or 'TradeTix'))
    description = _strip_html(str(seo.get('seo_description') or ''))
    canonical = str(seo.get('canonical_url') or '')
    og_image = str(seo.get('og_image') or '')
    json_ld = seo.get('json_ld') or {}
    # Prevent </script> breakouts in JSON-LD
    ld_text = json.dumps(json_ld, ensure_ascii=False).replace('<', '\\u003c')

    def repl_title(m):
        return f'<title>{title}</title>'

    html = re.sub(r'<title>[^<]*</title>', repl_title, html, count=1, flags=re.I)
    if not re.search(r'<title>', html, flags=re.I):
        html = html.replace('</head>', f'<title>{title}</title></head>', 1)

    meta_block = f'''
    <!-- TradeTix event SEO (server-injected for crawlers) -->
    <meta name="description" content="{_xml_attr(description)}" />
    <link rel="canonical" href="{_xml_attr(canonical)}" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="TradeTix" />
    <meta property="og:locale" content="he_IL" />
    <meta property="og:title" content="{_xml_attr(title)}" />
    <meta property="og:description" content="{_xml_attr(description)}" />
    <meta property="og:url" content="{_xml_attr(canonical)}" />
    <meta property="og:image" content="{_xml_attr(og_image)}" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{_xml_attr(title)}" />
    <meta name="twitter:description" content="{_xml_attr(description)}" />
    <meta name="twitter:image" content="{_xml_attr(og_image)}" />
    <script type="application/ld+json" id="tradetix-event-jsonld">{ld_text}</script>
    '''

    # Drop conflicting default description/canonical/og tags from static shell (first-pass).
    html = re.sub(
        r'<meta\s+name=["\']description["\'][^>]*>',
        '',
        html,
        flags=re.I,
    )
    html = re.sub(r'<link\s+rel=["\']canonical["\'][^>]*>', '', html, flags=re.I)
    html = re.sub(r'<meta\s+property=["\']og:[^"\']+["\'][^>]*>', '', html, flags=re.I)
    html = re.sub(r'<meta\s+name=["\']twitter:[^"\']+["\'][^>]*>', '', html, flags=re.I)
    html = html.replace('</head>', meta_block + '\n</head>', 1)

    # Noscript fallback for non-JS crawlers
    noscript = (
        f'<noscript><article><h1>{_xml_attr(title)}</h1>'
        f'<p>{_xml_attr(description)}</p>'
        f'<p><a href="{_xml_attr(canonical)}">Tickets</a></p></article></noscript>'
    )
    if '<div id="root">' in html:
        html = html.replace('<div id="root"></div>', f'<div id="root"></div>{noscript}', 1)
    return html


def _xml_attr(value: str) -> str:
    return (
        (value or '')
        .replace('&', '&amp;')
        .replace('"', '&quot;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def resolve_event_by_identifier(identifier: str, queryset=None):
    from django.shortcuts import get_object_or_404

    from users.models import Event

    qs = queryset if queryset is not None else Event.objects.all()
    key = (identifier or '').strip()
    if not key:
        raise Event.DoesNotExist
    if key.isdigit():
        return get_object_or_404(qs, pk=int(key))
    return get_object_or_404(qs, slug=key)
