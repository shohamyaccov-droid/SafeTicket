import { describe, expect, it } from 'vitest';
import { mergeSeatingDraft, seatingFromTicket } from './adminTicketSeating';

describe('adminTicketSeating', () => {
  it('prefers display section and row from the ticket payload', () => {
    expect(
      seatingFromTicket({
        section: '12',
        custom_section_text: 'ignored',
        row: '4',
        row_number: '9',
      }),
    ).toEqual({ section: '12', row: '4' });
  });

  it('lets an in-progress draft override empty seller fields', () => {
    const ticket = { id: 7, section: '', row: '' };
    expect(mergeSeatingDraft(ticket, { 7: { section: 'דשא', row: '1' } })).toEqual({
      section: 'דשא',
      row: '1',
    });
  });
});
