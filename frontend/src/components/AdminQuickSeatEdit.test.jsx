import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import AdminQuickSeatEdit from './AdminQuickSeatEdit';

function Harness() {
  const [values, setValues] = useState({ section: '', row: '' });
  return <AdminQuickSeatEdit values={values} onChange={setValues} />;
}

describe('AdminQuickSeatEdit', () => {
  it('lets an admin type section and row when the seller left them blank', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    await user.type(screen.getByLabelText('גוש'), '14');
    await user.type(screen.getByLabelText('שורה'), '8');
    expect(screen.getByLabelText('גוש')).toHaveValue('14');
    expect(screen.getByLabelText('שורה')).toHaveValue('8');
  });
});
