"""
GA4 reporting via the Google Analytics Data API.

Auth is Application Default Credentials only (`google.auth.default()`).
Do not load a service-account JSON path here — org policy forbids key files.
Local setup (prefer service-account impersonation; user OAuth + analytics.readonly
is often blocked by Google's consent screen):

    gcloud auth application-default login --impersonate-service-account=SA_EMAIL
"""

from __future__ import annotations

import logging
import os
import re

import google.auth
from django.conf import settings
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    FilterExpressionList,
    Metric,
    OrderBy,
    RunReportRequest,
)
from google.auth.exceptions import DefaultCredentialsError, RefreshError

logger = logging.getLogger(__name__)

_PROPERTY_ID_RE = re.compile(r'^\d+$')


class Ga4ConfigError(ValueError):
    """Missing or invalid GA4 property configuration."""


class Ga4AuthError(RuntimeError):
    """ADC is missing or cannot mint a token for the Analytics Data API."""


class Ga4ApiError(RuntimeError):
    """The Analytics Data API rejected the request or returned an unexpected payload."""


def normalize_ga4_property_id(raw: str | None) -> str:
    """Accept '123456789' or 'properties/123456789'. Reject measurement IDs like G-XXXX."""
    value = (raw or '').strip()
    if value.lower().startswith('properties/'):
        value = value.split('/', 1)[1].strip()
    if not value:
        raise Ga4ConfigError(
            'GA4_PROPERTY_ID is not set. In Analytics: Admin → Property settings → Property ID '
            '(digits only, not the G-XXXXXXXX measurement ID).'
        )
    if value.upper().startswith('G-'):
        raise Ga4ConfigError(
            'GA4_PROPERTY_ID looks like a Measurement ID (G-…). Use the numeric Property ID instead.'
        )
    if not _PROPERTY_ID_RE.fullmatch(value):
        raise Ga4ConfigError(f'GA4_PROPERTY_ID must be digits only, got {value!r}.')
    return value


def get_ga4_property_id() -> str:
    return normalize_ga4_property_id(getattr(settings, 'GA4_PROPERTY_ID', '') or '')


def get_adc_credentials():
    """Load ADC. Never reads a JSON key path explicitly.

    Do not request analytics.readonly on the user OAuth client — Google's
    default client hard-blocks that scope. Impersonated service accounts
    with GA4 Viewer access work via google.auth.default() with no extra scopes.
    """
    quota_project = (
        os.environ.get('GOOGLE_CLOUD_PROJECT')
        or os.environ.get('GCLOUD_PROJECT')
        or getattr(settings, 'GOOGLE_CLOUD_PROJECT', '')
        or ''
    ).strip()
    try:
        credentials, _project = google.auth.default(
            quota_project_id=quota_project or None,
        )
    except DefaultCredentialsError as exc:
        raise Ga4AuthError(
            'No Application Default Credentials. Run: '
            'gcloud auth application-default login '
            '--impersonate-service-account=YOUR_SA_EMAIL'
        ) from exc
    if quota_project and hasattr(credentials, 'with_quota_project'):
        credentials = credentials.with_quota_project(quota_project)
    return credentials


def _metric_int(row, index: int) -> int:
    try:
        raw = row.metric_values[index].value
    except (IndexError, AttributeError):
        return 0
    try:
        return int(float(raw or 0))
    except (TypeError, ValueError):
        return 0


def fetch_ga4_last_7_days(property_id: str | None = None) -> dict:
    """
    Totals for the last 7 days (including today): sessions, active users, page views.

    Returns a JSON-serializable dict. Does not log credential material.
    """
    pid = normalize_ga4_property_id(property_id) if property_id else get_ga4_property_id()
    credentials = get_adc_credentials()
    client = BetaAnalyticsDataClient(credentials=credentials)
    request = RunReportRequest(
        property=f'properties/{pid}',
        date_ranges=[DateRange(start_date='7daysAgo', end_date='today')],
        metrics=[
            Metric(name='sessions'),
            Metric(name='activeUsers'),
            Metric(name='screenPageViews'),
        ],
    )
    try:
        response = client.run_report(request)
    except RefreshError as exc:
        raise Ga4AuthError(
            'ADC token refresh failed. Re-run: gcloud auth application-default login '
            '--impersonate-service-account=YOUR_SA_EMAIL'
        ) from exc
    except Exception as exc:
        logger.warning('GA4 run_report failed: %s', exc.__class__.__name__)
        raise Ga4ApiError(f'GA4 Data API request failed: {exc}') from exc

    sessions = active_users = page_views = 0
    if response.rows:
        row = response.rows[0]
        sessions = _metric_int(row, 0)
        active_users = _metric_int(row, 1)
        page_views = _metric_int(row, 2)

    return {
        'property_id': pid,
        'date_range': {'start_date': '7daysAgo', 'end_date': 'today'},
        'sessions': sessions,
        'active_users': active_users,
        'page_views': page_views,
    }


