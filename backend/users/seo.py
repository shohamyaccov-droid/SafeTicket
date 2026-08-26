"""
Programmatic SEO helpers for Event and Artist pages (Schema.org Event / MusicGroup).

Architecture note (decoupled React SPA + Django API):
- Pure client-side Helmet is NOT enough for reliable indexing: Googlebot can render JS
  (delayed), but social crawlers and many AI bots do not. JSON-LD / meta must appear
  in the *initial* HTML when possible.
- This module builds title/description/canonical/JSON-LD once on the server.
- Consumers: EventSerializer, ArtistDetailSerializer, Django spa_index_view injection,
  frontend seo-server.mjs (serves injected HTML for /event/* and /artist/*).
"""
from __future__ import annotations

import json
import re
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from django.conf import settings
from django.db.models import Max, Min, Sum
from django.utils import timezone
from django.utils.text import slugify


_STAGING_WEB_HOST = 'safeticket-web.onrender.com'
_PUBLIC_SITE_DEFAULT = 'https://tradetix.co.il'
DEFAULT_SITE_TITLE = 'TradeTix - זירת מסחר בטוחה למכירת כרטיסים יד שנייה'
DEFAULT_SITE_DESCRIPTION = (
    'טריידטיקס (TradeTix) — זירת מסחר בטוחה בישראל לקנייה ומכירת כרטיסים יד שנייה. '
    'תשלום מאובטח והגנה על הכסף.'
)
_SITEMAP_CACHE: dict[str, Any] = {'at': 0.0, 'xml': ''}
_SPA_INDEX_CACHE: dict[str, Any] = {'mtime': None, 'html': ''}


def frontend_origin() -> str:
    """
    Public site origin for canonical URLs, Open Graph, JSON-LD, and sitemaps.

    Never emit the Render staging hostname — Google Search Console must see
    https://tradetix.co.il even if FRONTEND_ORIGIN is still set to onrender.com.
    """
    for raw in (
        getattr(settings, 'PUBLIC_SITE_ORIGIN', None),
        getattr(settings, 'FRONTEND_ORIGIN', None),
    ):
        origin = str(raw or '').strip().rstrip('/')
        if not origin:
            continue
        if _STAGING_WEB_HOST in origin.lower():
            continue
        return origin
    return _PUBLIC_SITE_DEFAULT


def api_public_origin() -> str:
    origin = getattr(settings, 'API_PUBLIC_ORIGIN', None) or ''
    if not origin:
        origin = getattr(settings, 'FRONTEND_ORIGIN', '') or 'https://safeticket-api.onrender.com'
    return str(origin).rstrip('/')


def event_path(slug_or_id: str) -> str:
    return f'/event/{slug_or_id}'


def event_public_slug(event) -> str:
    return (getattr(event, 'slug', None) or '').strip() or str(getattr(event, 'pk', '') or '')


def event_canonical_url(event) -> str:
    key = event_public_slug(event) or str(event.pk)
    return f'{frontend_origin()}{event_path(key)}'


def normalize_event_identifier(identifier: str) -> str:
    from urllib.parse import unquote

    return unquote((identifier or '').strip())


def event_legacy_redirect_path(identifier: str, event) -> Optional[str]:
    """Return /event/<ascii-slug> when the request used an id or old Hebrew slug."""
    key = normalize_event_identifier(identifier)
    canonical = event_public_slug(event)
    if not key or not canonical or key == canonical:
        return None
    return event_path(canonical)


def artist_path(slug_or_id: str) -> str:
    return f'/artist/{slug_or_id}'


def artist_canonical_url(artist) -> str:
    key = (getattr(artist, 'slug', None) or '').strip() or str(artist.pk)
    return f'{frontend_origin()}{artist_path(key)}'


def _strip_html(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text or '')).strip()


def _ascii_slug_token(value: str) -> str:
    return (slugify(value or '', allow_unicode=False) or '').strip('-')


def _event_date_stamp(event) -> str:
    dt = getattr(event, 'date', None)
    if not dt:
        return ''
    try:
        local = timezone.localtime(dt) if timezone.is_aware(dt) else dt
        return local.strftime('%Y-%m-%d')
    except Exception:
        return ''


