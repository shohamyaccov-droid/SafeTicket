export function seatingFromTicket(ticket) {
  return {
    section: String(ticket?.section || ticket?.custom_section_text || '').trim(),
    row: String(ticket?.row || ticket?.row_number || '').trim(),
  };
}

export function mergeSeatingDraft(ticket, drafts) {
  const base = seatingFromTicket(ticket);
  const extra = drafts?.[ticket?.id];
  if (!extra) return base;
  return {
    section: extra.section ?? base.section,
    row: extra.row ?? base.row,
  };
}
