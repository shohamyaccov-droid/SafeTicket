"""Admin pending-queue seating: section/row/seat plus listing-group auto-increment."""
from __future__ import annotations

import os
import re
from typing import List, Sequence, Tuple

from .models import Ticket, VenueSection

ALLOWED_SEATING_STATUSES = ('pending_approval', 'active', 'reserved')
_SEAT_INCREMENT_RE = re.compile(r'^(.*?)(\d+)(\D*)$')
_IMAGE_EXTS = frozenset({'jpg', 'jpeg', 'png', 'webp', 'gif'})


def request_flag(data, key: str, default: bool = True) -> bool:
    if data is None or key not in data:
        return default
    raw = data.get(key)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def optional_seating_from_request(request) -> dict:
    data = getattr(request, 'data', None) or {}
    payload = {}
    if 'section' in data:
        raw = data.get('section')
        payload['section'] = '' if raw is None else str(raw).strip()
    if 'row' in data:
        raw = data.get('row')
        payload['row'] = '' if raw is None else str(raw).strip()
    seat_key = None
    for candidate in ('seat', 'seat_number', 'seat_numbers'):
        if candidate in data:
            seat_key = candidate
            break
    if seat_key is not None:
        raw = data.get(seat_key)
        payload['seat'] = '' if raw is None else str(raw).strip()
    return payload


def increment_seat_label(seat, offset: int) -> str:
    """Bump a seat label by ``offset`` (12 → 13, A12 → A13). Non-numeric labels stay put."""
    text = '' if seat is None else str(seat).strip()
    if not text or not offset:
        return text
    match = _SEAT_INCREMENT_RE.match(text)
    if not match:
        return text
    prefix, digits, suffix = match.group(1), match.group(2), match.group(3)
    next_number = int(digits) + int(offset)
    if next_number < 0:
        next_number = 0
    return f'{prefix}{str(next_number).zfill(len(digits))}{suffix}'


def match_venue_section_for_ticket(ticket, section_text):
    event = getattr(ticket, 'event', None)
    venue_id = getattr(event, 'venue_place_id', None) if event is not None else None
    if not venue_id or not section_text:
        return None
    qs = VenueSection.objects.filter(venue_id=venue_id)
    matched = qs.filter(name__iexact=section_text).first()
    if matched:
        return matched
    stripped = section_text
    for prefix in ('גוש ', 'גוש', 'Section ', 'Block '):
        if stripped.lower().startswith(prefix.lower()):
            stripped = stripped[len(prefix):].strip()
            break
    if stripped and stripped != section_text:
        return qs.filter(name__iexact=stripped).first()
    return None


def apply_admin_ticket_seating(ticket, *, section=None, row=None, seat=None):
    """Write free-text גוש/שורה/כיסא from the admin review queue onto a ticket."""
    changed = []
    if section is not None:
        matched = match_venue_section_for_ticket(ticket, section) if section else None
        if matched:
            ticket.venue_section = matched
            ticket.custom_section_text = ''
            ticket.section_legacy = (matched.name or '')[:100]
        else:
            ticket.venue_section = None
            ticket.custom_section_text = (section or '')[:100]
            ticket.section_legacy = (section or '')[:100]
        changed.extend(['venue_section', 'custom_section_text', 'section_legacy'])
    if row is not None:
        ticket.row = row
        ticket.row_number = row
        changed.extend(['row', 'row_number'])
    if seat is not None:
        ticket.seat_number = seat
        ticket.seat_numbers = seat
        changed.extend(['seat_number', 'seat_numbers'])
    return changed


def listing_group_members(ticket) -> List[Ticket]:
    gid = (getattr(ticket, 'listing_group_id', None) or '').strip()
    if not gid:
        return [ticket]
    members = list(
        Ticket.objects.filter(listing_group_id=gid)
        .select_related('seller', 'event', 'event__venue_place', 'venue_section')
        .order_by('id')
    )
    if not any(member.pk == ticket.pk for member in members):
        members.append(ticket)
        members.sort(key=lambda item: item.pk or 0)
    return members


def apply_admin_seating_to_ticket_or_group(
    ticket,
    seating: dict,
    *,
    apply_to_group: bool = True,
    allowed_statuses: Sequence[str] = ALLOWED_SEATING_STATUSES,
) -> List[Tuple[Ticket, list]]:
    """
    Apply section/row to every sibling in the listing group.
    Auto-increment ``seat`` from the posted ticket's position (12, 13, 14…).
    """
    group = listing_group_members(ticket) if apply_to_group else [ticket]
    group = [member for member in group if member.status in allowed_statuses]
    if not group:
        group = [ticket]
    try:
        anchor_idx = next(i for i, member in enumerate(group) if member.pk == ticket.pk)
    except StopIteration:
        group = [ticket]
        anchor_idx = 0

    results = []
    for index, member in enumerate(group):
        member_seating = dict(seating)
        if 'seat' in member_seating:
            member_seating['seat'] = increment_seat_label(
                member_seating.get('seat'),
                index - anchor_idx,
            )
        fields = apply_admin_ticket_seating(member, **member_seating)
        results.append((member, fields))
    return results


def ticket_file_kind(ticket) -> str:
    name = ''
    try:
        name = (getattr(getattr(ticket, 'pdf_file', None), 'name', None) or '').strip()
    except Exception:
        name = ''
    ext = os.path.splitext(name)[1].lstrip('.').lower()
    if ext in _IMAGE_EXTS:
        return 'image'
    return 'pdf'