def build_event_slug_base(event) -> str:
    """ASCII URL slug: related artist's English slug + event date (e.g. itay-levi-2026-08-29)."""
    artist_token = ''
    artist = None
    if getattr(event, 'artist_id', None):
        try:
            artist = getattr(event, 'artist', None)
        except Exception:
            artist = None
    if artist is not None:
        artist_token = _ascii_slug_token(build_artist_slug_base(artist))
        if not artist_token:
            artist_token = _ascii_slug_token(getattr(artist, 'slug', None) or '')
    if not artist_token:
        artist_token = _ascii_slug_token(getattr(event, 'name', None) or '') or 'event'
    stamp = _event_date_stamp(event)
    raw = f'{artist_token}-{stamp}' if stamp else artist_token
    base = _ascii_slug_token(raw) or artist_token
    if not base:
        base = f'event-{getattr(event, "pk", None) or "new"}'
    return base[:180]


def apply_event_ascii_slug(event) -> str:
    """Set event.slug to the ASCII artist-date form; keep the previous slug on legacy_slug."""
    desired = ensure_unique_event_slug(event, build_event_slug_base(event))
    current = (getattr(event, 'slug', None) or '').strip()
    if current and current != desired and not (getattr(event, 'legacy_slug', None) or '').strip():
        event.legacy_slug = current
    event.slug = desired
    return desired


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


# ASCII slugs for high-volume Hebrew headliners (e.g. /artist/eyal-golan).
ARTIST_SLUG_ALIASES = {
    'אייל גולן': 'eyal-golan',
    'eyal golan': 'eyal-golan',
    'עומר אדם': 'omer-adam',
    'omer adam': 'omer-adam',
    'איתי לוי': 'itay-levi',
    'itay levi': 'itay-levi',
    'עדן חסון': 'eden-hason',
    'eden hason': 'eden-hason',
    'עודיה': 'odeya',
    'אודיה': 'odeya',
    'odeya': 'odeya',
    'שלמה ארצי': 'shlomo-artzi',
    'shlomo artzi': 'shlomo-artzi',
    'נועה קירל': 'noa-kirel',
    'noa kirel': 'noa-kirel',
    'פאר טסי': 'peer-tasi',
    'peer tasi': 'peer-tasi',
    'טונה': 'tuna',
    'tuna': 'tuna',
    'עדן בן זקן': 'eden-ben-zaken',
    'eden ben zaken': 'eden-ben-zaken',
}


def _normalize_artist_name(name: str) -> str:
    return re.sub(r'\s+', ' ', (name or '').strip()).lower()


def build_artist_slug_base(artist) -> str:
    """Prefer latin SEO slugs (eyal-golan); fall back to unicode slugify."""
    name = (getattr(artist, 'name', None) or '').strip()
    alias = ARTIST_SLUG_ALIASES.get(_normalize_artist_name(name))
    if alias:
        return alias[:180]
    ascii_slug = slugify(name, allow_unicode=False)
    if ascii_slug:
        return ascii_slug[:180]
    uni = slugify(name, allow_unicode=True)
    if uni:
        return uni[:180]
    return f'artist-{getattr(artist, "pk", None) or "new"}'


def ensure_unique_artist_slug(artist, base: Optional[str] = None) -> str:
    from users.models import Artist

    candidate = (base or build_artist_slug_base(artist)).strip('-')[:180] or f'artist-{artist.pk or "x"}'
    qs = Artist.objects.all()
    if artist.pk:
        qs = qs.exclude(pk=artist.pk)
    if not qs.filter(slug=candidate).exists():
        return candidate
    suffix = artist.pk or Artist.objects.order_by('-pk').values_list('pk', flat=True).first() or 1
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
    """SERP title: כרטיסים ל<artist> ב<venue> - TradeTix"""
    artist_name = ''
    if getattr(event, 'artist_id', None) and getattr(event, 'artist', None):
        artist_name = (event.artist.name or '').strip()
    name = (event.name or '').strip()
    subject = artist_name or name or 'אירוע'
    venue = ''
    try:
        venue = (event.venue_display_name() or '').strip()
    except Exception:
        venue = (event.venue or '').strip()
    city = (event.city or '').strip()
    place = venue or city
    if place:
        return _strip_html(f'כרטיסים ל{subject} ב{place} - TradeTix')[:70]
    return _strip_html(f'כרטיסים ל{subject} - TradeTix')[:70]


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


