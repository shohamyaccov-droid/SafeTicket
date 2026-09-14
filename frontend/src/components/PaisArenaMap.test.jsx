import { describe, expect, test } from 'vitest';
import { render } from '@testing-library/react';
import PaisArenaMap from '../components/PaisArenaMap';

describe('PaisArenaMap', () => {
  test('turns גוש 2 green and draws a price pill over that path', () => {
    const ticket = {
      status: 'active',
      section: 'גוש 2',
      asking_price: 240,
      currency: 'ILS',
      available_quantity: 2,
    };
    const rows = [
      {
        stableId: 'listing-2',
        group: { available_count: 2, tickets: [ticket] },
        firstTicket: ticket,
        pais: { sectionId: 'lower-2' },
      },
    ];
    const { container } = render(<PaisArenaMap rows={rows} />);
    const path = container.querySelector('[data-section-id="lower-2"]');
    expect(path).toBeTruthy();
    expect(path.getAttribute('fill')).toBe('#22c55e');
    const empty = container.querySelector('[data-section-id="lower-3"]');
    expect(empty.getAttribute('fill')).toBe('#f3f4f6');
    expect(container.textContent).toMatch(/240/);
    expect(container.querySelector('foreignObject')).toBeTruthy();
  });
});