def _metric_float(row, index: int) -> float:
    try:
        raw = row.metric_values[index].value
    except (IndexError, AttributeError):
        return 0.0
    try:
        return float(raw or 0)
    except (TypeError, ValueError):
        return 0.0


def _dimension_value(row, index: int) -> str:
    try:
        return str(row.dimension_values[index].value or '')
    except (IndexError, AttributeError):
        return ''


def _dropoff_percent(start, end):
    start_n = float(start or 0)
    end_n = float(end or 0)
    if start_n <= 0:
        return None
    return round(max(0.0, min(100.0, 100.0 * (1.0 - end_n / start_n))), 1)


def _conversion_percent(start, end):
    start_n = float(start or 0)
    end_n = float(end or 0)
    if start_n <= 0:
        return None
    return round(100.0 * end_n / start_n, 1)


_EXACT = Filter.StringFilter.MatchType.EXACT
_BEGINS = Filter.StringFilter.MatchType.BEGINS_WITH

# Ticket/artist surfaces in this SPA. `/event-group` is a name grouping, not `/event/:slug`.
_MARKETPLACE_PREFIXES = ('/event', '/event-group', '/artist', '/ticket')
# Buyer "ticket details" = event page + per-ticket selection. Artist hubs are browse, not details.
_TICKET_DETAIL_PREFIXES = ('/event', '/ticket')
_SELL_NEW_PREFIX = '/sell/new'


def _normalize_path(path: str) -> str:
    return (path or '').split('?')[0].rstrip('/') or '/'


def _path_matches_prefix(path: str, prefix: str) -> bool:
    p = _normalize_path(path)
    return p == prefix or p.startswith(prefix + '/')


def _page_kind(path: str) -> str:
    """Label a pagePath for the admin table (longer prefixes first)."""
    p = _normalize_path(path)
    if p == '/':
        return 'home'
    if _path_matches_prefix(path, '/event-group'):
        return 'event_group'
    if _path_matches_prefix(path, '/event'):
        return 'event'
    if _path_matches_prefix(path, '/artist'):
        return 'artist'
    if _path_matches_prefix(path, '/ticket'):
        return 'ticket'
    if _path_matches_prefix(path, '/sell'):
        return 'sell'
    if _path_matches_prefix(path, '/checkout'):
        return 'checkout'
    return 'other'


def _path_filter(match_type, value: str) -> FilterExpression:
    return FilterExpression(
        filter=Filter(
            field_name='pagePath',
            string_filter=Filter.StringFilter(
                match_type=match_type,
                value=value,
                case_sensitive=False,
            ),
        )
    )


def _path_family_expressions(prefix: str) -> list[FilterExpression]:
    """Match `/event` and `/event/slug` but not sibling `/event-group`."""
    return [
        _path_filter(_EXACT, prefix),
        _path_filter(_BEGINS, prefix + '/'),
    ]


def _any_path_family_filter(prefixes) -> FilterExpression:
    expressions = []
    for prefix in prefixes:
        expressions.extend(_path_family_expressions(prefix))
    return FilterExpression(or_group=FilterExpressionList(expressions=expressions))


def _event_name_filter(event_name: str) -> FilterExpression:
    return FilterExpression(
        filter=Filter(
            field_name='eventName',
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.EXACT,
                value=event_name,
                case_sensitive=True,
            ),
        )
    )


