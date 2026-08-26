import { canonicalVenueName, generatedSectionOptionsForVenue } from './sellVenueSections';

export function seatingFromTicket(ticket) {
  return {
    section: String(ticket?.section || ticket?.custom_section_text || '').trim(),
    row: String(ticket?.row || ticket?.row_number || '').trim(),
    seat: String(ticket?.seat_number || ticket?.seat_numbers || '').trim(),
  };
}

export function mergeSeatingDraft(ticket, drafts) {
  const base = seatingFromTicket(ticket);
  const extra = drafts?.[ticket?.id];
  if (!extra) return base;
  return {
    section: extra.section ?? base.section,
    row: extra.row ?? base.row,
    seat: extra.seat ?? base.seat,
  };
}

export function incrementSeatLabel(seat, offset) {
  const text = String(seat ?? '').trim();
  if (!text || !offset) return text;
  const match = text.match(/^(.*?)(\d+)(\D*)$/);
  if (!match) return text;
  const [, prefix, digits, suffix] = match;
  const next = Math.max(0, Number(digits) + Number(offset));
  return `${prefix}${String(next).padStart(digits.length, '0')}${suffix}`;
}

export function listingGroupTickets(tickets, ticket) {
  const gid = String(ticket?.listing_group_id || '').trim();
  if (!gid) return ticket ? [ticket] : [];
  return [...tickets]
    .filter((row) => String(row?.listing_group_id || '').trim() === gid)
    .sort((a, b) => Number(a.id) - Number(b.id));
}

export function fillSequentialSeatsByTicketId(tickets, startSeat) {
  const map = {};
  (Array.isArray(tickets) ? tickets : []).forEach((row, index) => {
    map[row.id] = startSeat ? incrementSeatLabel(startSeat, index) : '';
  });
  return map;
}

export function initialSeatsByTicketId(tickets, startSeat) {
  const list = Array.isArray(tickets) ? tickets : [];
  const hasStored = list.some((row) => String(row?.seat_number || row?.seat_numbers || '').trim());
  if (!hasStored) return fillSequentialSeatsByTicketId(list, startSeat);
  const map = {};
  list.forEach((row, index) => {
    const existing = String(row?.seat_number || row?.seat_numbers || '').trim();
    map[row.id] = existing || (startSeat ? incrementSeatLabel(startSeat, index) : '');
  });
  return map;
}

export function seatForTicket(seatsByTicketId, ticketId) {
  if (!seatsByTicketId) return '';
  if (ticketId in seatsByTicketId) return String(seatsByTicketId[ticketId] ?? '');
  const asString = String(ticketId);
  if (asString in seatsByTicketId) return String(seatsByTicketId[asString] ?? '');
  return '';
}

export function seatingAssignmentsForGroup({ tickets, anchorId, section, row, seat, seatsByTicketId }) {
  const list = Array.isArray(tickets) ? tickets : [];
  const found = list.findIndex((rowTicket) => Number(rowTicket.id) === Number(anchorId));
  const anchorIndex = found < 0 ? 0 : found;
  return list.map((rowTicket, index) => ({
    ticketId: rowTicket.id,
    section,
    row,
    seat: seatsByTicketId
      ? seatForTicket(seatsByTicketId, rowTicket.id)
      : incrementSeatLabel(seat, index - anchorIndex),
  }));
}

export function venueSectionNamesForEvent(eventLike) {
  const sections = eventLike?.venue_detail?.sections;
  if (Array.isArray(sections) && sections.length > 0) {
    const names = [
      ...new Set(sections.map((section) => String(section?.name || '').trim()).filter(Boolean)),
    ];
    names.sort((a, b) => a.localeCompare(b, 'he', { numeric: true }));
    return names;
  }
  const fallback = generatedSectionOptionsForVenue(canonicalVenueName(eventLike || {}));
  return fallback.map((option) => String(option.value || option.label || '').trim()).filter(Boolean);
}

export function venueSectionNamesForTicket(ticket) {
  return venueSectionNamesForEvent(ticket?.event || ticket);
}

function normalizeZoneNeedle(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/גוש\s+/g, 'גוש ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Pick the longest mapped zone name that appears in extracted PDF / OCR text. */
export function matchZoneFromOcr(text, zoneNames) {
  const hay = normalizeZoneNeedle(text);
  if (!hay || !Array.isArray(zoneNames) || zoneNames.length === 0) return '';
  const ranked = [...new Set(zoneNames.map((name) => String(name || '').trim()).filter(Boolean))].sort(
    (a, b) => b.length - a.length,
  );
  for (const name of ranked) {
    const needle = normalizeZoneNeedle(name);
    if (needle && hay.includes(needle)) return name;
  }
  return '';
}

export function ticketFileKind(ticket) {
  if (ticket?.ticket_file_kind === 'image') return 'image';
  const url = String(ticket?.ticket_file_url || ticket?.pdf_file_url || '');
  if (/\.(jpe?g|png|webp|gif)(\?|#|$)/i.test(url)) return 'image';
  return 'pdf';
}

export function seatingPayload(values, { applyToGroup = true, approveGroup = false } = {}) {
  const payload = {
    section: values?.section ?? '',
    row: values?.row ?? '',
    seat: values?.seat ?? '',
    apply_to_group: applyToGroup,
  };
  const map = values?.seatsByTicketId;
  if (map && typeof map === 'object') {
    payload.seats = Object.entries(map).map(([ticketId, seat]) => ({
      ticket_id: Number(ticketId),
      seat: String(seat ?? ''),
    }));
  }
  if (approveGroup) payload.approve_group = true;
  return payload;
}
