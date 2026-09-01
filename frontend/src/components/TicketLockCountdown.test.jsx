import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TicketLockCountdown from './TicketLockCountdown';

describe('TicketLockCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-01T12:00:00.000Z'));
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('renders the Hebrew MM:SS label and refreshes once at 00:00', () => {
    const onExpire = vi.fn();
    render(
      <TicketLockCountdown
        lockedUntil="2026-09-01T12:00:02.000Z"
        onExpire={onExpire}
      />,
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'מישהו בתהליך קנייה. משתחרר בעוד 00:02',
    );

    act(() => {
      vi.advanceTimersByTime(2100);
    });
    expect(screen.getByRole('status')).toHaveTextContent(
      'מישהו בתהליך קנייה. משתחרר בעוד 00:00',
    );
    expect(onExpire).toHaveBeenCalledTimes(1);
  });
});
