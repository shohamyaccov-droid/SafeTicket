"""
Defensive query/serialization when the production DB briefly lags behind deployed code
(e.g. migration not applied yet): omit new columns from SELECT and never 500 the public feed.
"""
from __future__ import annotations

from django.db.models import QuerySet
from django.db.utils import DatabaseError, OperationalError, ProgrammingError

# New Event columns introduced after initial launch; defer until migration is applied everywhere.
EVENT_PUBLIC_READ_DEFER = ('high_demand',)


def event_queryset_defer_rollout_columns(qs: QuerySet) -> QuerySet:
    """Avoid selecting Event.high_demand if the column does not exist yet (ProgrammingError)."""
    return qs.defer(*EVENT_PUBLIC_READ_DEFER)


def ticket_queryset_defer_event_rollout_columns(qs: QuerySet) -> QuerySet:
    """Same for Ticket → Event joins (listings, seller dashboard)."""
    return qs.defer('event__high_demand')


def safe_event_high_demand_bool(obj) -> bool:
    """Serializer helper: lazy-loaded deferred field or missing DB column."""
    try:
        return bool(getattr(obj, 'high_demand', False))
    except (ProgrammingError, OperationalError, DatabaseError, AttributeError):
        return False
    except Exception:
        return False