def _ticket_offer_nodes(event, *, canonical: str, currency: str) -> list[dict[str, Any]]:
    from users.models import Ticket

    rows = list(
        Ticket.objects.filter(
            event=event,
            status='active',
            available_quantity__gt=0,
        )
        .order_by('asking_price', 'id')[:20]
    )
    nodes = []
    for ticket in rows:
        try:
            price = str(Decimal(str(ticket.asking_price)).quantize(Decimal('0.01')))
        except Exception:
            continue
        nodes.append(
            {
                '@type': 'Offer',
                'url': canonical,
                'price': price,
                'priceCurrency': currency,
                'availability': 'https://schema.org/InStock',
                'category': 'ticket',
            }
        )
    return nodes


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
        image_url = f'{frontend_origin()}/og-share.png'

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
    offer_nodes = _ticket_offer_nodes(event, canonical=canonical, currency=currency)
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
        if offer_nodes:
            offers['offers'] = offer_nodes
        if len(offer_nodes) == 1:
            offers = offer_nodes[0]
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
        image = f'{frontend_origin()}/og-share.png'

    return {
        'slug': slug,
        'seo_title': title,
        'seo_description': description,
        'canonical_url': canonical,
        'canonical_path': event_path(slug),
        'og_image': image,
        'json_ld': json_ld,
        'crawler_html': (
            '<article class="seo-crawler-snapshot">'
            f'<h1>{_xml_attr(title)}</h1>'
            f'<p>{_xml_attr(description)}</p>'
            '</article>'
        ),
        'lowest_price': str(stats['low']) if stats['low'] is not None else None,
        'highest_price': str(stats['high']) if stats['high'] is not None else None,
        'available_ticket_count': stats['count'],
        'currency': currency,
    }


def artist_display_name(artist) -> str:
    return (getattr(artist, 'name', None) or '').strip() or 'אמן'


def build_artist_seo_title(artist) -> str:
    name = artist_display_name(artist)
    return _strip_html(f'כרטיסים ל{name} - לוח הופעות וכרטיסים יד שנייה | TradeTix')


def build_artist_seo_description(artist) -> str:
    name = artist_display_name(artist)
    return _strip_html(
        f'מחפשים כרטיסים ל{name}? כל המועדים והכרטיסים הכי שווים מחכים לכם ב-TradeTix. '
        f'קנייה ומכירה בטוחה ללא ספסרות.'
    )


def build_artist_intro(artist) -> str:
    name = artist_display_name(artist)
    return (
        f'כאן תמצאו את כל המועדים, ההופעות והכרטיסים יד שנייה ל{name}. '
        f'קנייה ומכירה מאובטחת.'
    )


def _upcoming_artist_events(artist, *, limit: int = 20):
    from users.models import Event

    return list(
        Event.objects.filter(
            artist=artist,
            status__in=['פעיל', 'סולד אאוט'],
            date__gte=timezone.now() - timedelta(hours=12),
        )
        .order_by('date', 'name')[:limit]
    )


def build_artist_json_ld(artist, *, request=None, upcoming_events=None) -> dict[str, Any]:
    from users.serializers import first_resolved_image_url_for_artist

    canonical = artist_canonical_url(artist)
    image_url = first_resolved_image_url_for_artist(request, artist) if request is not None else None
    if not image_url:
        image_url = f'{frontend_origin()}/og-share.png'
    data: dict[str, Any] = {
        '@context': 'https://schema.org',
        '@type': 'MusicGroup',
        'name': artist_display_name(artist),
        'url': canonical,
        'image': image_url,
        'description': build_artist_seo_description(artist),
    }
    events = upcoming_events if upcoming_events is not None else _upcoming_artist_events(artist)
    if events:
        data['event'] = [
            {
                '@type': 'Event',
                'name': (event.name or '').strip() or artist_display_name(artist),
                'startDate': iso_datetime(event.date),
                'url': event_canonical_url(event),
            }
            for event in events
        ]
    return data


