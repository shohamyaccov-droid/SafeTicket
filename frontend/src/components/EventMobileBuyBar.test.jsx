import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import EventMobileBuyBar from './EventMobileBuyBar';

vi.mock('../hooks/useBuyerServiceFeePercent', () => ({
  default: () => 7,
}));

describe('EventMobileBuyBar', () => {
  it('shows the all-in price with no fee copy', async () => {
    const onBuy = vi.fn();
    render(
      <EventMobileBuyBar
        ticket={{ asking_price: '150.00', original_price: '150.00', currency: 'ILS' }}
        onBuy={onBuy}
      />
    );
    expect(screen.getByText(/₪\s*161/)).toBeInTheDocument();
    expect(screen.queryByText(/דמי שירות/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'קנה עכשיו' }));
    expect(onBuy).toHaveBeenCalledTimes(1);
  });

  it('renders nothing without a ticket', () => {
    const { container } = render(<EventMobileBuyBar ticket={null} onBuy={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows a scarcity cue when three or fewer tickets remain', () => {
    render(
      <EventMobileBuyBar
        ticket={{ asking_price: '90.00', currency: 'ILS' }}
        remainingCount={2}
        onBuy={() => {}}
      />
    );
    expect(screen.getByText('נשארו 2 כרטיסים בקבוצה הזו')).toBeInTheDocument();
  });
});
