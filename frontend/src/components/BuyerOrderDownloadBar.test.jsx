import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import BuyerOrderDownloadBar from './BuyerOrderDownloadBar';

afterEach(() => {
  cleanup();
});

describe('BuyerOrderDownloadBar', () => {
  it('shows a download button for paid orders even without pdf flags', async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    render(
      <BuyerOrderDownloadBar
        purchase={{ status: 'paid', ticket: 42, tickets: [] }}
        onDownload={onDownload}
      />,
    );
    const button = screen.getByRole('button', { name: 'הורד כרטיס' });
    expect(button).toBeInTheDocument();
    await user.click(button);
    expect(onDownload).toHaveBeenCalledWith(42);
  });

  it('does not render for unpaid orders', () => {
    render(
      <BuyerOrderDownloadBar
        purchase={{ status: 'pending', ticket: 42 }}
        onDownload={vi.fn()}
      />,
    );
    expect(screen.queryByRole('button', { name: 'הורד כרטיס' })).not.toBeInTheDocument();
  });
});