def build_artist_seo_payload(artist, *, request=None) -> dict[str, Any]:
    slug = (getattr(artist, 'slug', None) or '').strip() or str(artist.pk)
    title = build_artist_seo_title(artist)
    description = build_artist_seo_description(artist)
    intro = build_artist_intro(artist)
    canonical = artist_canonical_url(artist)
    origin = frontend_origin()
    upcoming = _upcoming_artist_events(artist)
    image = None
    try:
        from users.serializers import first_resolved_image_url_for_artist

        image = first_resolved_image_url_for_artist(request, artist) if request is not None else None
    except Exception:
        image = None
    if not image:
        image = f'{origin}/og-share.png'

    return {
        'slug': slug,
        'seo_title': title,
        'seo_description': description,
        'canonical_url': canonical,
        'canonical_path': artist_path(slug),
        'og_image': image,
        'json_ld': build_artist_json_ld(artist, request=request, upcoming_events=upcoming),
        'crawler_html': (
            '<article class="seo-crawler-snapshot">'
            f'<h1>כרטיסים ל{_xml_attr(artist_display_name(artist))}</h1>'
            f'<p>{_xml_attr(intro)}</p>'
            f'<p><a href="{_xml_attr(origin)}/how-it-works">'
            'יש לך כרטיס מיותר? לחץ כאן כדי למכור אותו בטוח</a></p>'
            f'{_artist_bottom_seo_crawler_html(artist)}'
            '</article>'
        ),
    }


def _artist_bottom_seo_crawler_html(artist) -> str:
    bottom = (getattr(artist, 'bottom_seo_text', None) or '').strip()
    if not bottom:
        return ''
    return f'<p>{_xml_attr(bottom)}</p>'


def _content_json_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'content' / filename


def _load_content_json(filename: str) -> dict[str, Any]:
    path = _content_json_path(filename)
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def _crawler_list_html(section: dict[str, Any]) -> str:
    tag = 'ul' if section.get('list') == 'ul' else 'ol'
    items = []
    for item in section.get('items') or []:
        strong = _xml_attr(str(item.get('strong') or ''))
        text = _xml_attr(str(item.get('text') or ''))
        items.append(f'<li><strong>{strong}</strong> {text}</li>')
    return f'<{tag}>{"".join(items)}</{tag}>'


def _how_it_works_crawler_html(page: dict[str, Any]) -> str:
    parts = [
        '<article class="seo-crawler-snapshot">',
        f'<h1>{_xml_attr(page.get("h1") or "")}</h1>',
        f'<p>{_xml_attr(page.get("intro") or "")}</p>',
    ]
    for section in page.get('sections') or []:
        lead = section.get('lead') or ''
        parts.append('<section>')
        parts.append(f'<h2>{_xml_attr(section.get("h2") or "")}</h2>')
        if lead:
            parts.append(f'<p>{_xml_attr(lead)}</p>')
        parts.append(_crawler_list_html(section))
        parts.append('</section>')
    parts.append('</article>')
    return ''.join(parts)


def _faq_crawler_html(page: dict[str, Any]) -> str:
    parts = [
        '<article class="seo-crawler-snapshot">',
        f'<h1>{_xml_attr(page.get("h1") or "")}</h1>',
        f'<p>{_xml_attr(page.get("intro") or "")}</p>',
    ]
    for item in page.get('items') or []:
        parts.append(
            '<section>'
            f'<h2>{_xml_attr(item.get("question") or "")}</h2>'
            f'<p>{_xml_attr(item.get("answer") or "")}</p>'
            '</section>'
        )
    parts.append('</article>')
    return ''.join(parts)


def _how_it_works_json_ld(page: dict[str, Any]) -> dict[str, Any]:
    sell = next((s for s in page.get('sections') or [] if s.get('id') == 'sell'), None)
    buy = next((s for s in page.get('sections') or [] if s.get('id') == 'buy'), None)

    def steps(section: dict[str, Any] | None) -> list[dict[str, Any]]:
        out = []
        for index, item in enumerate((section or {}).get('items') or [], start=1):
            strong = str(item.get('strong') or '').rstrip(':')
            out.append(
                {
                    '@type': 'HowToStep',
                    'position': index,
                    'name': strong,
                    'text': f'{item.get("strong") or ""} {item.get("text") or ""}'.strip(),
                }
            )
        return out

    return {
        '@context': 'https://schema.org',
        '@graph': [
            {
                '@type': 'HowTo',
                'name': 'איך למכור כרטיס להופעה ב-TradeTix',
                'description': (sell or {}).get('lead') or page.get('description') or '',
                'step': steps(sell),
            },
            {
                '@type': 'HowTo',
                'name': 'איך לקנות כרטיסים יד שניה ב-TradeTix',
                'description': (buy or {}).get('lead') or page.get('description') or '',
                'step': steps(buy),
            },
        ],
    }


