import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import OptionalSeatingDisclosure, { SEATING_HINT } from './OptionalSeatingDisclosure';

afterEach(() => {
  cleanup();
});

describe('OptionalSeatingDisclosure', () => {
  it('starts closed and only shows seating fields after the toggle is clicked', async () => {
    const user = userEvent.setup();
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <OptionalSeatingDisclosure open={open} onToggle={() => setOpen((v) => !v)}>
          <label htmlFor="section">גוש (אופציונלי)</label>
          <input id="section" />
        </OptionalSeatingDisclosure>
      );
    }
    render(<Harness />);
    const toggle = screen.getByRole('button', { name: '➕ הוספת פרטי ישיבה (אופציונלי)' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByLabelText('גוש (אופציונלי)')).not.toBeInTheDocument();
    expect(screen.queryByText(SEATING_HINT)).not.toBeInTheDocument();
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText(SEATING_HINT)).toBeInTheDocument();
    expect(screen.getByLabelText('גוש (אופציונלי)')).toBeInTheDocument();
  });
});
