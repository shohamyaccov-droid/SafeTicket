"""Shared select_related / prefetch / annotate helpers for catalog querysets."""
from django.db.models import Count, IntegerField, OuterRef, Prefetch, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from users.models import Ticket, TicketAlert, VenueSection

TICKET_CATALOG_SELECT_RELATED = (
    'event',
    'event__artist',
    'event__venue_place',
    'seller',
    'venue_section',
)

EVENT_CATALOG_SELECT_RELATED = ('artist', 'venue_place')

_INT = IntegerField()


def event_venue_sections_prefetch():
    return Prefetch(
        'venue_place__sections',
        queryset=VenueSection.objects.order_by('name'),
    )


def _zero():
    return Value(0, output_field=_INT)


def annotate_waitlist_count(qs):
    """People currently waiting (un-notified TicketAlert rows) for this event.

    Uses a correlated Subquery (not JOIN+aggregate) so PostgreSQL never mixes
    DISTINCT / GROUP BY with reverse-FK sums.
    """
    waiting = (
        TicketAlert.objects.filter(event_id=OuterRef('pk'), notified=False)
        .order_by()
        .values('event_id')
        .annotate(c=Count('id'))
        .values('c')[:1]
    )
    return qs.annotate(
        _waitlist_count=Coalesce(
            Subquery(waiting, output_field=_INT),
            _zero(),
            output_field=_INT,
        )
    )


def annotate_active_tickets_total(qs):
    """Active listing quantity via Subquery — Postgres-safe (no JOIN Sum + COALESCE type clash)."""
    stock = (
        Ticket.objects.filter(
            event_id=OuterRef('pk'),
            status='active',
            available_quantity__gt=0,
        )
        .order_by()
        .values('event_id')
        .annotate(s=Sum('available_quantity'))
        .values('s')[:1]
    )
    qs = qs.annotate(
        _active_tickets_total=Coalesce(
            Subquery(stock, output_field=_INT),
            _zero(),
            output_field=_INT,
        )
    )
    return annotate_waitlist_count(qs)
