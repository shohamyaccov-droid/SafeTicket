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
    expect(onDownload).toHaveBeenCalledWith(42, expect.any(Object));
  });

  it('renders for paid orders with only ticket_details.id', async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    render(
      <BuyerOrderDownloadBar
        purchase={{ status: 'paid', tickets: [], ticket_details: { id: 55 } }}
        onDownload={onDownload}
      />,
    );
    const button = screen.getByRole('button', { name: 'הורד כרטיס' });
    expect(button).toBeInTheDocument();
    await user.click(button);
    expect(onDownload).toHaveBeenCalledWith(55, expect.any(Object));
  });

  it('renders for paid orders with empty tickets and only pdf_download_url', async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    render(
      <BuyerOrderDownloadBar
        purchase={{
          status: 'completed',
          tickets: [],
          pdf_download_url: 'https://example.com/api/users/tickets/77/download_pdf/',
        }}
        onDownload={onDownload}
      />,
    );
    const button = screen.getByRole('button', { name: 'הורד כרטיס' });
    expect(button).toBeInTheDocument();
    expect(button).toBeVisible();
    await user.click(button);
    expect(onDownload).toHaveBeenCalledWith(77, expect.any(Object));
  });

  it('still renders הורד כרטיס for paid orders when no ticket id is present yet', () => {
    render(
      <BuyerOrderDownloadBar
        purchase={{ status: 'paid', tickets: [], ticket_details: { event_name: 'Show' } }}
        onDownload={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: 'הורד כרטיס' })).toBeInTheDocument();
  });

  it('resolves download from ticket_ids alone', async () => {
    const user = userEvent.setup();
    const onDownload = vi.fn();
    render(
      <BuyerOrderDownloadBar
        purchase={{ status: 'paid', ticket: null, tickets: [], ticket_ids: [64] }}
        onDownload={onDownload}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'הורד כרטיס' }));
    expect(onDownload).toHaveBeenCalledWith(64, expect.objectContaining({ ticket_ids: [64] }));
  });
});
