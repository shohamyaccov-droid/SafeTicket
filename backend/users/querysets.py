"""Shared select_related / prefetch / annotate helpers for catalog querysets."""
from django.db.models import Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce

from users.models import VenueSection

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


def annotate_active_tickets_total(qs):
    return qs.annotate(
        _active_tickets_total=Coalesce(
            Sum(
                'tickets__available_quantity',
                filter=Q(tickets__status='active', tickets__available_quantity__gt=0),
            ),
            Value(0),
        )
    )