def _run_report(client, pid: str, **kwargs):
    try:
        return client.run_report(RunReportRequest(property=f'properties/{pid}', **kwargs))
    except RefreshError as exc:
        raise Ga4AuthError(
            'ADC token refresh failed. Re-run: gcloud auth application-default login '
            '--impersonate-service-account=YOUR_SA_EMAIL'
        ) from exc
    except Exception as exc:
        logger.warning('GA4 run_report failed: %s', exc.__class__.__name__)
        raise Ga4ApiError(f'GA4 Data API request failed: {exc}') from exc


def _first_row_metrics(response, ints=0, floats=0):
    if not response.rows:
        return tuple([0] * ints + [0.0] * floats)
    row = response.rows[0]
    out = []
    for i in range(ints):
        out.append(_metric_int(row, i))
    for i in range(floats):
        out.append(_metric_float(row, ints + i))
    return tuple(out)


def _sessions_matching(client, pid: str, date_range: DateRange, dimension_filter) -> int:
    """Sessions that included any matching page — no pagePath dimension, so no double-count."""
    response = _run_report(
        client,
        pid,
        date_ranges=[date_range],
        metrics=[Metric(name='sessions')],
        dimension_filter=dimension_filter,
    )
    return _first_row_metrics(response, ints=1)[0]


def _event_count(client, pid: str, date_range: DateRange, event_name: str) -> int:
    response = _run_report(
        client,
        pid,
        date_ranges=[date_range],
        metrics=[Metric(name='eventCount')],
        dimension_filter=_event_name_filter(event_name),
    )
    return _first_row_metrics(response, ints=1)[0]


def _step_dropoffs(steps):
    dropoffs = []
    for i in range(len(steps) - 1):
        a, b = steps[i], steps[i + 1]
        dropoffs.append(
            {
                'from': a['key'],
                'to': b['key'],
                'dropoff_percent': _dropoff_percent(a['sessions'], b['sessions']),
                'conversion_percent': _conversion_percent(a['sessions'], b['sessions']),
            }
        )
    return dropoffs


