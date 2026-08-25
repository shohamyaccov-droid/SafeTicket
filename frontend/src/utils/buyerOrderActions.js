export function isPaidActiveOrder(purchase) {
  const status = String(purchase?.status || '').toLowerCase();
  return status === 'paid' || status === 'completed';
}

function coerceTicketId(value) {
  if (value == null || value === '') return null;
  if (typeof value === 'object') return value.id ?? value.ticket_id ?? null;
  const n = Number(value);
  if (Number.isFinite(n) && n > 0) return n;
  return value;
}

export function ticketIdFromDownloadUrl(url) {
  const match = String(url || '').match(/\/tickets\/(\d+)\/download_pdf\/?/i);
  return match ? Number(match[1]) : null;
}

function ticketIdFromTicketLike(ticket) {
  const direct = coerceTicketId(ticket);
  if (direct != null && direct !== '') return direct;
  if (!ticket || typeof ticket !== 'object') return null;
  return (
    ticketIdFromDownloadUrl(ticket.pdf_file_url) ||
    ticketIdFromDownloadUrl(ticket.pdf_download_url) ||
    null
  );
}

export function orderTicketIds(purchase) {
  const tickets = Array.isArray(purchase?.tickets) ? purchase.tickets : [];
  const fromTickets = tickets.map(ticketIdFromTicketLike).filter((id) => id != null && id !== '');
  if (fromTickets.length) return fromTickets;

  const fromTicketIds = (Array.isArray(purchase?.ticket_ids) ? purchase.ticket_ids : [])
    .map(coerceTicketId)
    .filter((id) => id != null && id !== '');
  if (fromTicketIds.length) return fromTicketIds;

  const fallback =
    coerceTicketId(purchase?.ticket) ||
    coerceTicketId(purchase?.ticket_id) ||
    ticketIdFromTicketLike(purchase?.ticket_details);
  if (fallback != null && fallback !== '') return [fallback];

  const fromUrl =
    ticketIdFromDownloadUrl(purchase?.pdf_download_url) ||
    ticketIdFromDownloadUrl(purchase?.ticket_details?.pdf_download_url) ||
    ticketIdFromDownloadUrl(purchase?.ticket_details?.pdf_file_url);
  return fromUrl != null ? [fromUrl] : [];
}

export function resolveDownloadTicketId(purchase) {
  const ids = orderTicketIds(purchase);
  return ids.length ? ids[0] : null;
}

export function orderTicketIsDownloadable(ticket) {
  if (!ticket) return false;
  return Boolean(ticket.pdf_file_url || ticket.has_pdf_file);
}

/** Paid/completed matches the stepper "ready to download" step — do not require ids up front. */
export function orderCanDownloadTickets(purchase) {
  return isPaidActiveOrder(purchase);
}

/** Merge ticket_details + tickets[0] so section/row/seat survive thin payloads. */
export function purchaseSeatDetails(purchase) {
  const details = purchase?.ticket_details && typeof purchase.ticket_details === 'object'
    ? purchase.ticket_details
    : {};
  const firstTicket = Array.isArray(purchase?.tickets) && purchase.tickets[0]
    ? purchase.tickets[0]
    : {};
  return {
    ...firstTicket,
    ...details,
    section: details.section || firstTicket.section || details.section_legacy || details.custom_section_text || '',
    row: details.row || details.row_number || firstTicket.row || '',
    seat_numbers: details.seat_numbers || details.seat_number || firstTicket.seat_numbers || '',
    seat_number: details.seat_number || details.seat_numbers || firstTicket.seat_number || '',
    seat_row: details.seat_row || firstTicket.seat_row || '',
    venue: details.venue || details.event_venue || firstTicket.venue || '',
    id: details.id || firstTicket.id || coerceTicketId(purchase?.ticket) || null,
  };
}

export function formatPurchaseSectionRow(seat) {
  const section = (seat?.section || seat?.section_legacy || seat?.custom_section_text || '').trim();
  const row = (seat?.row || seat?.row_number || '').trim();
  const parts = [];
  if (section) parts.push(`גוש ${section}`);
  if (row) parts.push(`שורה ${row}`);
  if (parts.length) return parts.join(', ');
  if ((seat?.seat_row || '').trim()) return String(seat.seat_row).trim();
  if ((seat?.venue || '').trim()) return String(seat.venue).trim();
  return '';
}

export function formatPurchaseSeat(seat) {
  const value = (seat?.seat_numbers || seat?.seat_number || seat?.seat || '').trim();
  return value;
}

const STEP1 = 'הזמנה אושרה';
const STEP2_PENDING = 'מעבד';
const STEP2_PAID = 'תשלום אושר';
const STEP3 = 'מוכן להורדה';

function defaultTimelineSteps(paid) {
  return [
    { step: 1, label: STEP1, completed: paid },
    { step: 2, label: paid ? STEP2_PAID : STEP2_PENDING, completed: paid },
    { step: 3, label: STEP3, completed: paid },
  ];
}

/** Paid orders: step 2 is payment confirmed; only step 3 is "ready to download". */
export function timelineForBuyerDisplay(purchase, timeline) {
  const paid = isPaidActiveOrder(purchase);
  const incoming = Array.isArray(timeline?.steps) ? timeline.steps : [];
  const base = incoming.length ? incoming : defaultTimelineSteps(paid);
  const steps = base.map((step) => {
    if (step.step === 1) {
      return { ...step, label: STEP1, completed: paid || Boolean(step.completed) };
    }
    if (step.step === 2) {
      return { ...step, label: paid ? STEP2_PAID : STEP2_PENDING, completed: paid };
    }
    if (step.step === 3) {
      return { ...step, label: STEP3, completed: paid };
    }
    return step;
  });
  return {
    current_step: paid ? 3 : timeline?.current_step || 1,
    current_label: paid ? STEP3 : timeline?.current_label || STEP2_PENDING,
    steps,
  };
}
