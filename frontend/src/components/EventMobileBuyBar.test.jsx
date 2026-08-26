import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import EventMobileBuyBar from './EventMobileBuyBar';

describe('EventMobileBuyBar', () => {
  it('shows the lowest price and fires onBuy from קנה עכשיו', async () => {
    const onBuy = vi.fn();
    render(
      <EventMobileBuyBar
        ticket={{ asking_price: '150.00', original_price: '150.00', currency: 'ILS' }}
        onBuy={onBuy}
      />
    );
    expect(screen.getByText(/כרטיסים מ-/)).toBeInTheDocument();
    expect(screen.getByText(/150/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'קנה עכשיו' }));
    expect(onBuy).toHaveBeenCalledTimes(1);
  });

  it('renders nothing without a ticket', () => {
    const { container } = render(<EventMobileBuyBar ticket={null} onBuy={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
