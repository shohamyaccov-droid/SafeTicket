import { describe, expect, it } from 'vitest';
import {
  isPaidActiveOrder,
  orderCanDownloadTickets,
  orderTicketIds,
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

  it('replaces the processing step with ready-for-download', () => {
    const timeline = timelineForBuyerDisplay(paid, paid.status_timeline);
    expect(timeline.current_label).toBe('מוכן להורדה');
    expect(timeline.steps.map((s) => s.label)).not.toContain('מעבד');
    expect(timeline.steps[1].label).toBe('מוכן להורדה');
    expect(timeline.steps[1].completed).toBe(true);
  });
});
