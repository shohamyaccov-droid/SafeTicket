export function isPaidActiveOrder(purchase) {
  const status = String(purchase?.status || '').toLowerCase();
  return status === 'paid' || status === 'completed';
}

export function orderTicketIds(purchase) {
  const tickets = Array.isArray(purchase?.tickets) ? purchase.tickets : [];
  const fromTickets = tickets.map((t) => t?.id).filter((id) => id != null && id !== '');
  if (fromTickets.length) return fromTickets;
  const fallback = purchase?.ticket || purchase?.ticket_details?.id;
  return fallback != null && fallback !== '' ? [fallback] : [];
}

export function orderTicketIsDownloadable(ticket) {
  if (!ticket) return false;
  return Boolean(ticket.pdf_file_url || ticket.has_pdf_file);
}

export function orderCanDownloadTickets(purchase) {
  if (!isPaidActiveOrder(purchase)) return false;
  if (purchase?.pdf_download_url) return orderTicketIds(purchase).length > 0;
  const tickets = Array.isArray(purchase?.tickets) ? purchase.tickets : [];
  if (tickets.some(orderTicketIsDownloadable)) return true;
  return orderTicketIds(purchase).length > 0;
}

/** Paid/active orders should never sit on the "מעבד" step. */
export function timelineForBuyerDisplay(purchase, timeline) {
  const steps = Array.isArray(timeline?.steps) ? timeline.steps : [];
  if (!isPaidActiveOrder(purchase)) {
    return { current_step: timeline?.current_step || 0, current_label: timeline?.current_label || '', steps };
  }
  return {
    current_step: 3,
    current_label: 'מוכן להורדה',
    steps: steps.map((step) => {
      if (step.step === 2 || step.label === 'מעבד') {
        return { ...step, label: 'מוכן להורדה', completed: true };
      }
      if (step.step === 1 || step.step === 3) {
        return { ...step, completed: true };
      }
      return { ...step, completed: true };
    }),
  };
}
