import { describe, expect, it } from 'vitest';
import {
  isPaidActiveOrder,
  orderCanDownloadTickets,
  orderTicketIds,
  resolveDownloadTicketId,
  timelineForBuyerDisplay,
} from './buyerOrderActions';

describe('buyerOrderActions', () => {
  const paid = {
    status: 'paid',
    ticket: 9,
    tickets: [{ id: 9, pdf_file_url: '/api/users/tickets/9/download_pdf/', has_pdf_file: true }],
    status_timeline: {
      current_step: 2,
      current_label: 'מעבד',
      steps: [
        { step: 1, label: 'הזמנה אושרה', completed: true },
        { step: 2, label: 'מעבד', completed: false },
        { step: 3, label: 'מוכן להורדה', completed: false },
      ],
    },
  };

  it('treats paid orders as ready to download', () => {
    expect(isPaidActiveOrder(paid)).toBe(true);
    expect(orderCanDownloadTickets(paid)).toBe(true);
    expect(orderTicketIds(paid)).toEqual([9]);
  });

  it('shows download for paid orders even when ticket ids are missing', () => {
    expect(orderCanDownloadTickets({ status: 'paid', tickets: [] })).toBe(true);
    expect(orderCanDownloadTickets({ status: 'completed' })).toBe(true);
    expect(orderCanDownloadTickets({ status: 'pending' })).toBe(false);
  });

  it('resolves a ticket id from the download URL when tickets are missing', () => {
    expect(
      orderTicketIds({
        status: 'paid',
        pdf_download_url: 'https://example.com/api/users/tickets/77/download_pdf/',
      }),
    ).toEqual([77]);
  });

  it('resolves a ticket id from ticket_details.id', () => {
    expect(orderTicketIds({ status: 'paid', tickets: [], ticket_details: { id: 55 } })).toEqual([55]);
    expect(resolveDownloadTicketId({ status: 'paid', ticket: 42, tickets: [] })).toBe(42);
  });

  it('keeps processing on step 2 and ready-to-download only on step 3', () => {
    const timeline = timelineForBuyerDisplay(paid, paid.status_timeline);
    expect(timeline.current_label).toBe('מוכן להורדה');
    expect(timeline.steps[1].label).toBe('תשלום אושר');
    expect(timeline.steps[2].label).toBe('מוכן להורדה');
    expect(timeline.steps.filter((s) => s.label === 'מוכן להורדה')).toHaveLength(1);
    expect(timeline.steps[1].completed).toBe(true);
    expect(timeline.steps[2].completed).toBe(true);
  });
});
