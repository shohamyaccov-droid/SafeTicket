import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import OptionalSeatingDisclosure, { SEATING_HINT } from './OptionalSeatingDisclosure';

afterEach(() => {
  cleanup();
});

describe('OptionalSeatingDisclosure', () => {
  it('hides seating fields until the optional toggle is opened', async () => {
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
    expect(screen.queryByLabelText('גוש (אופציונלי)')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '➕ הוספת פרטי ישיבה (אופציונלי)' }));
    expect(screen.getByText(SEATING_HINT)).toBeInTheDocument();
    expect(screen.getByLabelText('גוש (אופציונלי)')).toBeInTheDocument();
  });
});