def get_static_page_seo(path: str) -> dict[str, Any] | None:
    """Title/description/JSON-LD/crawler HTML for marketing routes (no JS required)."""
    route = path if str(path).startswith('/') else f'/{path}'
    if route != '/' :
        route = route.rstrip('/') or '/'
    origin = frontend_origin()
    og_image = f'{origin}/og-share.png'
    if route == '/how-it-works':
        page = _load_content_json('how-it-works.json')
        return {
            'seo_title': page.get('h1') or DEFAULT_SITE_TITLE,
            'seo_description': page.get('description') or DEFAULT_SITE_DESCRIPTION,
            'canonical_url': f'{origin}/how-it-works',
            'og_image': og_image,
            'json_ld': _how_it_works_json_ld(page),
            'crawler_html': _how_it_works_crawler_html(page),
        }
    if route == '/faq':
        page = _load_content_json('faq-crawler.json')
        return {
            'seo_title': page.get('title') or DEFAULT_SITE_TITLE,
            'seo_description': page.get('description') or DEFAULT_SITE_DESCRIPTION,
            'canonical_url': f'{origin}/faq',
            'og_image': og_image,
            'json_ld': {
                '@context': 'https://schema.org',
                '@type': 'FAQPage',
                'mainEntity': [
                    {
                        '@type': 'Question',
                        'name': item.get('question') or '',
                        'acceptedAnswer': {'@type': 'Answer', 'text': item.get('answer') or ''},
                    }
                    for item in page.get('items') or []
                ],
            },
            'crawler_html': _faq_crawler_html(page),
        }
    if route == '/':
        return {
            'seo_title': DEFAULT_SITE_TITLE,
            'seo_description': DEFAULT_SITE_DESCRIPTION,
            'canonical_url': f'{origin}/',
            'og_image': og_image,
            'json_ld': {
                '@context': 'https://schema.org',
                '@type': 'WebSite',
                'name': 'TradeTix',
                'url': f'{origin}/',
                'description': DEFAULT_SITE_DESCRIPTION,
                'inLanguage': 'he-IL',
            },
            'crawler_html': (
                '<article class="seo-crawler-snapshot">'
                f'<h1>{_xml_attr(DEFAULT_SITE_TITLE)}</h1>'
                f'<p>{_xml_attr(DEFAULT_SITE_DESCRIPTION)}</p>'
                '<p>TradeTix היא זירת מסחר בטוחה לכרטיסים יד שנייה בישראל. '
                'קנייה ומכירה עם תשלום מאובטח והגנה על הכסף.</p>'
                '</article>'
            ),
        }
    return None


def inject_seo_into_html(html: str, seo: dict[str, Any]) -> str:
    """
    Replace/augment <title>, description, canonical, Open Graph, and inject JSON-LD
    into an SPA index.html for crawler-visible first paint.
    """
    title = _strip_html(str(seo.get('seo_title') or 'TradeTix'))
    description = _strip_html(str(seo.get('seo_description') or ''))
    canonical = str(seo.get('canonical_url') or '')
    og_image = str(seo.get('og_image') or '')
    json_ld = seo.get('json_ld') or {}
    crawler_html = str(seo.get('crawler_html') or '').strip()
    # Prevent </script> breakouts in JSON-LD
    ld_text = json.dumps(json_ld, ensure_ascii=False).replace('<', '\\u003c')

    html = re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', html, count=1, flags=re.I)
    if not re.search(r'<title>', html, flags=re.I):
        html = html.replace('</head>', f'<title>{title}</title></head>', 1)

    meta_block = f'''
    <!-- TradeTix SEO (server-injected for crawlers) -->
    <meta name="robots" content="index, follow" />
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
    <script type="application/ld+json" id="tradetix-jsonld">{ld_text}</script>
    '''

    html = re.sub(
        r'<meta\s+name=["\']description["\'][^>]*>',
        '',
        html,
        flags=re.I,
    )
    html = re.sub(r'<meta\s+name=["\']robots["\'][^>]*>', '', html, flags=re.I)
    html = re.sub(r'<link\s+rel=["\']canonical["\'][^>]*>', '', html, flags=re.I)
    html = re.sub(r'<meta\s+property=["\']og:[^"\']+["\'][^>]*>', '', html, flags=re.I)
    html = re.sub(r'<meta\s+name=["\']twitter:[^"\']+["\'][^>]*>', '', html, flags=re.I)
    html = html.replace('</head>', meta_block + '\n</head>', 1)

    if crawler_html:
        html = html.replace('<div id="root"></div>', f'<div id="root">{crawler_html}</div>', 1)
    else:
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


