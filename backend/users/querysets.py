"""Shared select_related / prefetch / annotate helpers for catalog querysets."""
from django.db.models import Count, IntegerField, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from users.models import TicketAlert, VenueSection

TICKET_CATALOG_SELECT_RELATED = (
    'event',
    'event__artist',
    'event__venue_place',
    'seller',
    'venue_section',
)

EVENT_CATALOG_SELECT_RELATED = ('artist', 'venue_place')


def event_venue_sections_prefetch():
    return Prefetch(
        'venue_place__sections',
        queryset=VenueSection.objects.order_by('name'),
    )


def annotate_waitlist_count(qs):
    """People currently waiting (un-notified TicketAlert rows) for this event."""
    waiting = (
        TicketAlert.objects.filter(event_id=OuterRef('pk'), notified=False)
        .order_by()
        .values('event_id')
        .annotate(c=Count('id'))
        .values('c')
    )
    return qs.annotate(
        _waitlist_count=Coalesce(
            Subquery(waiting[:1], output_field=IntegerField()),
            Value(0),
        )
    )


def annotate_active_tickets_total(qs):
    qs = qs.annotate(
        _active_tickets_total=Coalesce(
            Sum(
                'tickets__available_quantity',
                filter=Q(tickets__status='active', tickets__available_quantity__gt=0),
            ),
            Value(0),
        )
    )
    return annotate_waitlist_count(qs)
