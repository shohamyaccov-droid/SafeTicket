"""
Shomer Shabbat payment gating.

Fetches weekly candle-lighting / Havdalah times from Hebcal for Jerusalem
(Asia/Jerusalem), caches them, and exposes helpers to block checkout while
Shabbat is in effect — including a mandatory +5 minute post-Havdalah buffer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)

TZ_IL = ZoneInfo('Asia/Jerusalem')

# Jerusalem (geonameid) — representative Israel times for TradeTix.
HEBCAL_SHABBAT_URL = (
    'https://www.hebcal.com/shabbat?cfg=json&geonameid=281184&m=50'
)
CACHE_KEY_TIMES = 'users:shabbat_times:v1:jerusalem'
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours
HAVDALAH_BUFFER = timedelta(minutes=5)
HEBCAL_TIMEOUT_SECONDS = 8

SHABBAT_RESTRICTION_CODE = 'SHABBAT_RESTRICTION'
SHABBAT_USER_MESSAGE = (
    'התשלום אינו זמין בשבת. בצאת שבת תתחדש האפשרות לתשלום.'
)


@dataclass(frozen=True)
class ShabbatWindow:
    """Candle lighting → buffered Havdalah for the current/upcoming Shabbat."""

    candle_lighting: datetime
    havdalah: datetime  # raw from Hebcal (before buffer)
    havdalah_buffered: datetime

    def contains(self, when: datetime) -> bool:
        local = when.astimezone(TZ_IL) if when.tzinfo else when.replace(tzinfo=TZ_IL)
        start = self.candle_lighting.astimezone(TZ_IL)
        end = self.havdalah_buffered.astimezone(TZ_IL)
        return start <= local < end


def _parse_hebcal_iso(value: str) -> datetime:
    """Parse Hebcal ISO datetime into an aware Asia/Jerusalem datetime."""
    raw = (value or '').strip()
    if raw.endswith('Z'):
        raw = raw[:-1] + '+00:00'
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_IL)
    return dt.astimezone(TZ_IL)


def _extract_window_from_hebcal_payload(payload: dict[str, Any]) -> ShabbatWindow:
    items = payload.get('items') or []
    candles_dt: Optional[datetime] = None
    havdalah_dt: Optional[datetime] = None
    for item in items:
        if not isinstance(item, dict):
            continue
        category = (item.get('category') or '').strip().lower()
        date_str = item.get('date')
        if not date_str:
            continue
        try:
            parsed = _parse_hebcal_iso(str(date_str))
        except (TypeError, ValueError):
            continue
        if category == 'candles' and candles_dt is None:
            candles_dt = parsed
        elif category == 'havdalah' and havdalah_dt is None:
            havdalah_dt = parsed
    if candles_dt is None or havdalah_dt is None:
        raise ValueError('Hebcal payload missing candles/havdalah items')
    if havdalah_dt <= candles_dt:
        raise ValueError('Hebcal havdalah is not after candle lighting')
    buffered = havdalah_dt + HAVDALAH_BUFFER
    return ShabbatWindow(
        candle_lighting=candles_dt,
        havdalah=havdalah_dt,
        havdalah_buffered=buffered,
    )


def _fetch_hebcal_window() -> ShabbatWindow:
    response = requests.get(HEBCAL_SHABBAT_URL, timeout=HEBCAL_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError('Hebcal response is not a JSON object')
    return _extract_window_from_hebcal_payload(payload)


def _window_to_cache_dict(window: ShabbatWindow) -> dict[str, str]:
    return {
        'candle_lighting': window.candle_lighting.isoformat(),
        'havdalah': window.havdalah.isoformat(),
        'havdalah_buffered': window.havdalah_buffered.isoformat(),
    }


def _window_from_cache_dict(data: dict[str, Any]) -> ShabbatWindow:
    return ShabbatWindow(
        candle_lighting=_parse_hebcal_iso(str(data['candle_lighting'])),
        havdalah=_parse_hebcal_iso(str(data['havdalah'])),
        havdalah_buffered=_parse_hebcal_iso(str(data['havdalah_buffered'])),
    )


def _conservative_fallback_window(now: datetime) -> ShabbatWindow:
    """
    Fail-closed heuristic when Hebcal is unreachable and cache is empty.

    Uses a wide Friday afternoon → Saturday late-evening window in Israel so
    payments stay blocked during any plausible Shabbat, at the cost of a
    slightly longer block if times cannot be fetched.
    """
    local = now.astimezone(TZ_IL)
    weekday = local.weekday()  # Mon=0 … Fri=4, Sat=5, Sun=6

    if weekday == 4:  # Friday — candles ~15:30 local
        friday = local.date()
    elif weekday == 5:  # Saturday — candles were yesterday
        friday = (local - timedelta(days=1)).date()
    elif weekday == 6 and local.time() < time(1, 0):  # early Sunday still near Havdalah
        friday = (local - timedelta(days=2)).date()
    else:
        # Mid-week: point at upcoming Friday so contains() is False until then
        days_until_fri = (4 - weekday) % 7
        friday = (local + timedelta(days=days_until_fri)).date()

    saturday = friday + timedelta(days=1)
    candles = datetime.combine(friday, time(15, 30), tzinfo=TZ_IL)
    havdalah = datetime.combine(saturday, time(21, 55), tzinfo=TZ_IL)
    return ShabbatWindow(
        candle_lighting=candles,
        havdalah=havdalah,
        havdalah_buffered=havdalah + HAVDALAH_BUFFER,
    )


def get_shabbat_window(*, force_refresh: bool = False) -> ShabbatWindow:
    """
    Return the current/upcoming Shabbat window (with +5m Havdalah buffer).

    Prefer cache → live Hebcal → conservative fail-closed fallback.
    """
    if not force_refresh:
        cached = cache.get(CACHE_KEY_TIMES)
        if isinstance(cached, dict):
            try:
                return _window_from_cache_dict(cached)
            except (KeyError, TypeError, ValueError):
                cache.delete(CACHE_KEY_TIMES)

    try:
        window = _fetch_hebcal_window()
        cache.set(CACHE_KEY_TIMES, _window_to_cache_dict(window), CACHE_TTL_SECONDS)
        return window
    except Exception as exc:
        logger.warning('Hebcal Shabbat fetch failed: %s', exc, exc_info=False)
        cached = cache.get(CACHE_KEY_TIMES)
        if isinstance(cached, dict):
            try:
                return _window_from_cache_dict(cached)
            except (KeyError, TypeError, ValueError):
                pass
        now = timezone.now().astimezone(TZ_IL)
        return _conservative_fallback_window(now)


def get_shabbat_status(*, now: Optional[datetime] = None) -> dict[str, Any]:
    """
    Public status payload for API + guards.

    ``havdalah_time`` is always the *buffered* end of the restriction window.
    """
    when = (now or timezone.now()).astimezone(TZ_IL)
    window = get_shabbat_window()
    is_shabbat = window.contains(when)
    return {
        'is_shabbat': is_shabbat,
        'timezone': 'Asia/Jerusalem',
        'candle_lighting': window.candle_lighting.isoformat(),
        'havdalah_time': window.havdalah_buffered.isoformat(),
        'havdalah_raw': window.havdalah.isoformat(),
        'havdalah_buffer_minutes': int(HAVDALAH_BUFFER.total_seconds() // 60),
        'now': when.isoformat(),
        'code': SHABBAT_RESTRICTION_CODE if is_shabbat else None,
        'message': SHABBAT_USER_MESSAGE if is_shabbat else None,
    }


def is_shabbat_now(*, now: Optional[datetime] = None) -> bool:
    return bool(get_shabbat_status(now=now)['is_shabbat'])


def shabbat_forbidden_response(*, now: Optional[datetime] = None) -> Optional[Response]:
    """
    If payments are restricted, return a 403 Response with SHABBAT_RESTRICTION.
    Otherwise return None so the caller can continue.
    """
    info = get_shabbat_status(now=now)
    if not info['is_shabbat']:
        return None
    return Response(
        {
            'error': SHABBAT_USER_MESSAGE,
            'code': SHABBAT_RESTRICTION_CODE,
            'havdalah_time': info['havdalah_time'],
            'candle_lighting': info['candle_lighting'],
            'timezone': info['timezone'],
            'havdalah_buffer_minutes': info['havdalah_buffer_minutes'],
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def clear_shabbat_cache() -> None:
    cache.delete(CACHE_KEY_TIMES)


@api_view(['GET'])
@permission_classes([AllowAny])
def shabbat_status_view(request):
    """Public Shabbat payment-restriction status for the SPA countdown modal."""
    return Response(get_shabbat_status())
