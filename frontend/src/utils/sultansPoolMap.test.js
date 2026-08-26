import { describe, expect, it } from 'vitest';
import {
  isSultansPoolVenueName,
  sultansPoolTicketMatchesZone,
  sultansPoolZoneIdFromTicket,
} from './sultansPoolMap';

describe('sultansPoolMap', () => {
  it('detects Sultan\'s Pool venue names', () => {
    expect(isSultansPoolVenueName('בריכת הסולטן')).toBe(true);
    expect(isSultansPoolVenueName("Sultan's Pool")).toBe(true);
    expect(isSultansPoolVenueName('היכל מנורה')).toBe(false);
  });

  it('maps ticket sections to zone ids', () => {
    expect(sultansPoolZoneIdFromTicket({ section: 'גוש 1' })).toBe('gush-1');
    expect(sultansPoolZoneIdFromTicket({ section: 'אורקסטרה' })).toBe('orchestra');
    expect(sultansPoolZoneIdFromTicket({ section: 'מושבים נגישים' })).toBe('accessible');
    expect(sultansPoolZoneIdFromTicket({ section: 'גוש 11' })).toBe(null);
  });

  it('matches tickets to a clicked zone', () => {
    expect(sultansPoolTicketMatchesZone({ section: 'גוש 3' }, 'gush-3')).toBe(true);
    expect(sultansPoolTicketMatchesZone({ section: 'גוש 3' }, 'gush-1')).toBe(false);
  });
});
