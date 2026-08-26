import { describe, expect, it } from 'vitest';
import {
  incrementSeatLabel,
  listingGroupTickets,
  matchZoneFromOcr,
  mergeSeatingDraft,
  seatingAssignmentsForGroup,
  seatingFromTicket,
  ticketFileKind,
  venueSectionNamesForTicket,
} from './adminTicketSeating';

describe('adminTicketSeating', () => {
  it('prefers display section, row, and seat from the ticket payload', () => {
    expect(
      seatingFromTicket({
        section: '12',
        custom_section_text: 'ignored',
        row: '4',
        row_number: '9',
        seat_number: '22',
        seat_numbers: 'ignored',
      }),
    ).toEqual({ section: '12', row: '4', seat: '22' });
  });

  it('lets an in-progress draft override empty seller fields', () => {
    const ticket = { id: 7, section: '', row: '', seat_number: '' };
    expect(mergeSeatingDraft(ticket, { 7: { section: 'דשא', row: '1', seat: '12' } })).toEqual({
      section: 'דשא',
      row: '1',
      seat: '12',
    });
  });

  it('auto-increments numeric seats across a listing group', () => {
    expect(incrementSeatLabel('12', 1)).toBe('13');
    expect(incrementSeatLabel('A12', 2)).toBe('A14');
    const tickets = [
      { id: 10, listing_group_id: 'g1' },
      { id: 11, listing_group_id: 'g1' },
      { id: 12, listing_group_id: 'g1' },
    ];
    expect(listingGroupTickets(tickets, tickets[1]).map((row) => row.id)).toEqual([10, 11, 12]);
    expect(
      seatingAssignmentsForGroup({
        tickets,
        anchorId: 10,
        section: 'Block 12',
        row: '7',
        seat: '12',
      }).map((row) => row.seat),
    ).toEqual(['12', '13', '14']);
  });

  it('lists mapped venue sections and detects image tickets', () => {
    expect(
      venueSectionNamesForTicket({
        event: { venue_detail: { sections: [{ name: '14' }, { name: 'Block 12' }] } },
      }),
    ).toEqual(['14', 'Block 12']);
    expect(ticketFileKind({ ticket_file_kind: 'image' })).toBe('image');
    expect(ticketFileKind({ ticket_file_url: 'https://cdn.example/t.pdf' })).toBe('pdf');
  });

  it('falls back to Sultan\'s Pool sell zones when the venue has no DB sections', () => {
    expect(
      venueSectionNamesForTicket({
        event: {
          venue: 'ישראל',
          venue_detail: { name: 'בריכת הסולטן', city: 'ירושלים', sections: [] },
        },
      }),
    ).toEqual(['אורקסטרה', 'גוש 1', 'גוש 2', 'גוש 3', 'גוש 4', 'גוש 5', 'מושבים נגישים']);
  });

  it('matches the longest mapped zone name inside extracted PDF text', () => {
    const zones = ['אורקסטרה', 'גוש 1', 'גוש 11', 'מושבים נגישים'];
    expect(matchZoneFromOcr('כרטיס לאורקסטרה בריכת הסולטן', zones)).toBe('אורקסטרה');
    expect(matchZoneFromOcr('כניסה גוש 11 שורה 4', zones)).toBe('גוש 11');
    expect(matchZoneFromOcr('no zone here', zones)).toBe('');
  });
});
