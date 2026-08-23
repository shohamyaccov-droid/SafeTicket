"""
GA4 reporting via the Google Analytics Data API.

Auth is Application Default Credentials only (`google.auth.default()`).
Do not load a service-account JSON path here — org policy forbids key files.
Local setup:

    gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/analytics.readonly
"""

from __future__ import annotations

import logging
import re

import google.auth
from django.conf import settings
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
from google.auth.exceptions import DefaultCredentialsError, RefreshError

logger = logging.getLogger(__name__)

GA4_READONLY_SCOPE = 'https://www.googleapis.com/auth/analytics.readonly'
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
    """Load user/ADC credentials. Never reads a JSON key path explicitly."""
    try:
        credentials, _project = google.auth.default(scopes=[GA4_READONLY_SCOPE])
    except DefaultCredentialsError as exc:
        raise Ga4AuthError(
            'No Application Default Credentials. Run: '
            'gcloud auth application-default login '
            '--scopes=https://www.googleapis.com/auth/cloud-platform,'
            'https://www.googleapis.com/auth/analytics.readonly'
        ) from exc
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
            'ADC token refresh failed. Re-run gcloud auth application-default login with the '
            'analytics.readonly scope.'
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