SITEMAP_STATIC_PATHS = (
    '/',
    '/how-it-works',
    '/faq',
    '/about',
    '/contact',
    '/terms',
    '/privacy',
    '/refunds',
    '/buyer-guarantee',
    '/accessibility',
    '/sell/new',
)


def build_sitemap_xml() -> str:
    """XML sitemap of static marketing pages, artist hubs, and upcoming events."""
    from users.models import Artist, Event

    origin = frontend_origin()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in SITEMAP_STATIC_PATHS:
        loc = f'{origin}/' if path == '/' else f'{origin}{path}'
        freq = 'daily' if path == '/' else 'weekly'
        lines.append(
            f'  <url><loc>{_xml_attr(loc)}</loc><changefreq>{freq}</changefreq></url>'
        )
    cutoff = timezone.now() - timedelta(hours=12)
    upcoming_events = Event.objects.filter(status__in=['פעיל', 'סולד אאוט']).filter(date__gte=cutoff)
    artist_ids = upcoming_events.filter(artist_id__isnull=False).values_list('artist_id', flat=True).distinct()
    artists = (
        Artist.objects.filter(pk__in=artist_ids)
        .exclude(slug__isnull=True)
        .exclude(slug='')
        .only('id', 'slug', 'updated_at')
        .order_by('name')[:2000]
    )
    for artist in artists:
        loc = artist_canonical_url(artist)
        lastmod = ''
        updated = getattr(artist, 'updated_at', None)
        if updated:
            lastmod = f'<lastmod>{timezone.localtime(updated).date().isoformat()}</lastmod>'
        lines.append(
            f'  <url><loc>{_xml_attr(loc)}</loc>{lastmod}<changefreq>weekly</changefreq></url>'
        )
    qs = upcoming_events.only('id', 'slug', 'updated_at').order_by('-id')[:5000]
    for event in qs:
        loc = event_canonical_url(event)
        lastmod = ''
        updated = getattr(event, 'updated_at', None)
        if updated:
            lastmod = f'<lastmod>{timezone.localtime(updated).date().isoformat()}</lastmod>'
        lines.append(
            f'  <url><loc>{_xml_attr(loc)}</loc>{lastmod}<changefreq>daily</changefreq></url>'
        )
    lines.append('</urlset>')
    return '\n'.join(lines)


def cached_sitemap_xml(*, ttl: float = 60.0) -> str:
    now = time.time()
    cached = _SITEMAP_CACHE.get('xml') or ''
    if cached and now - float(_SITEMAP_CACHE.get('at') or 0) < ttl:
        return str(cached)
    xml = build_sitemap_xml()
    _SITEMAP_CACHE['at'] = now
    _SITEMAP_CACHE['xml'] = xml
    return xml


def load_spa_index_html() -> str:
    from django.http import Http404

    index = Path(settings.STATIC_ROOT) / 'index.html'
    if not index.is_file():
        raise Http404('index.html missing — run build_render.sh then collectstatic.')
    mtime = index.stat().st_mtime
    if _SPA_INDEX_CACHE.get('html') and _SPA_INDEX_CACHE.get('mtime') == mtime:
        return str(_SPA_INDEX_CACHE['html'])
    html = index.read_text(encoding='utf-8')
    _SPA_INDEX_CACHE['mtime'] = mtime
    _SPA_INDEX_CACHE['html'] = html
    return html


def resolve_event_by_identifier(identifier: str, queryset=None):
    from django.shortcuts import get_object_or_404

    from users.models import Event

    qs = queryset if queryset is not None else Event.objects.all()
    key = normalize_event_identifier(identifier)
    if not key:
        raise Event.DoesNotExist
    if key.isdigit():
        return get_object_or_404(qs, pk=int(key))
    by_slug = qs.filter(slug=key).first()
    if by_slug is not None:
        return by_slug
    by_legacy = qs.filter(legacy_slug=key).first()
    if by_legacy is not None:
        return by_legacy
    return get_object_or_404(qs, slug=key)


def resolve_artist_by_identifier(identifier: str, queryset=None):
    from django.shortcuts import get_object_or_404

    from users.models import Artist

    qs = queryset if queryset is not None else Artist.objects.all()
    key = (identifier or '').strip()
    if not key:
        raise Artist.DoesNotExist
    if key.isdigit():
        return get_object_or_404(qs, pk=int(key))
    return get_object_or_404(qs, slug=key)