def fetch_ga4_behavior_dashboard(property_id: str | None = None, start_date='7daysAgo', end_date='today') -> dict:
    """
    Conversion-focused GA4 snapshot: top marketplace pages, buyer/seller funnels, engagement.

    Funnel definitions (independent counts — NOT a strict same-session funnel):
    - Buyer: homepage `/` → ticket details (`/event/*` or `/ticket/*`) →
      `begin_checkout` → `purchase`. Checkout is a modal on the event page, so
      we use GA4 events rather than a `/checkout` path (PayMe return URLs exist
      but are not the start of checkout).
    - Seller: sessions on `/sell/new` → `generate_lead` (successful listing).
      `generate_lead` also fires on offer submit, so seller conversion can be
      slightly inflated.

    Direct landings on `/event` can make ticket-detail sessions exceed homepage.

    UI/UX interpretation of metrics:
    - Top event/artist/ticket pages: high views + high bounce usually means
      inventory or price does not match intent — fix empty/waitlist CTA and
      seating clarity before buying more ads to that URL.
    - Bounce rate: >~60% on home often means hero/search miss intent. On an
      event URL it often means sold-out inventory with a weak waitlist CTA.
    - Avg session duration: sub-30s is pogo-sticking; 2–4 min on `/event` is
      healthy map/price exploration.
    - Buyer drop-off: home→details = merchandising leak; details→begin_checkout
      = checkout friction (guest form, fees, map); begin_checkout→purchase =
      payment / PayMe return UX.
    - Seller `/sell/new`→generate_lead: form length, PDF validation, or auth wall.
    """
    pid = normalize_ga4_property_id(property_id) if property_id else get_ga4_property_id()
    client = BetaAnalyticsDataClient(credentials=get_adc_credentials())
    date_range = DateRange(start_date=start_date, end_date=end_date)

    totals_resp = _run_report(
        client,
        pid,
        date_ranges=[date_range],
        metrics=[
            Metric(name='sessions'),
            Metric(name='activeUsers'),
            Metric(name='screenPageViews'),
            Metric(name='engagedSessions'),
            Metric(name='bounceRate'),
            Metric(name='averageSessionDuration'),
            Metric(name='engagementRate'),
        ],
    )
    sessions, active_users, page_views, engaged, bounce_rate, avg_duration, engagement_rate = _first_row_metrics(
        totals_resp, ints=4, floats=3
    )

    # Dedicated marketplace query so homepage/admin traffic cannot crowd out /event and /artist.
    top_resp = _run_report(
        client,
        pid,
        date_ranges=[date_range],
        dimensions=[Dimension(name='pagePath'), Dimension(name='pageTitle')],
        metrics=[
            Metric(name='screenPageViews'),
            Metric(name='sessions'),
            Metric(name='bounceRate'),
            Metric(name='averageSessionDuration'),
        ],
        dimension_filter=_any_path_family_filter(_MARKETPLACE_PREFIXES),
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name='screenPageViews'), desc=True)],
        limit=25,
    )
    marketplace_pages = []
    for row in top_resp.rows or []:
        path = _dimension_value(row, 0)
        kind = _page_kind(path)
        if kind not in ('event', 'event_group', 'artist', 'ticket'):
            continue
        marketplace_pages.append(
            {
                'path': path or '/',
                'title': _dimension_value(row, 1),
                'kind': kind,
                'page_views': _metric_int(row, 0),
                'sessions': _metric_int(row, 1),
                'bounce_rate': round(_metric_float(row, 2), 4),
                'avg_session_duration_seconds': round(_metric_float(row, 3), 1),
            }
        )

    home_sessions = _sessions_matching(client, pid, date_range, _path_filter(_EXACT, '/'))
    ticket_detail_sessions = _sessions_matching(
        client, pid, date_range, _any_path_family_filter(_TICKET_DETAIL_PREFIXES)
    )
    checkout_events = _event_count(client, pid, date_range, 'begin_checkout')
    purchase_events = _event_count(client, pid, date_range, 'purchase')
    sell_new_sessions = _sessions_matching(
        client, pid, date_range, _any_path_family_filter((_SELL_NEW_PREFIX,))
    )
    listing_leads = _event_count(client, pid, date_range, 'generate_lead')

    buyer_steps = [
        {'key': 'home', 'label': 'דף הבית', 'path': '/', 'sessions': home_sessions},
        {
            'key': 'ticket_details',
            'label': 'פרטי כרטיס / אירוע',
            'path': '/event/*, /ticket/*',
            'sessions': ticket_detail_sessions,
        },
        {
            'key': 'checkout',
            'label': 'התחלת צ׳קאאוט (מודאל)',
            'event': 'begin_checkout',
            'sessions': checkout_events,
        },
        {
            'key': 'purchase',
            'label': 'רכישה הושלמה',
            'event': 'purchase',
            'sessions': purchase_events,
        },
    ]
    seller_steps = [
        {
            'key': 'sell_new',
            'label': 'טופס מכירה',
            'path': '/sell/new',
            'sessions': sell_new_sessions,
        },
        {
            'key': 'listing_created',
            'label': 'מודעה נוצרה',
            'event': 'generate_lead',
            'sessions': listing_leads,
        },
    ]

    return {
        'property_id': pid,
        'date_range': {'start_date': start_date, 'end_date': end_date},
        'sessions': sessions,
        'active_users': active_users,
        'page_views': page_views,
        'engagement': {
            # Bounce: high on home → hero/search miss; high on /event → weak inventory CTA.
            'bounce_rate': round(bounce_rate, 4),
            'bounce_rate_percent': round(bounce_rate * 100, 1),
            # Duration: <30s pogo-stick; 2–4 min on event pages is healthy exploration.
            'avg_session_duration_seconds': round(avg_duration, 1),
            'engaged_sessions': engaged,
            'engagement_rate': round(engagement_rate, 4),
            'engagement_rate_percent': round(engagement_rate * 100, 1),
        },
        'top_pages': marketplace_pages,
        'marketplace_pages': marketplace_pages,
        'buyer_funnel': {'steps': buyer_steps, 'dropoffs': _step_dropoffs(buyer_steps)},
        'seller_funnel': {'steps': seller_steps, 'dropoffs': _step_dropoffs(seller_steps)},
        'limitations': {
            'funnel_type': 'independent_counts',
            'notes': [
                'Path and event counts are independent, not a same-session sequential funnel.',
                'Checkout is a modal on the event page; begin_checkout/purchase events are used instead of /checkout paths.',
                'Seller step is /sell/new only (not the /sell prefix). generate_lead also fires on offer submit.',
                'Direct landings on /event can make ticket-detail sessions exceed homepage sessions.',
            ],
        },
    }

