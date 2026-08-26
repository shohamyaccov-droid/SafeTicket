import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import BloomfieldTicketListPanel from './BloomfieldTicketListPanel';

vi.mock('../hooks/useBuyerServiceFeePercent', () => ({
  default: () => 7,
}));

const buyableGroup = {
  id: 'g1',
  listing_group_id: 'g1',
  available_count: 2,
  split_type: 'any',
  tickets: [
    {
      id: 11,
      asking_price: '90.00',
      original_price: '90.00',
      section: 'A',
      row: '3',
      allow_negotiation: true,
      status: 'active',
    },
  ],
};

describe('BloomfieldTicketListPanel buy CTA', () => {
  it('shows קנה עכשיו on the collapsed row without expanding', async () => {
    const onBuy = vi.fn();
    render(
      <BloomfieldTicketListPanel
        rows={[
          {
            stableId: 'g1',
            group: buyableGroup,
            firstTicket: buyableGroup.tickets[0],
            bloomfield: { row: '3', sectionId: 'A', zone: 'north', blockId: 'n1' },
          },
        ]}
        onBuy={onBuy}
        onOffer={vi.fn()}
        onToggleRow={vi.fn()}
        onHoverRow={vi.fn()}
        onListingQuantityChange={vi.fn()}
        onOpenFilters={vi.fn()}
        isSellerFn={() => false}
        user={null}
        totalListingsBeforeQuantityFilter={1}
      />
    );
    const buy = screen.getByRole('button', { name: 'קנה עכשיו' });
    expect(buy).toBeVisible();
    expect(screen.queryByText('כמות')).not.toBeInTheDocument();
    await userEvent.click(buy);
    expect(onBuy).toHaveBeenCalledTimes(1);
  });
});
